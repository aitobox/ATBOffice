"""Unit tests for Quire Table models, layout, and multi-page pagination."""

from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.layout.table_layout import (
    TableLayout,
    layout_table,
    split_table_for_page,
)
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    RowProperties,
)
from atboffice.modules.writer.models.table import (
    create_simple_table,
    delete_cols,
    delete_rows,
    insert_cols,
    insert_rows,
    merge_cells,
    split_cells,
    table_map,
)


def _cell_text(cell: Cell) -> str:
    texts = []
    for block in cell.blocks:
        if isinstance(block, Paragraph):
            for run in block.runs:
                if isinstance(run, TextItem):
                    texts.append(run.text)
    return "".join(texts)


def _set_cell_text(cell: Cell, text: str) -> None:
    cell.blocks = [Paragraph(runs=[TextItem(text)])]


# ---------------------------------------------------------------------------
# Task 1: Table Model & Grid Mapping Tests
# ---------------------------------------------------------------------------


def test_create_simple_table():
    tbl = create_simple_table(rows=3, cols=4, width=400.0)
    assert len(tbl.rows) == 3
    assert len(tbl.grid) == 4
    assert tbl.grid == [100.0, 100.0, 100.0, 100.0]
    for row in tbl.rows:
        assert len(row.cells) == 4
        for cell in row.cells:
            assert cell.tc_pr.grid_span == 1
            assert cell.tc_pr.v_merge is None
            assert len(cell.blocks) >= 1


def test_table_map_basic():
    tbl = create_simple_table(rows=2, cols=3, width=300.0)
    m = table_map(tbl)
    assert len(m) == 2
    for r in range(2):
        assert len(m[r]) == 3
        for c in range(3):
            entry = m[r][c]
            assert entry.row_idx == r
            assert entry.col_idx == c
            assert entry.span == 1
            assert entry.rowspan == 1
            assert not entry.is_hidden


def test_table_map_grid_span_and_vmerge():
    # 3x3 table with gridSpan and vMerge
    tbl = create_simple_table(rows=3, cols=3, width=300.0)
    # Row 0: cell 0 spans 2 columns (col 0, col 1)
    tbl.rows[0].cells[0].tc_pr.grid_span = 2
    tbl.rows[0].cells.pop(1)  # Remove redundant cell in row 0

    # Col 2: Row 0 restart, Row 1 continue (vertical merge)
    tbl.rows[0].cells[1].tc_pr.v_merge = "restart"
    tbl.rows[1].cells[2].tc_pr.v_merge = "continue"

    m = table_map(tbl)
    assert len(m) == 3

    # Row 0
    assert m[0][0].col_idx == 0
    assert m[0][0].span == 2
    assert m[0][0].rowspan == 1

    assert m[0][1].col_idx == 2
    assert m[0][1].span == 1
    assert m[0][1].rowspan == 2  # spans row 0 and row 1!

    # Row 1, col 2 is hidden
    assert m[1][2].is_hidden is True
    assert m[1][2].col_idx == 2


def test_insert_and_delete_rows():
    tbl = create_simple_table(rows=2, cols=2, width=200.0)
    _set_cell_text(tbl.rows[0].cells[0], "R0C0")
    _set_cell_text(tbl.rows[1].cells[0], "R1C0")

    # Insert row below row 0
    insert_rows(tbl, row_idx=0, count=1, above=False)
    assert len(tbl.rows) == 3
    assert _cell_text(tbl.rows[0].cells[0]) == "R0C0"
    assert _cell_text(tbl.rows[1].cells[0]) == ""
    assert _cell_text(tbl.rows[2].cells[0]) == "R1C0"

    # Delete inserted row
    delete_rows(tbl, r0=1, r1=1)
    assert len(tbl.rows) == 2
    assert _cell_text(tbl.rows[0].cells[0]) == "R0C0"
    assert _cell_text(tbl.rows[1].cells[0]) == "R1C0"


def test_insert_and_delete_cols():
    tbl = create_simple_table(rows=2, cols=2, width=200.0)
    _set_cell_text(tbl.rows[0].cells[0], "C0")
    _set_cell_text(tbl.rows[0].cells[1], "C1")

    # Insert column between C0 and C1
    insert_cols(tbl, col_idx=0, count=1, left=False, default_width=50.0)
    assert len(tbl.grid) == 3
    assert len(tbl.rows[0].cells) == 3
    assert _cell_text(tbl.rows[0].cells[0]) == "C0"
    assert _cell_text(tbl.rows[0].cells[1]) == ""
    assert _cell_text(tbl.rows[0].cells[2]) == "C1"

    # Delete inserted col
    delete_cols(tbl, c0=1, c1=1)
    assert len(tbl.grid) == 2
    assert len(tbl.rows[0].cells) == 2
    assert _cell_text(tbl.rows[0].cells[0]) == "C0"
    assert _cell_text(tbl.rows[0].cells[1]) == "C1"


def test_merge_cells_horizontal():
    tbl = create_simple_table(rows=2, cols=3, width=300.0)
    _set_cell_text(tbl.rows[0].cells[0], "Alpha")
    _set_cell_text(tbl.rows[0].cells[1], "Beta")

    # Merge row 0, col 0 to col 1
    merged = merge_cells(tbl, r0=0, r1=0, c0=0, c1=1)
    assert merged.tc_pr.grid_span == 2
    assert len(tbl.rows[0].cells) == 2
    # Combined text from Alpha and Beta
    full_text = _cell_text(merged)
    assert "Alpha" in full_text
    assert "Beta" in full_text


