"""Unit tests for Quire Word table margins, borders, and layout line metrics (Issue #282)."""

import tempfile
from pathlib import Path
import pytest
from PySide6.QtGui import QFont, QFontMetricsF
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.modules.writer.layout.portions import (
    layout_paragraph,
    measure_char_width,
    measure_text_width,
)
from atboffice.modules.writer.layout.table_layout import (
    CellLayout,
    layout_table,
    resolve_cell_borders,
)
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    BorderProperties,
    CellProperties,
    RowProperties,
    TableProperties,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication is available for font metrics."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_table_margins_cascade_and_cell_override():
    """Verify that cell margins cascade: tcMar side overrides tblCellMar side, fallback to table."""
    tbl = Table(
        grid=[100.0, 100.0],
        tbl_pr=TableProperties(cell_mar={"t": 4.0, "b": 6.0, "l": 8.0, "r": 8.0}),
    )
    p1 = Paragraph(runs=[TextItem(text="Cell 1")])
    p2 = Paragraph(runs=[TextItem(text="Cell 2")])

    c1 = Cell(blocks=[p1], tc_pr=CellProperties())
    # c2 overrides top and left margins, inherits bottom and right from table
    c2 = Cell(blocks=[p2], tc_pr=CellProperties(tc_mar={"t": 12.0, "l": 15.0}))

    row = Row(cells=[c1, c2], tr_pr=RowProperties())
    tbl.rows.append(row)

    doc = Document()
    doc.main.blocks.append(tbl)

    tl = layout_table(tbl, container_width=200.0, doc=doc)
    assert len(tl.rows) == 1
    assert len(tl.rows[0].cells) == 2

    cl1 = tl.rows[0].cells[0]
    cl2 = tl.rows[0].cells[1]

    # Cell 1 inherits all margins from table
    assert cl1.mar_t == 4.0
    assert cl1.mar_b == 6.0
    assert cl1.mar_l == 8.0
    assert cl1.mar_r == 8.0

    # Cell 2 has overridden top and left, inherited bottom and right
    assert cl2.mar_t == 12.0
    assert cl2.mar_b == 6.0
    assert cl2.mar_l == 15.0
    assert cl2.mar_r == 8.0


def test_table_border_inheritance_and_resolution():
    """Verify table borders cascading (outer vs insideH/insideV) and cell-level border overrides."""
    tbl_borders = {
        "top": BorderProperties(val="single", sz=1.0, color="#111111"),
        "bottom": BorderProperties(val="single", sz=1.0, color="#222222"),
        "left": BorderProperties(val="single", sz=1.0, color="#333333"),
        "right": BorderProperties(val="single", sz=1.0, color="#444444"),
        "insideH": BorderProperties(val="dashed", sz=0.5, color="#555555"),
        "insideV": BorderProperties(val="dotted", sz=0.5, color="#666666"),
    }

    # Cell (0, 0) in 2x2 table: top=outer top, left=outer left, right=insideV, bottom=insideH
    bds_00 = resolve_cell_borders(
        tbl_borders=tbl_borders,
        cell_borders={},
        row_idx=0,
        col_idx=0,
        rowspan=1,
        span=1,
        num_rows=2,
        num_cols=2,
    )
    assert bds_00["top"].color == "#111111"
    assert bds_00["left"].color == "#333333"
    assert bds_00["right"].val == "dotted"
    assert bds_00["bottom"].val == "dashed"

    # Cell (0, 1) with explicit double right border overrides table outer right border
    bds_01 = resolve_cell_borders(
        tbl_borders=tbl_borders,
        cell_borders={"right": BorderProperties(val="double", sz=2.0, color="#FF0000")},
        row_idx=0,
        col_idx=1,
        rowspan=1,
        span=1,
        num_rows=2,
        num_cols=2,
    )
    assert bds_01["right"].val == "double"
    assert bds_01["right"].color == "#FF0000"
    assert bds_01["left"].val == "dotted"  # insideV


