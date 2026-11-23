"""Horizontal ruler extras: table column boundaries and multi-column gutters.

Positions are points measured from the page's left text margin (the ruler's origin).
"""

from __future__ import annotations

from typing import Any


def _current_table(canvas: Any) -> Any | None:
    ctx = canvas.get_current_table_context()
    return ctx["tbl"] if ctx else None


def table_column_markers(canvas: Any, page_idx: int) -> list[float]:
    """Column boundaries of the table holding the caret, from its laid-out position.

    Returns an empty list outside tables. Nested tables (not laid out as page
    fragments) fall back to the grid widths from the margin.
    """
    tbl = _current_table(canvas)
    if tbl is None:
        return []
    pages = getattr(canvas.pagination, "pages", None) or []
    order = [page_idx] + [i for i in range(len(pages)) if i != page_idx]
    for idx in order:
        if not 0 <= idx < len(pages):
            continue
        for reg in pages[idx].regions:
            for col in reg.columns:
                for frag in col.fragments:
                    tl = frag.table_layout
                    if tl is not None and tl.table is tbl:
                        return _cumulative(col.left + tl.x, tl.grid or tbl.grid)
    ind = tbl.tbl_pr.ind or 0.0
    return _cumulative(ind, tbl.grid)


def _cumulative(start: float, widths: list[float]) -> list[float]:
    out = [round(start, 2)]
    x = start
    for w in widths:
        x += float(w)
        out.append(round(x, 2))
    return out if len(out) > 1 else []


def column_gutters(canvas: Any, page_idx: int) -> list[tuple[float, float]]:
    """(start, end) of the gaps between text columns on the caret's page region."""
    pages = getattr(canvas.pagination, "pages", None) or []
    if not 0 <= page_idx < len(pages):
        return []
    for reg in pages[page_idx].regions:
        cols = sorted(reg.columns, key=lambda c: c.left)
        if len(cols) < 2:
            continue
        return [
            (round(a.left + a.width, 2), round(b.left, 2))
            for a, b in zip(cols, cols[1:], strict=False)
            if b.left > a.left + a.width
        ]
    return []
