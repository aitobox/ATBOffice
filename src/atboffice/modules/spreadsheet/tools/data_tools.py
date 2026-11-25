"""Excel 2003 Data/Tools menu operations implemented on the sheet model.

Each function mutates ``SheetDataModel`` cells directly and leaves undo recording and
repainting to the caller (``LedgerWindow`` wraps them in a grid undo snapshot).
"""

from __future__ import annotations

import fnmatch
import math
import re
import statistics
from collections.abc import Callable, Iterable
from typing import Any

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name, col_name
from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.spreadsheet.tools.chart_builder import resolve_range

Rect = tuple[int, int, int, int]

MAX_DATA_TABLE_CELLS = 2500


# ------------------------------------------------------------------ helpers
def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _clean(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def ensure_workbook(workbook: Any, sheet: Any) -> Any:
    """Return ``workbook`` or a throwaway workbook wrapping ``sheet`` for recalculation."""
    if workbook is not None:
        return workbook
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

    return WorkbookModel(sheets=[sheet])


def _set_value(sheet: Any, r: int, c: int, value: Any) -> None:
    cell = sheet.ensure_cell(r, c)
    cell.formula = None
    cell.cached_value = None
    cell.value = value
    sheet.dirty = True


def _set_formula(sheet: Any, r: int, c: int, formula: str, bold: bool = False) -> None:
    cell = sheet.ensure_cell(r, c)
    cell.formula = formula.lstrip("=")
    cell.value = None
    cell.cached_value = None
    if bold:
        cell.bold = True
    sheet.dirty = True


def shift_rows(sheet: Any, at: int, count: int) -> None:
    """Shift every cell/merge on or below row ``at`` by ``count`` rows (negative = up).

    When shifting up, the caller must already have removed the cells being overwritten.
    """
    if count == 0:
        return
    new_cells: dict[tuple[int, int], CellData] = {}
    for (r, c), cell in sheet.cells.items():
        if r >= at:
            new_cells[(r + count, c)] = cell
        else:
            new_cells[(r, c)] = cell
    sheet.cells = new_cells
    merges = []
    for mr1, mc1, mr2, mc2 in sheet.merges:
        if mr1 >= at:
            merges.append((mr1 + count, mc1, mr2 + count, mc2))
        else:
            merges.append((mr1, mc1, mr2, mc2))
    sheet.merges = merges
    sheet.dirty = True


AGGREGATES: dict[str, Callable[[list[Any]], Any]] = {
    "SUM": lambda v: sum(x for x in map(_num, v) if x is not None),
    "COUNT": lambda v: sum(1 for x in v if x not in (None, "")),
    "COUNTNUMS": lambda v: sum(1 for x in v if _num(x) is not None),
    "AVERAGE": lambda v: (
        statistics.fmean(n) if (n := [x for x in map(_num, v) if x is not None]) else 0
    ),
    "MAX": lambda v: max((x for x in map(_num, v) if x is not None), default=0),
    "MIN": lambda v: min((x for x in map(_num, v) if x is not None), default=0),
    "PRODUCT": lambda v: (
        math.prod(n) if (n := [x for x in map(_num, v) if x is not None]) else 0
    ),
    "STDEV": lambda v: (
        statistics.stdev(n) if len(n := [x for x in map(_num, v) if x is not None]) > 1 else 0
    ),
    "VAR": lambda v: (
        statistics.variance(n) if len(n := [x for x in map(_num, v) if x is not None]) > 1 else 0
    ),
}


# ------------------------------------------------------------------ subtotals
def _is_subtotal_row(sheet: Any, r: int, c1: int, c2: int) -> bool:
    for c in range(c1, c2 + 1):
        cell = sheet.get_cell(r, c)
        if cell is not None and cell.formula and "SUBTOTAL(" in cell.formula.upper():
            return True
    return False


def remove_subtotals(sheet: Any, rect: Rect) -> Rect:
    """Delete subtotal rows inside ``rect``; return the shrunken data rectangle."""
    r1, c1, r2, c2 = rect
    removed = 0
    r = r2
    while r > r1:
        if _is_subtotal_row(sheet, r, c1, c2):
            for c in list(range(c1, c2 + 1)):
                sheet.cells.pop((r, c), None)
            shift_rows(sheet, r + 1, -1)
            removed += 1
        r -= 1
    sheet.extra.pop("subtotals", None)
    breaks = sheet.view_state.row_breaks
    sheet.view_state.row_breaks = [b for b in breaks if not (r1 < b <= r2)]
    return r1, c1, r2 - removed, c2


def apply_subtotals(sheet: Any, rect: Rect, cfg: dict[str, Any]) -> Rect:
    """Insert ``SUBTOTAL`` rows after (or before) each group of ``rect``.

    ``rect`` includes the header row. Returns the new data rectangle (header to grand
    total row).
    """
    r1, c1, r2, c2 = rect
    if cfg.get("replace_current", True):
        r1, c1, r2, c2 = remove_subtotals(sheet, (r1, c1, r2, c2))
    gcol = c1 + int(cfg.get("group_by_col", 0))
    fn = int(cfg.get("function_code", 9))
    scols = [c1 + int(i) for i in cfg.get("subtotal_cols", [])]
    below = bool(cfg.get("summary_below", True))
    if r2 <= r1 or not scols:
        return r1, c1, r2, c2

    # Snapshot the data rows, then lay the block out again with subtotal rows.
    data_rows = list(range(r1 + 1, r2 + 1))
    groups: list[tuple[Any, list[int]]] = []
    for r in data_rows:
        key = sheet.get_cell_value(r, gcol)
        if groups and groups[-1][0] == key:
            groups[-1][1].append(r)
        else:
            groups.append((key, [r]))
    extra_rows = len(groups) + 1
    row_cells = {
        r: {c: sheet.cells.pop((r, c)) for c in range(c1, c2 + 1) if (r, c) in sheet.cells}
        for r in data_rows
    }
    shift_rows(sheet, r2 + 1, extra_rows)

    out = r1 + 1
    first_data = None
    last_data = None
    breaks: list[int] = []

    def write_summary(at: int, label: str, top: int, bottom: int) -> None:
        cell = sheet.ensure_cell(at, gcol)
        cell.value = label
        cell.formula = None
        cell.bold = True
        for c in scols:
            col = col_name(c)
            _set_formula(sheet, at, c, f"SUBTOTAL({fn},{col}{top + 1}:{col}{bottom + 1})", True)

    grand_at = None
    if not below:
        grand_at = out
        out += 1
    for key, rows in groups:
        label = safe_tr("{0} 汇总").format("" if key is None else key)
        if not below:
            summary_at = out
            out += 1
        start = out
        for r in rows:
            for c, cell in row_cells[r].items():
                sheet.cells[(out, c)] = cell
            out += 1
        end = out - 1
        first_data = start if first_data is None else first_data
        last_data = end
        if below:
            summary_at = out
            out += 1
        write_summary(summary_at, label, start, end)
        if cfg.get("page_break"):
            breaks.append(summary_at + 1)
    if grand_at is None:
        grand_at = out
        out += 1
    write_summary(grand_at, safe_tr("总计"), first_data or r1 + 1, last_data or r1 + 1)
    if breaks:
        breaks = breaks[:-1]  # no break after the last group
        sheet.view_state.row_breaks = sorted(set(sheet.view_state.row_breaks) | set(breaks))
    new_rect = (r1, c1, out - 1, c2)
    sheet.extra["subtotals"] = {"rect": new_rect}
    return new_rect


# ------------------------------------------------------------------ consolidate
def consolidate(
    workbook: Any, dest_sheet: Any, dest: tuple[int, int], cfg: dict[str, Any]
) -> Rect | None:
    """Consolidate the referenced source ranges into ``dest`` (top-left cell)."""
    fn_name = str(cfg.get("function") or "SUM").upper()
    agg = AGGREGATES.get(fn_name, AGGREGATES["SUM"])
    top, left = bool(cfg.get("top_row")), bool(cfg.get("left_column"))
    sources: list[tuple[Any, Rect]] = []
    for ref in cfg.get("references", []):
        resolved = resolve_range(ref, workbook, dest_sheet)
        if resolved is not None:
            sources.append(resolved)
    if not sources:
        return None
    dr, dc = dest

    if not top and not left:
        rows = max(r2 - r1 + 1 for _, (r1, _c1, r2, _c2) in sources)
        cols = max(c2 - c1 + 1 for _, (_r1, c1, _r2, c2) in sources)
        for i in range(rows):
            for j in range(cols):
                vals = [
                    sh.get_cell_value(r1 + i, c1 + j)
                    for sh, (r1, c1, r2, c2) in sources
                    if r1 + i <= r2 and c1 + j <= c2
                ]
                if cfg.get("create_links"):
                    refs = ",".join(
                        f"{_sheet_prefix(sh)}{cell_name(r1 + i, c1 + j, True, True)}"
                        for sh, (r1, c1, r2, c2) in sources
                        if r1 + i <= r2 and c1 + j <= c2
                    )
                    _set_formula(dest_sheet, dr + i, dc + j, f"{fn_name}({refs})")
                else:
                    _set_value(dest_sheet, dr + i, dc + j, _clean(agg(vals)))
        return dr, dc, dr + rows - 1, dc + cols - 1

    # Consolidate by category labels.
    row_keys: list[Any] = []
    col_keys: list[Any] = []
    buckets: dict[tuple[Any, Any], list[Any]] = {}
    for sh, (r1, c1, r2, c2) in sources:
        data_r = r1 + 1 if top else r1
        data_c = c1 + 1 if left else c1
        for r in range(data_r, r2 + 1):
            rk = sh.get_cell_value(r, c1) if left else r - data_r
            if rk not in row_keys:
                row_keys.append(rk)
            for c in range(data_c, c2 + 1):
                ck = sh.get_cell_value(r1, c) if top else c - data_c
                if ck not in col_keys:
                    col_keys.append(ck)
                buckets.setdefault((rk, ck), []).append(sh.get_cell_value(r, c))
    off_r = 1 if top else 0
    off_c = 1 if left else 0
    if top:
        for j, ck in enumerate(col_keys):
            _set_value(dest_sheet, dr, dc + off_c + j, ck)
    if left:
        for i, rk in enumerate(row_keys):
            _set_value(dest_sheet, dr + off_r + i, dc, rk)
    for i, rk in enumerate(row_keys):
        for j, ck in enumerate(col_keys):
            vals = buckets.get((rk, ck), [])
            if vals:
                _set_value(dest_sheet, dr + off_r + i, dc + off_c + j, _clean(agg(vals)))
    return dr, dc, dr + off_r + len(row_keys) - 1, dc + off_c + len(col_keys) - 1


def _sheet_prefix(sheet: Any) -> str:
    name = getattr(sheet, "name", "Sheet1")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", name):
        return f"{name}!"
    return "'" + name.replace("'", "''") + "'!"


# ------------------------------------------------------------------ advanced filter
_OP_RE = re.compile(r"^(>=|<=|<>|=|>|<)(.*)$", re.S)


def criterion_matches(value: Any, crit: Any) -> bool:
    """Evaluate one Excel criteria-range cell against a list value."""
    if crit is None or crit == "":
        return True
    text = str(crit).strip()
    m = _OP_RE.match(text)
    op, operand = (m.group(1), m.group(2).strip()) if m else ("", text)
    vnum, onum = _num(value), _num(operand)
    if op in (">", "<", ">=", "<="):
        if vnum is None or onum is None:
            a, b = str(value or "").lower(), operand.lower()
        else:
            a, b = vnum, onum
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]
    if op in ("=", "<>"):
        if operand == "":
            equal = value in (None, "")
        elif vnum is not None and onum is not None:
            equal = vnum == onum
        else:
            equal = fnmatch.fnmatchcase(str(value or "").lower(), operand.lower())
        return equal if op == "=" else not equal
    # Bare criterion: numbers compare equal, text matches "begins with".
    if onum is not None and vnum is not None:
        return vnum == onum
    pattern = operand.lower()
    if not any(ch in pattern for ch in "*?"):
        pattern += "*"
    return fnmatch.fnmatchcase(str(value if value is not None else "").lower(), pattern)


