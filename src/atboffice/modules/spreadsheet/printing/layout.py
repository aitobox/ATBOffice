"""Split a worksheet into printed pages (print area, scaling / fit-to, titles, breaks)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from atboffice.modules.spreadsheet.printing.setup import SheetPrintSetup

PX_TO_PT = 0.75  # grid pixels are 96 dpi
HEADING_W = 30.0  # row-number column (pt, before scaling)
HEADING_H = 14.0  # column-letter row


@dataclass
class PrintPage:
    rows: tuple[int, int]
    cols: tuple[int, int]
    repeat_rows: tuple[int, int] | None
    repeat_cols: tuple[int, int] | None


@dataclass
class PrintLayout:
    pages: list[PrintPage]
    scale: float  # points per grid pixel
    area: tuple[int, int, int, int]


def _drawing_extent(sheet: Any) -> tuple[int, int]:
    """Last (row, col) covered by any drawing."""
    from atboffice.modules.spreadsheet.views.object_layer import object_to_rect

    geo = sheet.geometry
    max_r = max_c = -1
    for obj in getattr(sheet, "drawings", []) or []:
        try:
            rect = object_to_rect(obj, geo, 0, 0, 0, 0)
        except Exception:
            continue
        max_r = max(max_r, geo.find_row_at(rect.bottom()))
        max_c = max(max_c, geo.find_col_at(rect.right()))
    return max_r, max_c


def content_bounds(sheet: Any) -> tuple[int, int, int, int]:
    """Used range: cells with values or visible formatting, merges and drawings."""
    rows: list[int] = []
    cols: list[int] = []
    for (r, c), cell in sheet.cells.items():
        has_value = cell.value not in (None, "") or bool(getattr(cell, "formula", None))
        styled = bool(getattr(cell, "bg_color", None)) or any(
            getattr(cell, side, None) is not None
            for side in ("border_top", "border_bottom", "border_left", "border_right")
        )
        if has_value or styled:
            rows.append(r)
            cols.append(c)
    for r1, c1, r2, c2 in getattr(sheet, "merges", []) or []:
        rows += [r1, r2]
        cols += [c1, c2]
    dr, dc = _drawing_extent(sheet)
    if dr >= 0:
        rows.append(dr)
        cols.append(dc)
    if not rows:
        return 0, 0, 0, 0
    return min(rows), min(cols), max(rows), max(cols)


def _sizes(geo: Any, start: int, end: int, is_row: bool) -> list[float]:
    size = geo.row_size if is_row else geo.col_size
    return [float(size(i)) for i in range(start, end + 1)]


def _split(
    sizes: list[float], start: int, avail: float, breaks: list[int]
) -> list[tuple[int, int]]:
    """Greedy split of consecutive indices into spans that fit ``avail`` (manual breaks win)."""
    spans: list[tuple[int, int]] = []
    span_start = start
    used = 0.0
    for offset, sz in enumerate(sizes):
        idx = start + offset
        forced = idx in breaks and idx > span_start
        if forced or (used > 0 and used + sz > avail):
            spans.append((span_start, idx - 1))
            span_start = idx
            used = 0.0
        used += sz
    spans.append((span_start, start + len(sizes) - 1))
    return spans


def paginate(sheet: Any, setup: SheetPrintSetup) -> PrintLayout:
    geo = sheet.geometry
    used = content_bounds(sheet)
    if setup.print_area is not None:
        # Whole-row / whole-column areas (A:B, 1:5) print only as far as the used range
        a1, b1, a2, b2 = setup.print_area
        area = (a1, b1, max(a1, min(a2, used[2])), max(b1, min(b2, used[3])))
    else:
        area = used
    r1, c1, r2, c2 = area
    paper_w, paper_h = setup.paper_size()
    m = setup.margins
    avail_w = paper_w - m["left"] - m["right"]
    avail_h = paper_h - m["top"] - m["bottom"]
    if setup.headings:
        avail_w -= HEADING_W
        avail_h -= HEADING_H

    col_sizes = _sizes(geo, c1, c2, is_row=False)
    row_sizes = _sizes(geo, r1, r2, is_row=True)
    title_rows = setup.title_rows
    title_cols = setup.title_cols
    title_h = sum(_sizes(geo, *title_rows, True)) if title_rows else 0.0
    title_w = sum(_sizes(geo, *title_cols, False)) if title_cols else 0.0

    if setup.fit_to:
        total_w = sum(col_sizes) * PX_TO_PT
        total_h = sum(row_sizes) * PX_TO_PT
        factors = [1.0]
        if setup.fit_width > 0 and total_w > 0:
            factors.append(avail_w * setup.fit_width / total_w)
        if setup.fit_height > 0 and total_h > 0:
            factors.append(avail_h * setup.fit_height / total_h)
        zoom = max(0.1, min(factors))
    else:
        zoom = max(0.1, min(4.0, setup.scale / 100.0))
    k = PX_TO_PT * zoom

    vs = getattr(sheet, "view_state", None)
    row_breaks = list(getattr(vs, "row_breaks", []) or [])
    col_breaks = list(getattr(vs, "col_breaks", []) or [])

    # Leave room for repeated titles on every page (they print above / left of the body)
    col_spans = _split(col_sizes, c1, max(1.0, avail_w / k - title_w), col_breaks)
    row_spans = _split(row_sizes, r1, max(1.0, avail_h / k - title_h), row_breaks)

    pages: list[PrintPage] = []
    ordered = (
        [(rs, cs) for cs in col_spans for rs in row_spans]
        if setup.page_order != "over_then_down"
        else [(rs, cs) for rs in row_spans for cs in col_spans]
    )
    for rs, cs in ordered:
        rep_r = title_rows if title_rows and rs[0] > title_rows[1] else None
        rep_c = title_cols if title_cols and cs[0] > title_cols[1] else None
        pages.append(PrintPage(rows=rs, cols=cs, repeat_rows=rep_r, repeat_cols=rep_c))
    return PrintLayout(pages=pages, scale=k, area=area)
