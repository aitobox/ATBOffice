"""Multi-dimensional PivotTable calculation engine for ATBOffice Ledger.

Supports:
- Multi-field Report Filters, Column Labels, Row Labels, and Values zones
- Aggregations: SUM, COUNT, AVERAGE, MAX, MIN, PRODUCT, COUNTNUMS
- Automatic nested subtotals for multi-level Row Labels and Grand Totals
- Semantic layout metadata (headers, banded rows, subtotals, grand totals, dropdown cells)
- Non-destructive live refresh clearing stale output cells
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.calc.references import col_name
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    FormatDelta,
    SheetDataModel,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

AGG_FUNCTIONS: tuple[str, ...] = (
    "sum",
    "count",
    "average",
    "max",
    "min",
    "product",
    "countNums",
)

AGG_FUNC_LABELS: dict[str, str] = {
    "sum": "Sum",
    "count": "Count",
    "average": "Average",
    "max": "Max",
    "min": "Min",
    "product": "Product",
    "countNums": "Count Nums",
}


def _to_number(val: Any) -> float | None:
    """Convert cell value to float if numeric (excluding booleans)."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def aggregate_values(vals: list[Any], func: str) -> Any:
    """Aggregate a sequence of raw cell values using the given Pivot function."""
    nums: list[float] = []
    for v in vals:
        num = _to_number(v)
        if num is not None:
            nums.append(num)

    match func.lower():
        case "count":
            return len([x for x in vals if x is not None and str(x) != ""])
        case "countnums":
            return len(nums)
        case "average":
            return (sum(nums) / len(nums)) if nums else "#DIV/0!"
        case "max":
            return max(nums) if nums else 0
        case "min":
            return min(nums) if nums else 0
        case "product":
            return math.prod(nums) if nums else 0
        case _:  # default "sum"
            return sum(nums) if nums else 0


def _natural_key_token(token: str) -> tuple[int, Any]:
    """Natural sort key matching Excel/Ledger ordering (numbers, text, blanks last)."""
    if token == "(blank)":
        return (2, "")
    try:
        return (0, float(token))
    except ValueError:
        return (1, token.lower())


def _natural_tuple_key(tup: tuple[str, ...]) -> tuple[tuple[int, Any], ...]:
    return tuple(_natural_key_token(t) for t in tup)


@dataclass
class PivotFieldSpec:
    """Configuration for a field placed in Filters, Rows, or Columns."""

    col_idx: int
    name: str = ""
    selected_values: set[str] | None = None  # None means (All)
    show_subtotal: bool = True
    sort_order: str = "asc"


@dataclass
class PivotValueSpec:
    """Configuration for a field placed in the Values zone."""

    col_idx: int
    name: str = ""
    agg_func: str = "sum"  # sum, count, average, max, min, product, countNums
    caption: str | None = None

    @property
    def display_label(self) -> str:
        if self.caption:
            return self.caption
        fn_label = AGG_FUNC_LABELS.get(self.agg_func, self.agg_func.capitalize())
        return f"{fn_label} of {self.name}"


@dataclass
class PivotLayoutSpec:
    """Complete multi-dimensional layout specification for a PivotTable."""

    source_sheet: str
    source_range: tuple[int, int, int, int]  # (r1, c1, r2, c2)
    filters: list[PivotFieldSpec] = field(default_factory=list)
    columns: list[PivotFieldSpec] = field(default_factory=list)
    rows: list[PivotFieldSpec] = field(default_factory=list)
    values: list[PivotValueSpec] = field(default_factory=list)
    show_subtotals: bool = True
    show_grand_total_rows: bool = True
    show_grand_total_cols: bool = True
    target_sheet: str = "new"
    target_cell: tuple[int, int] = (2, 0)
    name: str = "PivotTable1"