def filter_matching_rows(
    list_sheet: Any, list_rect: Rect, crit_sheet: Any, crit_rect: Rect
) -> list[int]:
    """Return list rows (absolute, excluding header) that satisfy the criteria range."""
    lr1, lc1, lr2, lc2 = list_rect
    cr1, cc1, cr2, cc2 = crit_rect
    headers = {
        str(list_sheet.get_cell_value(lr1, c) or "").strip().lower(): c
        for c in range(lc1, lc2 + 1)
    }
    conditions: list[list[tuple[int, Any]]] = []
    for r in range(cr1 + 1, cr2 + 1):
        row: list[tuple[int, Any]] = []
        for c in range(cc1, cc2 + 1):
            head = str(crit_sheet.get_cell_value(cr1, c) or "").strip().lower()
            crit = crit_sheet.get_cell_value(r, c)
            if head in headers and crit not in (None, ""):
                row.append((headers[head], crit))
        conditions.append(row)
    if not conditions or all(not row for row in conditions):
        conditions = [[]]  # an empty criteria row matches everything
    matches = []
    for r in range(lr1 + 1, lr2 + 1):
        if any(
            all(criterion_matches(list_sheet.get_cell_value(r, c), crit) for c, crit in row)
            for row in conditions
        ):
            matches.append(r)
    return matches


