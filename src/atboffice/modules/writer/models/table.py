"""Table models, grid mapping, and structural editing operations for Quire."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from atboffice.modules.writer.models.document import (
    Cell,
    Paragraph,
    Row,
    Table,
    TextItem,
    plen,
)
from atboffice.modules.writer.models.properties import (
    CellProperties,
    TableProperties,
)


@dataclass
class CellMapEntry:
    """Mapping entry for a cell on the 2D table grid."""

    cell: Cell
    row_idx: int
    col_idx: int
    span: int = 1
    rowspan: int = 1
    is_hidden: bool = False


def create_simple_table(
    rows: int,
    cols: int,
    width: float = 468.0,
    col_widths: list[float] | None = None,
) -> Table:
    """Create a standard N x M table with paragraphs initialized in each cell."""
    rows = max(1, rows)
    cols = max(1, cols)
    if col_widths and len(col_widths) == cols:
        grid = [float(w) for w in col_widths]
    else:
        grid = [round(width / cols, 2)] * cols

    table_rows: list[Row] = []
    for _ in range(rows):
        cells: list[Cell] = []
        for _ in range(cols):
            p = Paragraph(runs=[TextItem()])
            c = Cell(tc_pr=CellProperties(grid_span=1), blocks=[p])
            cells.append(c)
        table_rows.append(Row(cells=cells))

    return Table(
        grid=grid,
        rows=table_rows,
        tbl_pr=TableProperties(w=sum(grid), w_type="dxa"),
    )


def table_map(table: Table) -> list[list[CellMapEntry]]:
    """Generate a 2D mapping of cells with resolved spans, rowspans, and hidden flags."""
    mapped_rows: list[list[CellMapEntry]] = []

    for r_idx, row in enumerate(table.rows):
        cur_c = 0
        entry_list: list[CellMapEntry] = []
        for cell in row.cells:
            span = max(1, getattr(cell.tc_pr, "grid_span", 1) or 1)
            entry = CellMapEntry(
                cell=cell,
                row_idx=r_idx,
                col_idx=cur_c,
                span=span,
                rowspan=1,
                is_hidden=False,
            )
            entry_list.append(entry)
            cur_c += span
        mapped_rows.append(entry_list)

    # Resolve vertical merges (rowspan and is_hidden)
    num_rows = len(mapped_rows)
    for r_idx in range(num_rows):
        for entry in mapped_rows[r_idx]:
            vm = getattr(entry.cell.tc_pr, "v_merge", None)
            if vm == "continue":
                # Check if there is a restart above with matching col_idx
                has_restart_above = False
                for k in range(r_idx - 1, -1, -1):
                    above_entry = next(
                        (e for e in mapped_rows[k] if e.col_idx == entry.col_idx), None
                    )
                    if above_entry:
                        above_vm = getattr(above_entry.cell.tc_pr, "v_merge", None)
                        if above_vm == "restart":
                            has_restart_above = True
                            break
                        if above_vm != "continue":
                            break
                if has_restart_above:
                    entry.is_hidden = True
                else:
                    # Rogue continue without restart, treat as normal cell
                    entry.is_hidden = False
            elif vm == "restart":
                # Count subsequent continue cells in same column
                entry.rowspan = 1
                for k in range(r_idx + 1, num_rows):
                    below_entry = next(
                        (e for e in mapped_rows[k] if e.col_idx == entry.col_idx), None
                    )
                    if (
                        below_entry
                        and getattr(below_entry.cell.tc_pr, "v_merge", None) == "continue"
                    ):
                        entry.rowspan += 1
                    else:
                        break

    return mapped_rows


def clean_merges(table: Table) -> None:
    """Sanitize orphaned vertical merges in the table."""
    m = table_map(table)
    num_rows = len(m)

    # 1. Continue with no restart above becomes restart
    for r_idx in range(num_rows):
        for entry in m[r_idx]:
            if entry.cell.tc_pr.v_merge == "continue":
                up = (
                    next(
                        (
                            x
                            for x in m[r_idx - 1]
                            if x.col_idx == entry.col_idx and x.span == entry.span
                        ),
                        None,
                    )
                    if r_idx > 0
                    else None
                )
                if not up or not up.cell.tc_pr.v_merge:
                    entry.cell.tc_pr.v_merge = "restart"

    # 2. Restart with no continue below loses v_merge
    m2 = table_map(table)
    for r_idx in range(num_rows):
        for entry in m2[r_idx]:
            if entry.cell.tc_pr.v_merge == "restart":
                dn = (
                    next((x for x in m2[r_idx + 1] if x.col_idx == entry.col_idx), None)
                    if r_idx + 1 < num_rows
                    else None
                )
                if not dn or dn.cell.tc_pr.v_merge != "continue":
                    entry.cell.tc_pr.v_merge = None


def insert_rows(
    table: Table,
    row_idx: int,
    count: int = 1,
    above: bool = False,
) -> None:
    """Insert new row(s) above or below row_idx."""
    if not table.rows:
        return
    row_idx = max(0, min(row_idx, len(table.rows) - 1))
    at = row_idx if above else row_idx + 1
    m = table_map(table)
    ref_row_entries = m[row_idx]
    ref_row = table.rows[row_idx]

    new_rows: list[Row] = []
    for _ in range(count):
        new_cells: list[Cell] = []
        for entry in ref_row_entries:
            span = entry.span
            below_m = (
                next((x for x in m[row_idx + 1] if x.col_idx == entry.col_idx), None)
                if row_idx + 1 < len(m)
                else None
            )
            in_merge = (
                entry.cell.tc_pr.v_merge == "continue"
                if above
                else (
                    entry.cell.tc_pr.v_merge in ("restart", "continue")
                    and below_m is not None
                    and below_m.cell.tc_pr.v_merge == "continue"
                )
            )
            tc_pr = CellProperties(
                grid_span=span,
                v_merge="continue" if in_merge else None,
                v_align=entry.cell.tc_pr.v_align,
            )
            p = Paragraph(runs=[TextItem()])
            new_cells.append(Cell(tc_pr=tc_pr, blocks=[p]))

        tr_pr = copy.deepcopy(ref_row.tr_pr)
        if not above or row_idx > 0:
            tr_pr.tbl_header = False
        new_rows.append(Row(tr_pr=tr_pr, cells=new_cells))

    table.rows[at:at] = new_rows
    clean_merges(table)


def delete_rows(table: Table, r0: int, r1: int) -> None:
    """Delete row(s) from r0 to r1 (inclusive)."""
    if not table.rows:
        return
    r0 = max(0, min(r0, len(table.rows) - 1))
    r1 = max(r0, min(r1, len(table.rows) - 1))
    m = table_map(table)

    # If merge starts in deleted rows and continues below, restart below
    if r1 + 1 < len(m):
        below_entries = m[r1 + 1]
        for entry in below_entries:
            if entry.cell.tc_pr.v_merge == "continue":
                # Find if restart was in deleted range
                had_restart_in_deleted = any(
                    any(
                        e.col_idx == entry.col_idx and e.cell.tc_pr.v_merge == "restart"
                        for e in m[r]
                    )
                    for r in range(r0, r1 + 1)
                )
                if had_restart_in_deleted:
                    entry.cell.tc_pr.v_merge = "restart"
                    # If below cell was empty, carry content from the restart cell
                    if all(isinstance(b, Paragraph) and plen(b) == 0 for b in entry.cell.blocks):
                        src_entry = next(
                            (
                                e
                                for r in range(r0, r1 + 1)
                                for e in m[r]
                                if e.col_idx == entry.col_idx and e.cell.tc_pr.v_merge == "restart"
                            ),
                            None,
                        )
                        if src_entry:
                            entry.cell.blocks = copy.deepcopy(src_entry.cell.blocks)

    del table.rows[r0 : r1 + 1]
    if not table.rows:
        # Keep at least one valid row
        cols = len(table.grid) or 1
        table.rows.append(
            Row(
                cells=[
                    Cell(tc_pr=CellProperties(grid_span=1), blocks=[Paragraph(runs=[TextItem()])])
                    for _ in range(cols)
                ]
            )
        )
    clean_merges(table)


def insert_cols(
    table: Table,
    col_idx: int,
    count: int = 1,
    left: bool = False,
    default_width: float = 72.0,
) -> None:
    """Insert count column(s) left or right of col_idx."""
    gi = col_idx if left else col_idx + 1
    gi = max(0, min(gi, len(table.grid)))

    ref_w = table.grid[min(col_idx, len(table.grid) - 1)] if table.grid else default_width
    new_widths = [ref_w] * count
    table.grid[gi:gi] = new_widths

    m = table_map(table)
    for r_idx, row in enumerate(table.rows):
        row_entries = m[r_idx]
        spanning = next(
            (e for e in row_entries if e.col_idx < gi and e.col_idx + e.span > gi), None
        )
        if spanning:
            spanning.cell.tc_pr.grid_span += count
            continue

        insert_pos = len(row.cells)
        for i, cell in enumerate(row.cells):
            entry = next((e for e in row_entries if e.cell is cell), None)
            if entry and entry.col_idx >= gi:
                insert_pos = i
                break

        new_cells = [
            Cell(
                tc_pr=CellProperties(grid_span=1),
                blocks=[Paragraph(runs=[TextItem()])],
            )
            for _ in range(count)
        ]
        row.cells[insert_pos:insert_pos] = new_cells

    clean_merges(table)


def delete_cols(table: Table, c0: int, c1: int) -> None:
    """Delete columns from c0 to c1 (inclusive)."""
    if not table.grid:
        return
    c0 = max(0, min(c0, len(table.grid) - 1))
    c1 = max(c0, min(c1, len(table.grid) - 1))
    del table.grid[c0 : c1 + 1]

    m = table_map(table)
    for r_idx, row in enumerate(table.rows):
        row_entries = m[r_idx]
        cells_to_remove: list[Cell] = []
        for entry in row_entries:
            a = max(entry.col_idx, c0)
            b = min(entry.col_idx + entry.span - 1, c1)
            if a > b:
                continue
            overlap = b - a + 1
            if overlap >= entry.span:
                cells_to_remove.append(entry.cell)
            else:
                entry.cell.tc_pr.grid_span -= overlap

        row.cells = [c for c in row.cells if c not in cells_to_remove]
        if not row.cells:
            row.cells.append(
                Cell(tc_pr=CellProperties(grid_span=1), blocks=[Paragraph(runs=[TextItem()])])
            )

    if not table.grid:
        table.grid.append(72.0)

    clean_merges(table)


def merge_cells(table: Table, r0: int, r1: int, c0: int, c1: int) -> Cell:
    """Merge cells within bounding box [r0..r1, c0..c1] respecting vMerge and gridSpan."""
    r0 = max(0, min(r0, len(table.rows) - 1))
    r1 = max(r0, min(r1, len(table.rows) - 1))
    c0 = max(0, min(c0, len(table.grid) - 1))
    c1 = max(c0, min(c1, len(table.grid) - 1))

    # Expand box until no cell crosses boundary
    m = table_map(table)
    for _ in range(20):
        changed = False
        for r in range(r0, r1 + 1):
            for entry in m[r]:
                if entry.col_idx + entry.span - 1 < c0 or entry.col_idx > c1:
                    continue
                if entry.col_idx < c0:
                    c0 = entry.col_idx
                    changed = True
                if entry.col_idx + entry.span - 1 > c1:
                    c1 = entry.col_idx + entry.span - 1
                    changed = True
                if not entry.is_hidden and entry.rowspan > 1 and r + entry.rowspan - 1 > r1:
                    r1 = r + entry.rowspan - 1
                    changed = True
        if not changed:
            break

    # Gather non-empty paragraph blocks
    collected_blocks: list[Paragraph] = []
    for r in range(r0, r1 + 1):
        for entry in m[r]:
            if entry.col_idx < c0 or entry.col_idx > c1 or entry.is_hidden:
                continue
            for block in entry.cell.blocks:
                if isinstance(block, Paragraph) and plen(block) > 0:
                    collected_blocks.append(copy.deepcopy(block))

    top_entry = next((e for e in m[r0] if e.col_idx == c0), None)
    if not top_entry:
        return table.rows[r0].cells[0]

    top_cell = top_entry.cell
    span_width = c1 - c0 + 1
    top_cell.tc_pr.grid_span = span_width
    top_cell.tc_pr.v_merge = "restart" if r1 > r0 else None
    top_cell.blocks = collected_blocks if collected_blocks else [Paragraph(runs=[TextItem()])]

    # In row r0, remove other cells that were in [c0, c1]
    r0_row = table.rows[r0]
    r0_row.cells = [
        c
        for c in r0_row.cells
        if c is top_cell
        or not any(e.cell is c and e.col_idx >= c0 and e.col_idx <= c1 for e in m[r0])
    ]

    # In rows r0+1..r1, keep one continuation cell and remove the rest
    for r in range(r0 + 1, r1 + 1):
        row = table.rows[r]
        row_entries_in_range = [e for e in m[r] if e.col_idx >= c0 and e.col_idx <= c1]
        if not row_entries_in_range:
            continue
        first_entry = row_entries_in_range[0]
        first_entry.cell.tc_pr.grid_span = span_width
        first_entry.cell.tc_pr.v_merge = "continue"
        first_entry.cell.blocks = [Paragraph(runs=[TextItem()])]

        # Remove other cells in this range
        other_cells = [e.cell for e in row_entries_in_range[1:]]
        row.cells = [c for c in row.cells if c not in other_cells]

    clean_merges(table)
    return top_cell


def split_cells(
    table: Table,
    cell: Cell,
    num_rows: int,
    num_cols: int,
) -> list[Cell]:
    """Split cell into num_rows x num_cols sub-cells."""
    num_rows = max(1, num_rows)
    num_cols = max(1, num_cols)
    m = table_map(table)

    target_entry: CellMapEntry | None = None
    for row in m:
        for entry in row:
            if entry.cell is cell:
                target_entry = entry
                break
        if target_entry:
            break

    if not target_entry:
        return [cell]

    ri = target_entry.row_idx
    c0 = target_entry.col_idx
    cur_span = target_entry.span

    news: list[Cell] = [cell]

    # Column split
    if num_cols > 1:
        if cur_span >= num_cols:
            # Distribute span
            base_span = cur_span // num_cols
            rem = cur_span % num_cols
            cell.tc_pr.grid_span = base_span + (1 if rem > 0 else 0)
            created: list[Cell] = []
            for i in range(1, num_cols):
                sp = base_span + (1 if i < rem else 0)
                nc = Cell(
                    tc_pr=CellProperties(grid_span=sp),
                    blocks=[Paragraph(runs=[TextItem()])],
                )
                created.append(nc)
            row = table.rows[ri]
            idx = row.cells.index(cell)
            row.cells[idx + 1 : idx + 1] = created
            news.extend(created)
        else:
            # Need to split grid columns
            orig_w = sum(table.grid[c0 : c0 + cur_span])
            sub_w = round(orig_w / num_cols, 2)
            new_sub_grid = [sub_w] * num_cols
            table.grid[c0 : c0 + cur_span] = new_sub_grid

            cell.tc_pr.grid_span = 1
            created = [
                Cell(
                    tc_pr=CellProperties(grid_span=1),
                    blocks=[Paragraph(runs=[TextItem()])],
                )
                for _ in range(num_cols - 1)
            ]
            row = table.rows[ri]
            idx = row.cells.index(cell)
            row.cells[idx + 1 : idx + 1] = created
            news.extend(created)

            # Adjust other rows' cells that crossed or were after c0
            clean_merges(table)

    return news