@dataclass
class PivotLayoutMeta:
    """Semantic metadata for rendered PivotTable cells used by GridViewport."""

    filter_rows: set[int] = field(default_factory=set)
    header_rows: set[int] = field(default_factory=set)
    data_rows: list[int] = field(default_factory=list)
    subtotal_rows: set[int] = field(default_factory=set)
    grand_total_rows: set[int] = field(default_factory=set)
    grand_total_cols: set[int] = field(default_factory=set)
    filter_dropdown_cells: dict[tuple[int, int], tuple[str, int]] = field(
        default_factory=dict
    )

    def clear(self) -> None:
        self.filter_rows.clear()
        self.header_rows.clear()
        self.data_rows.clear()
        self.subtotal_rows.clear()
        self.grand_total_rows.clear()
        self.grand_total_cols.clear()
        self.filter_dropdown_cells.clear()


@dataclass
class PivotReport:
    """Live PivotTable instance bound to a target worksheet."""

    name: str
    layout: PivotLayoutSpec
    sheet_name: str
    bbox: tuple[int, int, int, int]  # (r1, c1, r2, c2) inclusive
    meta: PivotLayoutMeta = field(default_factory=PivotLayoutMeta)
    needs_refresh: bool = False

    def contains_cell(self, r: int, c: int) -> bool:
        r1, c1, r2, c2 = self.bbox
        return r1 <= r <= r2 and c1 <= c <= c2


@dataclass
class _PivotRowEntry:
    kind: str  # "data" | "subtotal" | "grand_total"
    labels: list[str]
    key_tuple: tuple[str, ...]
    level: int = -1


@dataclass
class _PivotColSlice:
    col_tuple: tuple[str, ...] | None
    val_idx: int | None
    is_grand_total: bool = False


@dataclass
class PivotGridResult:
    """Pure computed tabular structure before painting into SheetDataModel."""

    col_headers: dict[int, str]
    row_entries: list[_PivotRowEntry]
    col_slices: list[_PivotColSlice]
    sorted_row_tuples: list[tuple[str, ...]]
    sorted_col_tuples: list[tuple[str, ...]]
    cell_vals: dict[tuple[tuple[str, ...], tuple[str, ...], int], list[Any]]
    row_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]]
    col_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]]
    grand_tot_vals: dict[int, list[Any]]
    sub_cell_vals: dict[tuple[tuple[str, ...], tuple[str, ...], int], list[Any]]
    sub_row_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]]


def extract_source_fields(
    workbook: WorkbookModel,
    source_sheet: str,
    source_range: tuple[int, int, int, int],
) -> tuple[list[tuple[int, str]], set[int]]:
    """Return list of (col_idx, header_name) and set of numeric col_idx."""
    src = workbook.get_sheet_by_name(source_sheet)
    if src is None:
        return [], set()

    r1, c1, r2, c2 = source_range
    fields: list[tuple[int, str]] = []
    numeric_cols: set[int] = set()

    for c in range(c1, c2 + 1):
        val = src.get_cell_value(r1, c)
        name = str(val).strip() if val is not None and str(val).strip() else col_name(c)
        fields.append((c, name))

        # Check sample rows for numeric values
        sample_end = min(r2, r1 + 10)
        for r in range(r1 + 1, sample_end + 1):
            sample = src.get_cell_value(r, c)
            if isinstance(sample, (int, float)) and not isinstance(sample, bool):
                numeric_cols.add(c)
                break

    return fields, numeric_cols


def get_unique_field_values(
    workbook: WorkbookModel,
    source_sheet: str,
    source_range: tuple[int, int, int, int],
    col_idx: int,
) -> list[str]:
    """Return naturally sorted unique display values for a column in source_range."""
    src = workbook.get_sheet_by_name(source_sheet)
    if src is None:
        return []

    r1, _, r2, _ = source_range
    seen: set[str] = set()
    for r in range(r1 + 1, r2 + 1):
        val = src.get_cell_value(r, col_idx)
        key = "(blank)" if val is None or str(val).strip() == "" else str(val)
        seen.add(key)

    return sorted(seen, key=_natural_key_token)