def advanced_filter(workbook: Any, sheet: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Run Data > Filter > Advanced Filter. Returns a summary dict."""
    lst = resolve_range(params.get("list_range", ""), workbook, sheet)
    crit = resolve_range(params.get("criteria_range", ""), workbook, sheet)
    if lst is None or crit is None:
        raise ValueError(safe_tr("列表区域或条件区域无效。"))
    list_sheet, list_rect = lst
    crit_sheet, crit_rect = crit
    rows = filter_matching_rows(list_sheet, list_rect, crit_sheet, crit_rect)
    lr1, lc1, lr2, lc2 = list_rect
    if params.get("unique_only"):
        seen: set[tuple[Any, ...]] = set()
        unique = []
        for r in rows:
            key = tuple(list_sheet.get_cell_value(r, c) for c in range(lc1, lc2 + 1))
            if key not in seen:
                seen.add(key)
                unique.append(r)
        rows = unique

    if params.get("action") == "copy_to":
        dest = resolve_range(params.get("copy_to", ""), workbook, sheet)
        if dest is None:
            raise ValueError(safe_tr("复制到的目标区域无效。"))
        dsheet, (dr, dc, _, _) = dest
        for j, c in enumerate(range(lc1, lc2 + 1)):
            src = list_sheet.get_cell(lr1, c)
            dsheet.set_cell(dr, dc + j, src.clone() if src else CellData())
        for i, r in enumerate(rows, start=1):
            for j, c in enumerate(range(lc1, lc2 + 1)):
                src = list_sheet.get_cell(r, c)
                if src is not None:
                    clone = src.clone()
                    if clone.formula:
                        clone.formula = None  # Excel copies the displayed values
                    dsheet.set_cell(dr + i, dc + j, clone)
                else:
                    dsheet.cells.pop((dr + i, dc + j), None)
        return {"matched": len(rows), "copied_to": (dr, dc)}

    hidden = list_sheet.geometry.hidden_rows
    previous = sorted(r for r in hidden if lr1 < r <= lr2)
    list_sheet.extra["advanced_filter"] = {"rect": list_rect, "previous_hidden": previous}
    keep = set(rows)
    for r in range(lr1 + 1, lr2 + 1):
        if r in keep:
            hidden.discard(r)
        else:
            hidden.add(r)
    list_sheet.dirty = True
    return {"matched": len(rows), "hidden": (lr2 - lr1) - len(rows)}


def show_all_after_filter(sheet: Any) -> bool:
    """Undo an in-place advanced filter (Data > Filter > Show All)."""
    info = sheet.extra.pop("advanced_filter", None)
    if not info:
        return False
    r1, _c1, r2, _c2 = info["rect"]
    for r in range(r1 + 1, r2 + 1):
        sheet.geometry.hidden_rows.discard(r)
    sheet.geometry.hidden_rows.update(info.get("previous_hidden", []))
    return True


# ------------------------------------------------------------------ data table
def _single_cell(ref: str, workbook: Any, sheet: Any) -> tuple[Any, int, int] | None:
    if not ref:
        return None
    resolved = resolve_range(ref, workbook, sheet)
    if resolved is None:
        raise ValueError(safe_tr("输入单元格引用无效：{0}").format(ref))
    sh, (r1, c1, r2, c2) = resolved
    if (r1, c1) != (r2, c2):
        raise ValueError(safe_tr("输入单元格必须是单个单元格：{0}").format(ref))
    return sh, r1, c1


def _evaluate_cell(sheet: Any, r: int, c: int) -> Any:
    cell = sheet.get_cell(r, c)
    if cell is None:
        return None
    return cell.value


def compute_data_table(
    workbook: Any, sheet: Any, rect: Rect, row_input: str = "", col_input: str = ""
) -> int:
    """Fill a What-If Data Table by substituting inputs and recalculating the DAG.

    Layouts follow Excel:
      * two inputs — formula in the top-left corner, row values across the first row,
        column values down the first column;
      * column input only — input values down the first column, formulas across the
        first row (from the second column);
      * row input only — input values across the first row, formulas down the first
        column (from the second row).
    Returns the number of result cells written.
    """
    r1, c1, r2, c2 = rect
    if r2 <= r1 and c2 <= c1:
        raise ValueError(safe_tr("请选择包含输入值和公式的区域。"))
    if (r2 - r1) * (c2 - c1) > MAX_DATA_TABLE_CELLS:
        raise ValueError(safe_tr("模拟运算表过大（最多 {0} 个结果单元格）。").format(
            MAX_DATA_TABLE_CELLS))
    wb = ensure_workbook(workbook, sheet)
    row_cell = _single_cell(row_input, wb, sheet)
    col_cell = _single_cell(col_input, wb, sheet)
    if row_cell is None and col_cell is None:
        raise ValueError(safe_tr("必须指定行输入单元格或列输入单元格。"))

    inputs = [x for x in (row_cell, col_cell) if x is not None]
    saved = {(id(sh), r, c): (sh, sh.get_cell(r, c).clone() if sh.get_cell(r, c) else None)
             for sh, r, c in inputs}

    def substitute(target: tuple[Any, int, int] | None, value: Any) -> None:
        if target is None:
            return
        sh, r, c = target
        _set_value(sh, r, c, value)

    jobs: list[tuple[int, int, tuple[int, int], list[tuple[Any, Any]]]] = []
    if row_cell is not None and col_cell is not None:
        for r in range(r1 + 1, r2 + 1):
            for c in range(c1 + 1, c2 + 1):
                jobs.append((r, c, (r1, c1), [
                    (row_cell, sheet.get_cell_value(r1, c)),
                    (col_cell, sheet.get_cell_value(r, c1)),
                ]))
    elif col_cell is not None:
        for r in range(r1 + 1, r2 + 1):
            for c in range(c1 + 1, c2 + 1):
                jobs.append((r, c, (r1, c), [(col_cell, sheet.get_cell_value(r, c1))]))
    else:
        for r in range(r1 + 1, r2 + 1):
            for c in range(c1 + 1, c2 + 1):
                jobs.append((r, c, (r, c1), [(row_cell, sheet.get_cell_value(r1, c))]))

    results: dict[tuple[int, int], Any] = {}
    try:
        for r, c, (fr, fc), subs in jobs:
            for target, value in subs:
                substitute(target, value)
            wb.recalculate()
            results[(r, c)] = _evaluate_cell(sheet, fr, fc)
    finally:
        for (_, rr, cc), (sh, original) in saved.items():
            if original is None:
                sh.cells.pop((rr, cc), None)
            else:
                sh.set_cell(rr, cc, original)
        wb.recalculate()
    for (r, c), value in results.items():
        _set_value(sheet, r, c, value)
    tables = sheet.extra.setdefault("data_tables", [])
    tables.append({"rect": rect, "row_input": row_input, "col_input": col_input})
    return len(results)


# ------------------------------------------------------------------ scenarios
def _parse_value(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    n = _num(text)
    if n is None:
        return text
    return _clean(n)


def _cells_of(refs: Iterable[str], workbook: Any, sheet: Any) -> list[tuple[str, Any, int, int]]:
    out = []
    for ref in refs:
        resolved = resolve_range(ref, workbook, sheet)
        if resolved is None:
            continue
        sh, (r1, c1, r2, c2) = resolved
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                out.append((cell_name(r, c, True, True), sh, r, c))
    return out


def scenario_summary(
    workbook: Any, sheet: Any, scenarios: list[dict[str, Any]], result_refs: str = ""
) -> Any:
    """Create an Excel-style "Scenario Summary" worksheet and return it."""
    if workbook is None or not hasattr(workbook, "add_sheet"):
        raise ValueError(safe_tr("无法创建方案摘要：未找到工作簿。"))
    changing: list[str] = []
    for sc in scenarios:
        for ref in sc.get("values", {}):
            key = ref.replace("$", "").upper()
            if key not in [c.replace("$", "").upper() for c in changing]:
                changing.append(ref)
    change_cells = _cells_of(changing, workbook, sheet)
    result_cells = _cells_of(
        [p.strip() for p in re.split(r"[,;]", result_refs or "") if p.strip()], workbook, sheet
    )

    saved = {(id(sh), r, c): (sh, r, c, sh.get_cell(r, c).clone() if sh.get_cell(r, c) else None)
             for _, sh, r, c in change_cells}

    def read(cells: list[tuple[str, Any, int, int]]) -> list[Any]:
        return [sh.get_cell_value(r, c) for _, sh, r, c in cells]

    current_changing = read(change_cells)
    current_results = read(result_cells)
    columns: list[tuple[list[Any], list[Any]]] = []
    try:
        for sc in scenarios:
            values = {k.replace("$", "").upper(): v for k, v in sc.get("values", {}).items()}
            for name, sh, r, c in change_cells:
                key = name.replace("$", "").upper()
                if key in values:
                    _set_value(sh, r, c, _parse_value(values[key]))
            workbook.recalculate()
            columns.append((read(change_cells), read(result_cells)))
            for _, (sh, r, c, original) in saved.items():
                if original is None:
                    sh.cells.pop((r, c), None)
                else:
                    sh.set_cell(r, c, original.clone())
    finally:
        for _, (sh, r, c, original) in saved.items():
            if original is None:
                sh.cells.pop((r, c), None)
            else:
                sh.set_cell(r, c, original)
        workbook.recalculate()

    base = safe_tr("方案摘要")
    name, n = base, 1
    existing = {s.name.lower() for s in workbook.sheets}
    while name.lower() in existing:
        n += 1
        name = f"{base} {n}"
    out = workbook.add_sheet(name=name)

    def put(r: int, c: int, v: Any, bold: bool = False, fill: str | None = None) -> None:
        cell = out.ensure_cell(r, c)
        cell.value = v
        cell.bold = bold or cell.bold
        if fill:
            cell.bg_color = fill
            cell.pattern = "solid"

    head_fill = "#C0C0C0"
    put(0, 1, safe_tr("方案摘要"), bold=True, fill=head_fill)
    put(1, 2, safe_tr("当前值:"), bold=True, fill=head_fill)
    for j, sc in enumerate(scenarios):
        put(1, 3 + j, sc.get("name", ""), bold=True, fill=head_fill)
    put(2, 1, safe_tr("可变单元格:"), bold=True)
    row = 3
    for i, (ref, *_rest) in enumerate(change_cells):
        put(row, 1, ref)
        put(row, 2, current_changing[i])
        for j, (vals, _res) in enumerate(columns):
            put(row, 3 + j, vals[i])
        row += 1
    if result_cells:
        put(row, 1, safe_tr("结果单元格:"), bold=True)
        row += 1
        for i, (ref, *_rest) in enumerate(result_cells):
            put(row, 1, ref)
            put(row, 2, current_results[i])
            for j, (_vals, res) in enumerate(columns):
                put(row, 3 + j, res[i])
            row += 1
    row += 1
    put(row, 1, safe_tr("注释：“当前值”这一列表示的是在建立方案汇总时，可变单元格的值。"))
    put(row + 1, 1, safe_tr("每组方案的可变单元格均以灰色底纹突出显示。"))
    return out


# ------------------------------------------------------------------ text to columns
def split_fixed_width(line: str, breaks: Iterable[int]) -> list[str]:
    """Split ``line`` at the character positions in ``breaks`` (Excel fixed width)."""
    cuts = sorted({b for b in breaks if 0 < b < len(line)})
    parts, start = [], 0
    for b in cuts:
        parts.append(line[start:b].strip())
        start = b
    parts.append(line[start:].strip())
    return parts


def suggest_fixed_breaks(lines: list[str]) -> list[int]:
    """Guess column breaks: positions where every sample line has a space after text."""
    sample = [ln for ln in lines if ln.strip()][:50]
    if not sample:
        return []
    width = max(len(ln) for ln in sample)
    padded = [ln.ljust(width) for ln in sample]
    breaks = []
    for pos in range(1, width):
        if all(p[pos - 1] == " " for p in padded) and any(p[pos] != " " for p in padded):
            breaks.append(pos)
    return breaks