def test_merge_cells_vertical():
    tbl = create_simple_table(rows=2, cols=2, width=200.0)
    _set_cell_text(tbl.rows[0].cells[0], "Top")
    _set_cell_text(tbl.rows[1].cells[0], "Bottom")

    # Merge col 0 across row 0 and row 1
    merged = merge_cells(tbl, r0=0, r1=1, c0=0, c1=0)
    assert merged.tc_pr.v_merge == "restart"
    assert tbl.rows[1].cells[0].tc_pr.v_merge == "continue"
    full_text = _cell_text(merged)
    assert "Top" in full_text
    assert "Bottom" in full_text


def test_split_cells():
    tbl = create_simple_table(rows=2, cols=2, width=200.0)
    target_cell = tbl.rows[0].cells[0]
    _set_cell_text(target_cell, "Hello")

    # Split into 1 row, 2 cols
    news = split_cells(tbl, target_cell, num_rows=1, num_cols=2)
    assert len(news) == 2
    assert len(tbl.rows[0].cells) == 3
    assert len(tbl.grid) == 3


# ---------------------------------------------------------------------------
# Task 2: Table Layout Engine Tests
# ---------------------------------------------------------------------------


def test_table_layout_dimensions():
    doc = Document()
    tbl = create_simple_table(rows=2, cols=2, width=200.0)
    _set_cell_text(tbl.rows[0].cells[0], "Cell 0,0")
    _set_cell_text(tbl.rows[0].cells[1], "Cell 0,1")
    _set_cell_text(tbl.rows[1].cells[0], "Cell 1,0")
    _set_cell_text(tbl.rows[1].cells[1], "Cell 1,1")

    t_layout = layout_table(tbl, container_width=400.0, doc=doc)
    assert isinstance(t_layout, TableLayout)
    assert len(t_layout.rows) == 2
    assert t_layout.width > 0
    assert t_layout.height > 0
    for r_layout in t_layout.rows:
        assert len(r_layout.cells) == 2
        for c_layout in r_layout.cells:
            assert c_layout.width > 0
            assert c_layout.height > 0


def test_table_layout_vertical_alignment():
    doc = Document()
    tbl = create_simple_table(rows=1, cols=2, width=200.0)
    # Make row height at least 60pt
    tbl.rows[0].tr_pr = RowProperties(h=60.0, h_rule="exact")
    # Cell 0 top aligned, Cell 1 center aligned
    tbl.rows[0].cells[0].tc_pr.v_align = "top"
    tbl.rows[0].cells[1].tc_pr.v_align = "center"
    _set_cell_text(tbl.rows[0].cells[0], "Top")
    _set_cell_text(tbl.rows[0].cells[1], "Center")

    t_layout = layout_table(tbl, container_width=200.0, doc=doc)
    c0 = t_layout.rows[0].cells[0]
    c1 = t_layout.rows[0].cells[1]
    assert c0.content_offset_y == 0.0
    assert c1.content_offset_y > 0.0


def test_table_page_split_and_repeated_header():
    doc = Document()
    tbl = create_simple_table(rows=5, cols=2, width=200.0)
    # Header row
    tbl.rows[0].tr_pr.tbl_header = True
    for r in range(5):
        tbl.rows[r].tr_pr.h = 40.0
        tbl.rows[r].tr_pr.h_rule = "exact"
        _set_cell_text(tbl.rows[r].cells[0], f"Row {r}")

    t_layout = layout_table(tbl, container_width=200.0, doc=doc)

    # Avail height fits only 2 rows on first page (e.g. 90pt -> rows 0, 1)
    p1_layout, next_row = split_table_for_page(
        t_layout, start_row=0, avail_height=90.0, is_first_page=True
    )
    assert p1_layout is not None
    assert len(p1_layout.rows) == 2
    assert next_row == 2

    # Second page: avail height fits 3 rows. Since row 0 is repeated header,
    # it must repeat row 0, plus rows 2 and 3!
    p2_layout, next_row_2 = split_table_for_page(
        t_layout, start_row=2, avail_height=130.0, is_first_page=False
    )
    assert p2_layout is not None
    # Row 0 repeated + Row 2 + Row 3
    assert len(p2_layout.rows) >= 2
    assert p2_layout.rows[0].is_repeated_header is True
    assert p2_layout.rows[0].row_idx == 0


# ---------------------------------------------------------------------------
# Task 3: Pagination Integration Tests
# ---------------------------------------------------------------------------


def test_pagination_with_table():
    doc = Document()
    doc.main.blocks.clear()

    # Paragraph before table
    doc.main.blocks.append(Paragraph(runs=[TextItem("Paragraph before table")]))

    # Add a table
    tbl = create_simple_table(rows=4, cols=2, width=300.0)
    for r in range(4):
        _set_cell_text(tbl.rows[r].cells[0], f"Cell {r},0")
        _set_cell_text(tbl.rows[r].cells[1], f"Cell {r},1")
    doc.main.blocks.append(tbl)

    # Paragraph after table
    doc.main.blocks.append(Paragraph(runs=[TextItem("Paragraph after table")]))

    res = paginate_document(doc)
    assert res.total_pages >= 1
    p0 = res.pages[0]
    # Check that fragments contain table
    table_frags = [
        frag
        for reg in p0.regions
        for col in reg.columns
        for frag in col.fragments
        if getattr(frag, "table_layout", None) is not None
    ]
    assert len(table_frags) == 1
    assert table_frags[0].table_layout.table is tbl