class PivotCalculationEngine:
    """Multi-dimensional PivotTable computation and worksheet rendering engine."""

    @staticmethod
    def _resolve_col_headers(
        src_sheet: SheetDataModel,
        r1: int,
        c1: int,
        c2: int,
        layout: PivotLayoutSpec,
    ) -> dict[int, str]:
        headers: dict[int, str] = {}
        for c in range(c1, c2 + 1):
            v = src_sheet.get_cell_value(r1, c)
            headers[c] = str(v).strip() if v is not None and str(v).strip() else col_name(c)

        for spec_list in (layout.filters, layout.columns, layout.rows, layout.values):
            for spec in spec_list:
                if not spec.name and spec.col_idx in headers:
                    spec.name = headers[spec.col_idx]
        return headers

    @staticmethod
    def _key_of(sheet: SheetDataModel, r: int, c: int) -> str:
        val = sheet.get_cell_value(r, c)
        if val is None or str(val).strip() == "":
            return "(blank)"
        return str(val)

    def calculate(
        self, workbook: WorkbookModel, layout: PivotLayoutSpec
    ) -> PivotGridResult:
        """Compute multi-dimensional pivot groupings and raw value buckets."""
        src_sheet = workbook.get_sheet_by_name(layout.source_sheet)
        if src_sheet is None:
            raise ValueError(f"Source worksheet '{layout.source_sheet}' not found.")

        r1, c1, r2, c2 = layout.source_range
        if r2 < r1 or c2 < c1:
            raise ValueError("Source data range is invalid.")

        col_headers = self._resolve_col_headers(src_sheet, r1, c1, c2, layout)

        row_tuples_seen: set[tuple[str, ...]] = set()
        col_tuples_seen: set[tuple[str, ...]] = set()
        row_tuples: list[tuple[str, ...]] = []
        col_tuples: list[tuple[str, ...]] = []

        cell_vals: dict[tuple[tuple[str, ...], tuple[str, ...], int], list[Any]] = {}
        row_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]] = {}
        col_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]] = {}
        grand_tot_vals: dict[int, list[Any]] = {}
        sub_cell_vals: dict[tuple[tuple[str, ...], tuple[str, ...], int], list[Any]] = {}
        sub_row_tot_vals: dict[tuple[tuple[str, ...], int], list[Any]] = {}

        filter_fields = list(layout.filters) + [
            f for f in layout.rows if f.selected_values is not None
        ] + [
            f for f in layout.columns if f.selected_values is not None
        ]

        for r in range(r1 + 1, r2 + 1):
            # Apply filters (Report Filters + Row/Col active filters)
            skip = False
            for ff in filter_fields:
                if ff.selected_values is not None:
                    k = self._key_of(src_sheet, r, ff.col_idx)
                    if k not in ff.selected_values:
                        skip = True
                        break
            if skip:
                continue

            rk = tuple(self._key_of(src_sheet, r, rf.col_idx) for rf in layout.rows)
            ck = tuple(self._key_of(src_sheet, r, cf.col_idx) for cf in layout.columns)

            if layout.rows and rk not in row_tuples_seen:
                row_tuples_seen.add(rk)
                row_tuples.append(rk)
            if layout.columns and ck not in col_tuples_seen:
                col_tuples_seen.add(ck)
                col_tuples.append(ck)

            for vi, vf in enumerate(layout.values):
                val = src_sheet.get_cell_value(r, vf.col_idx)
                cell_vals.setdefault((rk, ck, vi), []).append(val)
                row_tot_vals.setdefault((rk, vi), []).append(val)
                col_tot_vals.setdefault((ck, vi), []).append(val)
                grand_tot_vals.setdefault(vi, []).append(val)

                # Accumulate subtotal buckets for outer row levels
                for prefix_len in range(1, len(layout.rows)):
                    prefix = rk[:prefix_len]
                    sub_cell_vals.setdefault((prefix, ck, vi), []).append(val)
                    sub_row_tot_vals.setdefault((prefix, vi), []).append(val)

        # Sort row tuples & col tuples naturally
        sorted_row_tuples = sorted(row_tuples, key=_natural_tuple_key)
        sorted_col_tuples = sorted(col_tuples, key=_natural_tuple_key)

        # Build row entries (with multi-level subtotals + grand total)
        row_entries: list[_PivotRowEntry] = []
        n_row_fields = len(layout.rows)
        n_row_cols = max(1, n_row_fields)

        if n_row_fields == 0:
            if layout.values:
                row_entries.append(
                    _PivotRowEntry(
                        kind="grand_total" if layout.show_grand_total_rows else "data",
                        labels=["Grand Total" if layout.show_grand_total_rows else "Total"],
                        key_tuple=(),
                    )
                )
        else:
            prev_rk: tuple[str, ...] | None = None
            for idx, rk in enumerate(sorted_row_tuples):
                # Emit data row with suppressed repeated outer labels
                labels = [""] * n_row_cols
                for lvl in range(n_row_fields):
                    if prev_rk is None or rk[: lvl + 1] != prev_rk[: lvl + 1]:
                        labels[lvl] = rk[lvl]
                    elif lvl == n_row_fields - 1:
                        labels[lvl] = rk[lvl]

                row_entries.append(
                    _PivotRowEntry(kind="data", labels=labels, key_tuple=rk)
                )

                # Determine which outer prefix levels end after this row
                next_rk = (
                    sorted_row_tuples[idx + 1]
                    if idx + 1 < len(sorted_row_tuples)
                    else None
                )
                if layout.show_subtotals and n_row_fields >= 2:
                    for lvl in range(n_row_fields - 2, -1, -1):
                        if not layout.rows[lvl].show_subtotal:
                            continue
                        prefix = rk[: lvl + 1]
                        if next_rk is None or next_rk[: lvl + 1] != prefix:
                            sub_labels = [""] * n_row_cols
                            sub_labels[lvl] = f"{prefix[-1]} Total"
                            row_entries.append(
                                _PivotRowEntry(
                                    kind="subtotal",
                                    labels=sub_labels,
                                    key_tuple=prefix,
                                    level=lvl,
                                )
                            )
                prev_rk = rk

            if layout.show_grand_total_rows and (sorted_row_tuples or layout.values):
                gt_labels = [""] * n_row_cols
                gt_labels[0] = "Grand Total"
                row_entries.append(
                    _PivotRowEntry(kind="grand_total", labels=gt_labels, key_tuple=())
                )

        # Build column slices
        col_slices: list[_PivotColSlice] = []
        n_vals = len(layout.values)
        val_indices: list[int | None] = list(range(n_vals)) if n_vals > 0 else [None]

        if not layout.columns:
            for vi in val_indices:
                col_slices.append(_PivotColSlice(col_tuple=(), val_idx=vi, is_grand_total=False))
        else:
            for ct in sorted_col_tuples:
                for vi in val_indices:
                    col_slices.append(
                        _PivotColSlice(col_tuple=ct, val_idx=vi, is_grand_total=False)
                    )
            if layout.show_grand_total_cols and n_vals > 0:
                for vi in val_indices:
                    col_slices.append(
                        _PivotColSlice(col_tuple=None, val_idx=vi, is_grand_total=True)
                    )

        return PivotGridResult(
            col_headers=col_headers,
            row_entries=row_entries,
            col_slices=col_slices,
            sorted_row_tuples=sorted_row_tuples,
            sorted_col_tuples=sorted_col_tuples,
            cell_vals=cell_vals,
            row_tot_vals=row_tot_vals,
            col_tot_vals=col_tot_vals,
            grand_tot_vals=grand_tot_vals,
            sub_cell_vals=sub_cell_vals,
            sub_row_tot_vals=sub_row_tot_vals,
        )

    @staticmethod
    def _filter_display_text(ff: PivotFieldSpec) -> str:
        if ff.selected_values is None:
            return "(All)"
        if len(ff.selected_values) == 0:
            return "(None)"
        if len(ff.selected_values) == 1:
            return next(iter(ff.selected_values))
        return "(Multiple Items)"

    def render_report(
        self,
        workbook: WorkbookModel,
        layout: PivotLayoutSpec,
        existing_report: PivotReport | None = None,
    ) -> PivotReport:
        """Calculate and write PivotTable cells and semantic metadata onto target sheet."""
        res = self.calculate(workbook, layout)

        # Resolve destination sheet & anchor cell
        if existing_report is not None:
            dst_sheet = workbook.get_sheet_by_name(existing_report.sheet_name)
            if dst_sheet is None:
                dst_sheet = workbook.add_sheet(name=existing_report.sheet_name)
            r0, c0 = existing_report.layout.target_cell
            # Clear previous pivot output cells cleanly
            old_r1, old_c1, old_r2, old_c2 = existing_report.bbox
            for rr in range(old_r1, old_r2 + 1):
                for cc in range(old_c1, old_c2 + 1):
                    dst_sheet.cells.pop((rr, cc), None)
        else:
            if layout.target_sheet == "new":
                dst_sheet = workbook.add_sheet()
                r0, c0 = 2, 0
                workbook.set_active_sheet(dst_sheet)
            else:
                dst_sheet = workbook.get_sheet_by_name(layout.target_sheet)
                if dst_sheet is None:
                    dst_sheet = workbook.add_sheet(name=layout.target_sheet)
                r0, c0 = layout.target_cell

        layout.target_sheet = dst_sheet.name
        layout.target_cell = (r0, c0)

        meta = PivotLayoutMeta()

        # Cell styles
        fmt_bold = FormatDelta(bold=True)
        fmt_filter_val = FormatDelta(
            bg_color="#FFFFFF",
            border_top=BorderStyle(style="thin", color="#9EB6CE"),
            border_bottom=BorderStyle(style="thin", color="#9EB6CE"),
            border_left=BorderStyle(style="thin", color="#9EB6CE"),
            border_right=BorderStyle(style="thin", color="#9EB6CE"),
        )
        fmt_head = FormatDelta(
            bold=True,
            bg_color="#DCE6F2",
            border_top=BorderStyle(style="thin", color="#9EB6CE"),
            border_bottom=BorderStyle(style="thin", color="#9EB6CE"),
        )
        fmt_band_even = FormatDelta(bg_color="#FFFFFF")
        fmt_band_odd = FormatDelta(bg_color="#F4F7FC")
        fmt_subtotal = FormatDelta(
            bold=True,
            bg_color="#E9EDF4",
            border_top=BorderStyle(style="thin", color="#8EA9DB"),
            border_bottom=BorderStyle(style="thin", color="#8EA9DB"),
        )
        fmt_grand_total = FormatDelta(
            bold=True,
            bg_color="#D9E1F2",
            border_top=BorderStyle(style="thin", color="#4F81BD"),
            border_bottom=BorderStyle(style="double", color="#4F81BD"),
        )

        def put(r: int, c: int, v: Any, fmt: FormatDelta | None = None) -> None:
            cell = CellData(value=v)
            dst_sheet.set_cell(r, c, cell)
            if fmt is not None:
                dst_sheet.apply_format_delta(r, c, fmt)

        curr_r = r0

        # 1. Report Filter rows
        if layout.filters:
            for ff in layout.filters:
                fname = ff.name or res.col_headers.get(ff.col_idx, col_name(ff.col_idx))
                put(curr_r, c0, fname, fmt_bold)
                put(curr_r, c0 + 1, self._filter_display_text(ff), fmt_filter_val)
                meta.filter_rows.add(curr_r)
                meta.filter_dropdown_cells[(curr_r, c0 + 1)] = ("filter", ff.col_idx)
                curr_r += 1
            curr_r += 1  # blank row between filters and pivot table body

        n_row_cols = max(1, len(layout.rows))
        n_col_fields = len(layout.columns)
        n_vals = len(layout.values)
        n_slices = max(1, len(res.col_slices))

        # 2. Header Rows
        # Title / top row
        top_title = (
            layout.values[0].display_label
            if n_vals == 1
            else ("Values" if n_vals > 1 else layout.name)
        )
        put(curr_r, c0, top_title, fmt_head)
        for offset in range(1, n_row_cols):
            put(curr_r, c0 + offset, "", fmt_head)

        if n_col_fields > 0:
            col_top_name = layout.columns[0].name or res.col_headers.get(
                layout.columns[0].col_idx, col_name(layout.columns[0].col_idx)
            )
            put(curr_r, c0 + n_row_cols, col_top_name, fmt_head)
            meta.filter_dropdown_cells[(curr_r, c0 + n_row_cols)] = (
                "col",
                layout.columns[0].col_idx,
            )
            for j in range(1, n_slices):
                put(curr_r, c0 + n_row_cols + j, "", fmt_head)
        else:
            for j in range(n_slices):
                put(curr_r, c0 + n_row_cols + j, "", fmt_head)
        meta.header_rows.add(curr_r)
        curr_r += 1

        # Intermediate column dimension rows (if >= 2 column fields)
        if n_col_fields >= 2:
            for c_lvl in range(n_col_fields - 1):
                for rc in range(n_row_cols):
                    put(curr_r, c0 + rc, "", fmt_head)
                prev_ct_prefix: tuple[str, ...] | None = None
                for j, sl in enumerate(res.col_slices):
                    if sl.is_grand_total or sl.col_tuple is None:
                        is_first_gt = j == 0 or not res.col_slices[j - 1].is_grand_total
                        lbl = "Grand Total" if is_first_gt else ""
                    else:
                        prefix = sl.col_tuple[: c_lvl + 1]
                        lbl = sl.col_tuple[c_lvl] if prefix != prev_ct_prefix else ""
                        prev_ct_prefix = prefix
                    put(curr_r, c0 + n_row_cols + j, lbl, fmt_head)
                meta.header_rows.add(curr_r)
                curr_r += 1

        # If multi-col AND multi-value, add a column-values header row above individual value labels
        if n_col_fields >= 1 and n_vals > 1:
            for rc in range(n_row_cols):
                put(curr_r, c0 + rc, "", fmt_head)
            prev_ct: tuple[str, ...] | None = None
            for j, sl in enumerate(res.col_slices):
                if sl.is_grand_total or sl.col_tuple is None:
                    is_first_gt = j == 0 or not res.col_slices[j - 1].is_grand_total
                    lbl = "Grand Total" if is_first_gt else ""
                else:
                    lbl = sl.col_tuple[-1] if sl.col_tuple != prev_ct else ""
                    prev_ct = sl.col_tuple
                put(curr_r, c0 + n_row_cols + j, lbl, fmt_head)
            meta.header_rows.add(curr_r)
            curr_r += 1

        # Bottom field header row (row field headers + leaf col headers)
        if layout.rows:
            for rc, rf in enumerate(layout.rows):
                rname = rf.name or res.col_headers.get(rf.col_idx, col_name(rf.col_idx))
                put(curr_r, c0 + rc, rname, fmt_head)
                meta.filter_dropdown_cells[(curr_r, c0 + rc)] = ("row", rf.col_idx)
        else:
            put(curr_r, c0, "", fmt_head)

        for j, sl in enumerate(res.col_slices):
            if n_col_fields == 0:
                if sl.val_idx is not None and n_vals > 1:
                    col_lbl = layout.values[sl.val_idx].display_label
                elif sl.val_idx is not None and n_vals == 1:
                    col_lbl = "Total"
                else:
                    col_lbl = "Total"
            elif sl.is_grand_total:
                meta.grand_total_cols.add(c0 + n_row_cols + j)
                if n_vals > 1 and sl.val_idx is not None:
                    col_lbl = f"Total {layout.values[sl.val_idx].display_label}"
                else:
                    col_lbl = "Grand Total"
            else:
                if n_vals > 1 and sl.val_idx is not None:
                    col_lbl = layout.values[sl.val_idx].display_label
                elif sl.col_tuple:
                    col_lbl = sl.col_tuple[-1]
                else:
                    col_lbl = "Total"
            put(curr_r, c0 + n_row_cols + j, col_lbl, fmt_head)

        meta.header_rows.add(curr_r)
        curr_r += 1

        # 3. Data, Subtotal & Grand Total Rows
        data_band_idx = 0
        for entry in res.row_entries:
            if entry.kind == "subtotal":
                row_fmt = fmt_subtotal
                meta.subtotal_rows.add(curr_r)
            elif entry.kind == "grand_total":
                row_fmt = fmt_grand_total
                meta.grand_total_rows.add(curr_r)
            else:
                row_fmt = fmt_band_odd if (data_band_idx % 2 == 1) else fmt_band_even
                meta.data_rows.append(curr_r)
                data_band_idx += 1

            # Row labels
            for rc, lbl in enumerate(entry.labels):
                put(curr_r, c0 + rc, lbl, row_fmt)

            # Data cells
            for j, sl in enumerate(res.col_slices):
                col_pos = c0 + n_row_cols + j
                cell_fmt = row_fmt
                if sl.is_grand_total and entry.kind == "data":
                    cell_fmt = fmt_bold

                if sl.val_idx is None:
                    put(curr_r, col_pos, None, cell_fmt)
                    continue

                vf = layout.values[sl.val_idx]
                vals_bucket: list[Any] | None = None

                if entry.kind == "grand_total":
                    if sl.is_grand_total or not layout.columns:
                        vals_bucket = res.grand_tot_vals.get(sl.val_idx, [])
                    elif sl.col_tuple is not None:
                        vals_bucket = res.col_tot_vals.get((sl.col_tuple, sl.val_idx), [])
                elif entry.kind == "subtotal":
                    if sl.is_grand_total or not layout.columns:
                        vals_bucket = res.sub_row_tot_vals.get((entry.key_tuple, sl.val_idx), [])
                    elif sl.col_tuple is not None:
                        vals_bucket = res.sub_cell_vals.get(
                            (entry.key_tuple, sl.col_tuple, sl.val_idx), []
                        )
                else:  # "data"
                    if sl.is_grand_total:
                        vals_bucket = res.row_tot_vals.get((entry.key_tuple, sl.val_idx), [])
                    elif sl.col_tuple is not None:
                        vals_bucket = res.cell_vals.get(
                            (entry.key_tuple, sl.col_tuple, sl.val_idx), []
                        )

                if vals_bucket:
                    agg_val = aggregate_values(vals_bucket, vf.agg_func)
                    put(curr_r, col_pos, agg_val, cell_fmt)
                else:
                    # Leave empty intersection blank (preserve row formatting)
                    put(curr_r, col_pos, None, cell_fmt)

            curr_r += 1

        end_r = max(r0, curr_r - 1)
        end_c = c0 + n_row_cols + n_slices - 1
        if layout.filters:
            end_c = max(end_c, c0 + 1)

        bbox = (r0, c0, end_r, end_c)

        if existing_report is not None:
            existing_report.name = layout.name
            existing_report.layout = layout
            existing_report.sheet_name = dst_sheet.name
            existing_report.bbox = bbox
            existing_report.meta = meta
            existing_report.needs_refresh = False
            if existing_report not in dst_sheet.pivot_reports:
                dst_sheet.pivot_reports.append(existing_report)
            return existing_report

        report = PivotReport(
            name=layout.name,
            layout=layout,
            sheet_name=dst_sheet.name,
            bbox=bbox,
            meta=meta,
            needs_refresh=False,
        )
        dst_sheet.pivot_reports.append(report)
        return report

    def refresh_report(self, workbook: WorkbookModel, report: PivotReport) -> bool:
        """Recalculate and re-render an existing PivotReport in place."""
        src_sheet = workbook.get_sheet_by_name(report.layout.source_sheet)
        if src_sheet is None:
            return False
        self.render_report(workbook, report.layout, existing_report=report)
        return True


def calculate_pivot(
    workbook: WorkbookModel, layout: PivotLayoutSpec
) -> PivotGridResult:
    """Compute a PivotGridResult without writing to worksheet."""
    return PivotCalculationEngine().calculate(workbook, layout)


def build_interactive_pivot(
    workbook: WorkbookModel,
    layout: PivotLayoutSpec,
    existing_report: PivotReport | None = None,
) -> PivotReport:
    """Build or update an interactive PivotReport on the target worksheet."""
    return PivotCalculationEngine().render_report(
        workbook, layout, existing_report=existing_report
    )


def refresh_pivot_report(workbook: WorkbookModel, report: PivotReport) -> bool:
    """Refresh an existing PivotReport from its source range."""
    return PivotCalculationEngine().refresh_report(workbook, report)
