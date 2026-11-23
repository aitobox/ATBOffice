"""Structured table references (``Table1[Col]``, ``[@Col]``, ``Table1[#All]``) and ``@``."""

from __future__ import annotations

from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import REF, VALUE

SPECIALS = {"#all", "#data", "#headers", "#totals", "#this row"}


def _sheets(ctx: EvalContext) -> list[Any]:
    wb = ctx.workbook
    return list(getattr(wb, "sheets", []) or []) if wb is not None else []


def find_table(ctx: EvalContext, name: str | None) -> tuple[Any, Any] | None:
    """(sheet, table) for ``name``; without a name, the table around the current cell."""
    if name is None:
        sheet = None
        if ctx.workbook is not None and hasattr(ctx.workbook, "get_sheet_by_name"):
            sheet = ctx.workbook.get_sheet_by_name(ctx.current_sheet)
        if sheet is not None and hasattr(sheet, "table_at"):
            table = sheet.table_at(ctx.current_row, ctx.current_col)
            if table is not None:
                return sheet, table
        return None
    key = name.lower()
    for sheet in _sheets(ctx):
        for table in getattr(sheet, "tables", []) or []:
            if key in (str(table.name).lower(), str(table.display_name or "").lower()):
                return sheet, table
    return None


def _split_top(text: str) -> list[str]:
    """Split ``[#This Row],[Amount]`` at top-level commas, dropping one level of brackets."""
    items, depth, buf = [], 0, ""
    for ch in text:
        if ch == "[":
            depth += 1
            if depth == 1:
                continue
        elif ch == "]":
            depth -= 1
            if depth == 0:
                continue
        if ch == "," and depth == 0:
            items.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(buf.strip())
    return items


def parse_spec(spec: str) -> tuple[set[str], list[str]]:
    """Specials and column names of a structured reference specifier."""
    body = spec.strip()
    if body.startswith("[") and body.endswith("]"):
        body = body[1:-1]
    specials: set[str] = set()
    columns: list[str] = []
    if body.startswith("@"):
        specials.add("#this row")
        body = body[1:]
    if not body.startswith("[") and body:
        parts = [body]
    else:
        parts = _split_top(body)
    for part in parts:
        if ":" in part and not part.startswith("#"):
            a, _, b = part.partition(":")
            columns.extend([a.strip().strip("[]"), b.strip().strip("[]")])
            columns.append(":")  # marks a column range
            continue
        low = part.lower().strip()
        if low in SPECIALS:
            specials.add(low)
        elif low == "@" or low.startswith("@"):
            specials.add("#this row")
            if part[1:].strip():
                columns.append(part[1:].strip().strip("[]"))
        elif part:
            columns.append(part.replace("'", ""))
    return specials, columns


def _table_box(table: Any) -> tuple[int, int, int, int]:
    from atboffice.modules.spreadsheet.calc.references import parse_range

    if all(isinstance(getattr(table, k, None), int) for k in ("r1", "c1", "r2", "c2")):
        return table.r1, table.c1, table.r2, table.c2
    rng = parse_range(table.ref)
    if not rng:
        raise ValueError(table.ref)
    return rng["r1"], rng["c1"], rng["r2"], rng["c2"]


def resolve(node: Any, ctx: EvalContext) -> Any:
    """Evaluate a StructuredRefNode to a Ref (or a single value / error)."""
    found = find_table(ctx, node.table)
    if found is None:
        return REF
    sheet, table = found
    try:
        r1, c1, r2, c2 = _table_box(table)
    except ValueError:
        return REF
    hdr = int(getattr(table, "header_row_count", 1) or 0)
    tot = int(getattr(table, "totals_row_count", 0) or 0)
    data_r1, data_r2 = r1 + hdr, r2 - tot
    specials, columns = parse_spec(node.spec)

    names = [str(col.name).lower() for col in getattr(table, "columns", [])]
    if not names and hdr:
        names = [str(ctx.get_cell_value(sheet.name, r1, c)).lower() for c in range(c1, c2 + 1)]
    if ":" in columns:
        a, b = columns[0].lower(), columns[1].lower()
        if a not in names or b not in names:
            return REF
        col_a, col_b = sorted((names.index(a), names.index(b)))
    elif columns:
        col = columns[0].lower()
        if col not in names:
            return REF
        col_a = col_b = names.index(col)
    else:
        col_a, col_b = 0, c2 - c1

    if "#this row" in specials:
        row = ctx.current_row
        if not (data_r1 <= row <= data_r2) or ctx.current_sheet.lower() != sheet.name.lower():
            return VALUE
        rows = (row, row)
    elif "#all" in specials:
        rows = (r1, r2)
    else:
        picks = []
        if "#headers" in specials and hdr:
            picks.append((r1, r1 + hdr - 1))
        if "#data" in specials or not (specials & {"#headers", "#totals"}):
            picks.append((data_r1, data_r2))
        if "#totals" in specials and tot:
            picks.append((r2 - tot + 1, r2))
        if not picks:
            return REF
        rows = (min(p[0] for p in picks), max(p[1] for p in picks))
    if rows[1] < rows[0]:
        return REF
    ref = ctx.create_ref(sheet.name, rows[0], c1 + col_a, rows[1], c1 + col_b)
    if isinstance(ref, Ref) and ref.single:
        return ctx.get_cell_value(sheet.name, ref.r1, ref.c1)
    return ref


def implicit_intersection(value: Any, ctx: EvalContext) -> Any:
    """``@``: a single value from a range (same row / column as the formula) or array."""
    if isinstance(value, Arr):
        return value.data[0][0] if value.data and value.data[0] else VALUE
    if not isinstance(value, Ref):
        return value
    if value.single:
        return value.cell_value(value.r1, value.c1)
    if value.cols == 1 and value.r1 <= ctx.current_row <= value.r2:
        return value.cell_value(ctx.current_row, value.c1)
    if value.rows == 1 and value.c1 <= ctx.current_col <= value.c2:
        return value.cell_value(value.r1, ctx.current_col)
    return VALUE
