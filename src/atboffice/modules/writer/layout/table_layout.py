"""Quire table layout engine (Word 2003 port).

Computes table geometry, column widths, multi-paragraph cell layout,
row height resolution with vertical merges, vertical alignment,
and cross-page splitting with repeated header rows.
"""

from __future__ import annotations

import copy
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
    CellProperties,
    RowProperties,
    ShadingProperties,
    TableProperties,
)
from atboffice.modules.writer.models.table import CellMapEntry, table_map


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
    borders: dict[str, BorderProperties] = field(default_factory=dict)
    shd: ShadingProperties = field(default_factory=ShadingProperties)
    v_align: str = "top"
    content_offset_y: float = 0.0
    content_height: float = 0.0


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


def layout_table(
    table: Table,
    container_width: float,
    doc: Document,
) -> TableLayout:
    """Layout a Table block into geometric coordinates and paragraph portions."""
    container_width = max(20.0, container_width)
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
    cell_layouts_grid: list[list[CellLayout | None]] = [[None] * len(resolved_grid) for _ in range(num_rows)]
    cell_content_heights: dict[int, float] = {}  # id(cell) -> height

    for r_idx, row in enumerate(table.rows):
        row_entries = m[r_idx]
        for entry in row_entries:
            if entry.is_hidden:
                continue
            c0 = entry.col_idx
            c1 = min(len(col_xs) - 1, c0 + entry.span)
            cell_w = col_xs[c1] - col_xs[c0]
            inner_w = max(10.0, cell_w - mar_l - mar_r)

            p_layouts: list[ParagraphLayout] = []
            cur_p_y = mar_t
            for block in entry.cell.blocks:
                if isinstance(block, Paragraph):
                    playout = layout_paragraph(
                        p=block,
                        container_width=inner_w,
                        section_props=doc.sect,
                        doc=doc,
                    )
                    p_layouts.append(playout)
                    cur_p_y += playout.height + playout.space_before + playout.space_after

            total_h = cur_p_y + mar_b
            cell_content_heights[id(entry.cell)] = total_h

            cl = CellLayout(
                cell=entry.cell,
                col_idx=c0,
                row_idx=r_idx,
                x=col_xs[c0],
                y=0.0,
                width=cell_w,
                height=total_h,
                paragraphs_layout=p_layouts,
                borders=dict(entry.cell.tc_pr.borders),
                shd=copy.deepcopy(entry.cell.tc_pr.shd),
                v_align=entry.cell.tc_pr.v_align or "top",
                content_height=total_h,
            )
            cell_layouts_grid[r_idx][c0] = cl

    # 2. Compute Row Heights
    row_heights: list[float] = [18.0] * num_rows
    for r_idx, row in enumerate(table.rows):
        single_row_cells = [
            cell_layouts_grid[r_idx][e.col_idx]
            for e in m[r_idx]
            if not e.is_hidden and e.rowspan == 1 and cell_layouts_grid[r_idx][e.col_idx] is not None
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
        x=0.0,
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
