"""Quire table layout engine (Word 2003 port).

Computes table geometry, column widths, multi-paragraph cell layout,
row height resolution with vertical merges, vertical alignment,
and cross-page splitting with repeated header rows.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.writer.layout.portions import (
    ParagraphLayout,
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Table,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    ShadingProperties,
)
from atboffice.modules.writer.models.table import table_map


@dataclass
class CellLayout:
    """Computed layout geometry and paragraphs for a single cell."""

    cell: Cell
    col_idx: int
    row_idx: int
    x: float
    y: float
    width: float
    height: float
    paragraphs_layout: list[ParagraphLayout] = field(default_factory=list)
    # Ordered cell content (paragraphs and nested tables) with their top offsets
    # relative to the cell's content origin (before the paragraph's space-before).
    block_layouts: list[ParagraphLayout | TableLayout] = field(default_factory=list)
    block_tops: list[float] = field(default_factory=list)
    borders: dict[str, BorderProperties] = field(default_factory=dict)
    shd: ShadingProperties = field(default_factory=ShadingProperties)
    v_align: str = "top"
    content_offset_y: float = 0.0
    content_height: float = 0.0
    mar_t: float = 0.0
    mar_b: float = 0.0
    mar_l: float = 5.4
    mar_r: float = 5.4


def resolve_cell_borders(
    tbl_borders: dict[str, BorderProperties] | None,
    cell_borders: dict[str, BorderProperties] | None,
    row_idx: int,
    col_idx: int,
    rowspan: int,
    span: int,
    num_rows: int,
    num_cols: int,
) -> dict[str, BorderProperties]:
    """Resolve cascading borders for a cell.

    Handles outer borders vs insideH/insideV and cell-level overrides.
    """
    tb = tbl_borders or {}
    own = cell_borders or {}

    def pick(side: str, outer_key: str, inner_key: str, is_outer: bool) -> BorderProperties:
        if side in own:
            return own[side]
        if is_outer:
            if outer_key in tb:
                return tb[outer_key]
        else:
            if inner_key in tb:
                return tb[inner_key]
        return BorderProperties(val="none")

    return {
        "top": pick("top", "top", "insideH", row_idx == 0),
        "bottom": pick("bottom", "bottom", "insideH", row_idx + rowspan >= num_rows),
        "left": pick("left", "left", "insideV", col_idx == 0),
        "right": pick("right", "right", "insideV", col_idx + span >= num_cols),
    }


@dataclass
class RowLayout:
    """Computed layout geometry and cells for a single table row."""

    row: Row
    row_idx: int
    y: float
    height: float
    cells: list[CellLayout] = field(default_factory=list)
    is_header: bool = False
    is_repeated_header: bool = False


@dataclass
class TableLayout:
    """Computed layout for an entire table or page slice of a table."""

    table: Table
    x: float
    y: float
    width: float
    height: float
    rows: list[RowLayout] = field(default_factory=list)
    grid: list[float] = field(default_factory=list)
    total_grid_width: float = 0.0


# Guard against pathological nesting depth in malformed documents.
_MAX_NESTING_DEPTH = 16


def _table_style_chain(doc: Document, table: Table) -> list[Any]:
    """Return the table style chain, most-derived first, following basedOn (cycle-safe)."""
    styles = getattr(doc, "styles", None) or {}
    style_id = getattr(table.tbl_pr, "style", "") or ""
    st = styles.get(style_id)
    if st is None or getattr(st, "style_type", "") != "table":
        # Unknown / absent style: fall back to the document's default table style.
        # Prefer the document's own default over the builtin TableNormal.
        defaults = [
            s
            for s in styles.values()
            if getattr(s, "style_type", "") == "table" and getattr(s, "is_default", False)
        ]
        defaults.sort(key=lambda s: bool(getattr(s, "builtin", True)))
        st = defaults[0] if defaults else None
    chain: list[Any] = []
    seen: set[str] = set()
    while st is not None and st.id not in seen:
        seen.add(st.id)
        chain.append(st)
        st = styles.get(st.based_on) if st.based_on else None
    return chain


def resolve_table_style_props(doc: Document, table: Table) -> dict[str, Any]:
    """Resolve effective table borders and indent.

    Style values cascade along ``basedOn``; direct ``w:tblPr`` values override
    the style per border side, and a direct ``w:tblInd`` overrides the style indent.
    """
    borders: dict[str, BorderProperties] = {}
    ind = 0.0
    for st in reversed(_table_style_chain(doc, table)):
        st_tbl_pr = getattr(st, "tbl_pr", None) or {}
        borders.update(st_tbl_pr.get("borders") or {})
        if st_tbl_pr.get("ind") is not None:
            ind = float(st_tbl_pr["ind"])
    borders.update(table.tbl_pr.borders or {})
    direct_ind = getattr(table.tbl_pr, "ind", None)
    if direct_ind is not None:
        ind = float(direct_ind)
    return {"borders": borders, "ind": ind}


def layout_table(
    table: Table,
    container_width: float,
    doc: Document,
    _depth: int = 0,
) -> TableLayout:
    """Layout a Table block into geometric coordinates and paragraph portions.

    Nested tables inside cells are laid out recursively with the cell's inner
    width as their container width.
    """
    container_width = max(20.0, container_width)
    style_props = resolve_table_style_props(doc, table)
    total_raw_grid = sum(table.grid) if table.grid else container_width
    if total_raw_grid <= 0:
        total_raw_grid = container_width

    # Resolve grid scaling
    w_type = getattr(table.tbl_pr, "w_type", "auto")
    tbl_w = getattr(table.tbl_pr, "w", 0.0) or 0.0
    if w_type == "pct" and tbl_w > 0:
        target_w = container_width * (tbl_w / 5000.0 if tbl_w > 100 else tbl_w / 100.0)
    elif w_type == "dxa" and tbl_w > 0:
        target_w = min(tbl_w, container_width)
    elif total_raw_grid > container_width:
        target_w = container_width
    else:
        target_w = total_raw_grid

    scale = target_w / total_raw_grid
    resolved_grid = [round(g * scale, 2) for g in table.grid] if table.grid else [target_w]

    # Precalculate column X boundaries
    col_xs = [0.0]
    for w in resolved_grid:
        col_xs.append(col_xs[-1] + w)

    table_width = col_xs[-1]
    cell_mar = table.tbl_pr.cell_mar or {"t": 0.0, "b": 0.0, "l": 5.4, "r": 5.4}
    mar_l = float(cell_mar.get("l", 5.4))
    mar_r = float(cell_mar.get("r", 5.4))
    mar_t = float(cell_mar.get("t", 0.0))
    mar_b = float(cell_mar.get("b", 0.0))

    m = table_map(table)
    num_rows = len(table.rows)

    # 1. Compute paragraph layouts and content height for each cell
    cell_layouts_grid: list[list[CellLayout | None]] = [
        [None] * len(resolved_grid) for _ in range(num_rows)
    ]
    cell_content_heights: dict[int, float] = {}  # id(cell) -> height

    for r_idx, row in enumerate(table.rows):
        row_entries = m[r_idx]
        for entry in row_entries:
            if entry.is_hidden:
                continue
            c0 = entry.col_idx
            c1 = min(len(col_xs) - 1, c0 + entry.span)
            cell_w = col_xs[c1] - col_xs[c0]

            # Cascade per-cell margin: tc_mar overrides tbl_cell_mar
            tc_mar = entry.cell.tc_pr.tc_mar or {}
            c_mar_l = float(tc_mar.get("l", mar_l))
            c_mar_r = float(tc_mar.get("r", mar_r))
            c_mar_t = float(tc_mar.get("t", mar_t))
            c_mar_b = float(tc_mar.get("b", mar_b))

            inner_w = max(10.0, cell_w - c_mar_l - c_mar_r)

            p_layouts: list[ParagraphLayout] = []
            items: list[ParagraphLayout | TableLayout] = []
            item_tops: list[float] = []
            cur_p_y = c_mar_t
            for block in entry.cell.blocks:
                if isinstance(block, Paragraph):
                    playout = layout_paragraph(
                        p=block,
                        container_width=inner_w,
                        section_props=doc.sect,
                        doc=doc,
                    )
                    p_layouts.append(playout)
                    items.append(playout)
                    item_tops.append(cur_p_y - c_mar_t)
                    cur_p_y += (
                        playout.height
                        + playout.effective_space_before
                        + playout.effective_space_after
                    )
                elif isinstance(block, Table) and _depth < _MAX_NESTING_DEPTH:
                    inner_tl = layout_table(block, inner_w, doc, _depth=_depth + 1)
                    # Keep the nested table inside its cell: clamp its indent so the
                    # table never starts left of, or runs past, the cell's text box.
                    inner_tl.x = min(max(inner_tl.x, 0.0), max(0.0, inner_w - inner_tl.width))
                    items.append(inner_tl)
                    item_tops.append(cur_p_y - c_mar_t)
                    cur_p_y += inner_tl.height

            total_h = cur_p_y + c_mar_b
            cell_content_heights[id(entry.cell)] = total_h

            resolved_bds = resolve_cell_borders(
                tbl_borders=style_props["borders"],
                cell_borders=entry.cell.tc_pr.borders,
                row_idx=r_idx,
                col_idx=c0,
                rowspan=entry.rowspan,
                span=entry.span,
                num_rows=num_rows,
                num_cols=len(resolved_grid),
            )

            cl = CellLayout(
                cell=entry.cell,
                col_idx=c0,
                row_idx=r_idx,
                x=col_xs[c0],
                y=0.0,
                width=cell_w,
                height=total_h,
                paragraphs_layout=p_layouts,
                block_layouts=items,
                block_tops=item_tops,
                borders=resolved_bds,
                shd=copy.deepcopy(entry.cell.tc_pr.shd),
                v_align=entry.cell.tc_pr.v_align or "top",
                content_height=total_h,
                mar_t=c_mar_t,
                mar_b=c_mar_b,
                mar_l=c_mar_l,
                mar_r=c_mar_r,
            )
            cell_layouts_grid[r_idx][c0] = cl

    # 2. Compute Row Heights
    row_heights: list[float] = [18.0] * num_rows
    for r_idx, row in enumerate(table.rows):
        single_row_cells = [
            cell_layouts_grid[r_idx][e.col_idx]
            for e in m[r_idx]
            if not e.is_hidden
            and e.rowspan == 1
            and cell_layouts_grid[r_idx][e.col_idx] is not None
        ]
        max_content = max((c.content_height for c in single_row_cells), default=18.0)
        tr_pr = row.tr_pr
        h = tr_pr.h
        h_rule = tr_pr.h_rule or "auto"
        if h_rule == "exact" and h is not None:
            rh = float(h)
        elif h_rule == "atLeast" and h is not None:
            rh = max(float(h), max_content)
        else:
            rh = max(max_content, 18.0)
        row_heights[r_idx] = rh

    # Spanned cells height expansion
    for r_idx in range(num_rows):
        for entry in m[r_idx]:
            if not entry.is_hidden and entry.rowspan > 1:
                cl = cell_layouts_grid[r_idx][entry.col_idx]
                if cl:
                    sum_spanned_h = sum(row_heights[r_idx : r_idx + entry.rowspan])
                    if cl.content_height > sum_spanned_h:
                        diff = cl.content_height - sum_spanned_h
                        add_per_row = diff / entry.rowspan
                        for r in range(r_idx, r_idx + entry.rowspan):
                            row_heights[r] += add_per_row

    # 3. Finalize RowLayout and CellLayout positions
    row_layouts: list[RowLayout] = []
    cur_y = 0.0

    for r_idx, row in enumerate(table.rows):
        rh = row_heights[r_idx]
        is_hdr = bool(row.tr_pr.tbl_header)
        rl = RowLayout(
            row=row,
            row_idx=r_idx,
            y=cur_y,
            height=rh,
            cells=[],
            is_header=is_hdr,
            is_repeated_header=False,
        )

        for entry in m[r_idx]:
            if entry.is_hidden:
                continue
            cl = cell_layouts_grid[r_idx][entry.col_idx]
            if not cl:
                continue
            total_cell_h = sum(row_heights[r_idx : r_idx + entry.rowspan])
            cl.y = cur_y
            cl.height = total_cell_h

            # Vertical Alignment
            valign = getattr(cl.cell.tc_pr, "v_align", "top") or "top"
            if valign == "center" and total_cell_h > cl.content_height:
                cl.content_offset_y = (total_cell_h - cl.content_height) / 2.0
            elif valign == "bottom" and total_cell_h > cl.content_height:
                cl.content_offset_y = total_cell_h - cl.content_height
            else:
                cl.content_offset_y = 0.0

            rl.cells.append(cl)

        row_layouts.append(rl)
        cur_y += rh

    return TableLayout(
        table=table,
        x=style_props["ind"],
        y=0.0,
        width=table_width,
        height=cur_y,
        rows=row_layouts,
        grid=resolved_grid,
        total_grid_width=table_width,
    )


def split_table_for_page(
    table_layout: TableLayout,
    start_row: int,
    avail_height: float,
    is_first_page: bool = True,
) -> tuple[TableLayout | None, int | None]:
    """Slice a TableLayout into rows that fit within avail_height.

    Repeats header rows automatically when is_first_page is False.
    Returns (sliced_table_layout, next_row_index_or_None).
    """
    if start_row >= len(table_layout.rows):
        return None, None

    num_rows = len(table_layout.rows)

    # Detect repeating header rows
    hdr_rows: list[RowLayout] = []
    hdr_height = 0.0
    hdr_idx = 0
    while hdr_idx < num_rows and table_layout.rows[hdr_idx].row.tr_pr.tbl_header:
        hdr_rows.append(table_layout.rows[hdr_idx])
        hdr_height += table_layout.rows[hdr_idx].height
        hdr_idx += 1

    page_rows: list[RowLayout] = []
    accum_h = 0.0

    # Repeat headers on subsequent pages
    if not is_first_page and hdr_rows and start_row >= len(hdr_rows):
        if hdr_height < avail_height:
            for hr in hdr_rows:
                rep_r = copy.deepcopy(hr)
                rep_r.is_repeated_header = True
                rep_r.y = accum_h
                for c in rep_r.cells:
                    c.y = accum_h
                page_rows.append(rep_r)
                accum_h += hr.height

    cur_r = start_row
    while cur_r < num_rows:
        rl = table_layout.rows[cur_r]
        rh = rl.height
        if accum_h + rh > avail_height + 0.5:
            # Row doesn't fit
            if not page_rows:
                # Force at least one row to avoid infinite loop
                rep_r = copy.deepcopy(rl)
                rep_r.y = accum_h
                for c in rep_r.cells:
                    c.y = accum_h
                page_rows.append(rep_r)
                accum_h += rh
                cur_r += 1
            break

        rep_r = copy.deepcopy(rl)
        rep_r.y = accum_h
        for c in rep_r.cells:
            c.y = accum_h
        page_rows.append(rep_r)
        accum_h += rh
        cur_r += 1

    next_r = cur_r if cur_r < num_rows else None
    sliced = TableLayout(
        table=table_layout.table,
        x=table_layout.x,
        y=0.0,
        width=table_layout.width,
        height=accum_h,
        rows=page_rows,
        grid=list(table_layout.grid),
        total_grid_width=table_layout.total_grid_width,
    )
    return sliced, next_r


def iter_table_paragraphs(
    table_layout: TableLayout,
    origin_x: float,
    origin_y: float,
) -> Iterator[tuple[Paragraph, ParagraphLayout, float, float]]:
    """Yield ``(paragraph, layout, top, inner_x)`` for every paragraph in a table.

    Recurses into nested tables. ``top`` is the paragraph's first-line origin
    (after space-before) and ``inner_x`` the left edge of the cell's text box, both
    in the same coordinate space as ``origin_x`` / ``origin_y`` (the table's origin).
    """
    for rl in table_layout.rows:
        for cl in rl.cells:
            inner_x = origin_x + cl.x + cl.mar_l
            content_y = origin_y + cl.y + cl.content_offset_y + cl.mar_t
            paras = iter([b for b in cl.cell.blocks if isinstance(b, Paragraph)])
            for item, item_top in zip(cl.block_layouts, cl.block_tops):
                if isinstance(item, TableLayout):
                    yield from iter_table_paragraphs(item, inner_x + item.x, content_y + item_top)
                    continue
                para = next(paras, None)
                if para is None:
                    break
                yield para, item, content_y + item_top + item.effective_space_before, inner_x