def test_cell_vertical_alignment_offsets():
    """Verify vertical alignment calculations for top, center, and bottom."""
    tbl = Table(
        grid=[100.0],
        tbl_pr=TableProperties(),
    )
    p = Paragraph(runs=[TextItem(text="Short text")])
    c = Cell(blocks=[p], tc_pr=CellProperties(v_align="center"))
    row = Row(cells=[c], tr_pr=RowProperties(h=80.0, h_rule="exact"))
    tbl.rows.append(row)

    doc = Document()
    doc.main.blocks.append(tbl)

    tl = layout_table(tbl, container_width=100.0, doc=doc)
    cl = tl.rows[0].cells[0]
    assert cl.height == 80.0
    assert cl.v_align == "center"
    expected_offset = (80.0 - cl.content_height) / 2.0
    assert abs(cl.content_offset_y - expected_offset) < 0.01

    # Bottom alignment
    c.tc_pr.v_align = "bottom"
    tl_bot = layout_table(tbl, container_width=100.0, doc=doc)
    cl_bot = tl_bot.rows[0].cells[0]
    assert abs(cl_bot.content_offset_y - (80.0 - cl_bot.content_height)) < 0.01


def test_docx_roundtrip_table_margins_and_borders():
    """Verify that tblCellMar, tblBorders, tcMar, and tcBorders survive docx read/write roundtrip."""
    doc = Document()
    tbl = Table(
        grid=[120.0, 120.0],
        tbl_pr=TableProperties(
            cell_mar={"t": 3.0, "b": 4.0, "l": 5.0, "r": 6.0},
            borders={
                "top": BorderProperties(val="single", sz=1.0, color="#123456"),
                "insideH": BorderProperties(val="dashed", sz=0.5, color="#654321"),
            },
        ),
    )
    c1 = Cell(
        blocks=[Paragraph(runs=[TextItem(text="C1")])],
        tc_pr=CellProperties(
            tc_mar={"t": 7.0, "b": 8.0, "l": 9.0, "r": 10.0},
            borders={"left": BorderProperties(val="double", sz=1.5, color="#AABBCC")},
        ),
    )
    c2 = Cell(
        blocks=[Paragraph(runs=[TextItem(text="C2")])],
        tc_pr=CellProperties(),
    )
    row = Row(cells=[c1, c2], tr_pr=RowProperties())
    tbl.rows.append(row)
    doc.main.blocks = [tbl]

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "test_table_roundtrip.docx"
        write_docx(doc, str(docx_path))
        loaded = read_docx(str(docx_path))

        l_tbl = next(b for b in loaded.main.blocks if isinstance(b, Table))
        assert isinstance(l_tbl, Table)

        # Verify tbl_pr.cell_mar
        assert l_tbl.tbl_pr.cell_mar.get("t") == 3.0
        assert l_tbl.tbl_pr.cell_mar.get("b") == 4.0
        assert l_tbl.tbl_pr.cell_mar.get("l") == 5.0
        assert l_tbl.tbl_pr.cell_mar.get("r") == 6.0

        # Verify tbl_pr.borders
        assert "top" in l_tbl.tbl_pr.borders
        assert l_tbl.tbl_pr.borders["top"].val == "single"
        assert "insideH" in l_tbl.tbl_pr.borders
        assert l_tbl.tbl_pr.borders["insideH"].val == "dashed"

        # Verify cell 1 tc_mar and borders
        l_c1 = l_tbl.rows[0].cells[0]
        assert l_c1.tc_pr.tc_mar.get("t") == 7.0
        assert l_c1.tc_pr.tc_mar.get("b") == 8.0
        assert l_c1.tc_pr.tc_mar.get("l") == 9.0
        assert l_c1.tc_pr.tc_mar.get("r") == 10.0
        assert "left" in l_c1.tc_pr.borders
        assert l_c1.tc_pr.borders["left"].val == "double"


def test_font_metrics_advance_precision():
    """Verify font advance calculation is deterministic and scales linearly with font size."""
    w12 = measure_text_width("Cascading Layout Test", 12.0, "Times New Roman")
    w24 = measure_text_width("Cascading Layout Test", 24.0, "Times New Roman")
    assert abs(w24 - w12 * 2.0) < 1e-4
    assert w12 > 50.0
