"""Tests for Quire table layout: nested tables, table indent, style borders (issue #373)."""

from __future__ import annotations

import pytest

from atboffice.modules.writer.layout.portions import ParagraphLayout
from atboffice.modules.writer.layout.table_layout import (
    TableLayout,
    layout_table,
    resolve_table_style_props,
)
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import BorderProperties
from atboffice.modules.writer.models.styles import Style

FIXTURES = "tests/docs/word/docx/"


def _para(text: str) -> Paragraph:
    return Paragraph(runs=[TextItem(text)])


def _table(blocks: list, grid: list[float] | None = None) -> Table:
    tbl = Table()
    tbl.grid = grid or [200.0]
    tbl.rows = [Row(cells=[Cell(blocks=blocks)])]
    return tbl


def _iter_tables(tl: TableLayout):
    yield tl
    for rl in tl.rows:
        for cl in rl.cells:
            for item in cl.block_layouts:
                if isinstance(item, TableLayout):
                    yield from _iter_tables(item)


def _texts(tl: TableLayout) -> str:
    out: list[str] = []
    for t in _iter_tables(tl):
        for rl in t.rows:
            for cl in rl.cells:
                for item in cl.block_layouts:
                    if isinstance(item, ParagraphLayout):
                        for line in item.lines:
                            out.extend(po.text or "" for po in line.portions)
    return "".join(out)


def test_nested_table_lays_out_paragraph_and_inner_table() -> None:
    doc = Document()
    inner = _table([_para("inner")], grid=[100.0])
    outer = _table([_para("outer"), inner])
    tl = layout_table(outer, 400.0, doc)

    cl = tl.rows[0].cells[0]
    kinds = [type(i) for i in cl.block_layouts]
    assert kinds == [ParagraphLayout, TableLayout]
    assert len(cl.block_tops) == 2
    p_layout, t_layout = cl.block_layouts
    # The inner table sits below the paragraph, and the cell grows to contain it.
    p_bottom = p_layout.effective_space_before + p_layout.height + p_layout.effective_space_after
    assert cl.block_tops[1] >= cl.block_tops[0] + p_bottom - 0.01
    assert cl.content_height >= cl.block_tops[1] + t_layout.height
    assert t_layout.width <= cl.width - cl.mar_l - cl.mar_r + 0.01
    assert "inner" in _texts(tl) and "outer" in _texts(tl)
    # paragraphs_layout stays paragraph-only for existing callers.
    assert len(cl.paragraphs_layout) == 1


def test_three_levels_of_nesting() -> None:
    doc = Document()
    lvl3 = _table([_para("deep")], grid=[60.0])
    lvl2 = _table([lvl3], grid=[120.0])
    lvl1 = _table([lvl2], grid=[300.0])
    tl = layout_table(lvl1, 400.0, doc)
    assert len(list(_iter_tables(tl))) == 3
    assert "deep" in _texts(tl)


def test_nested_table_wider_than_cell_is_clamped() -> None:
    doc = Document()
    inner = _table([_para("wide")], grid=[900.0])
    outer = _table([inner], grid=[150.0])
    tl = layout_table(outer, 400.0, doc)
    cl = tl.rows[0].cells[0]
    inner_tl = cl.block_layouts[0]
    assert isinstance(inner_tl, TableLayout)
    assert inner_tl.x + inner_tl.width <= cl.width - cl.mar_l - cl.mar_r + 0.01


def test_direct_table_indent_sets_x() -> None:
    doc = Document()
    tbl = _table([_para("x")])
    tbl.tbl_pr.ind = 36.0
    assert layout_table(tbl, 400.0, doc).x == pytest.approx(36.0)


def test_style_borders_resolved_and_direct_overrides() -> None:
    doc = Document()
    doc.styles["Base"] = Style(
        id="Base",
        name="Base",
        style_type="table",
        tbl_pr={"borders": {"top": BorderProperties(val="single", sz=0.5)}, "ind": 10.0},
    )
    doc.styles["Grid"] = Style(
        id="Grid",
        name="Grid",
        style_type="table",
        based_on="Base",
        tbl_pr={"borders": {"left": BorderProperties(val="single", sz=0.5)}},
    )
    tbl = _table([_para("x")])
    tbl.tbl_pr.style = "Grid"
    tbl.tbl_pr.borders = {"left": BorderProperties(val="double", sz=1.0)}
    props = resolve_table_style_props(doc, tbl)
    assert props["borders"]["top"].val == "single"
    assert props["borders"]["left"].val == "double"
    assert props["ind"] == pytest.approx(10.0)


def test_style_chain_cycle_does_not_hang() -> None:
    doc = Document()
    doc.styles["A"] = Style(id="A", name="A", style_type="table", based_on="B")
    doc.styles["B"] = Style(id="B", name="B", style_type="table", based_on="A")
    tbl = _table([_para("x")])
    tbl.tbl_pr.style = "A"
    assert resolve_table_style_props(doc, tbl)["borders"] == {}


def test_fixture_tdf131260_nested_tables_and_text() -> None:
    from atboffice.modules.writer.io.docx_reader import DocxReader

    doc = DocxReader().read(FIXTURES + "libreoffice__tdf131260.docx")
    top = next(b for b in doc.main.blocks if isinstance(b, Table))
    tl = layout_table(top, 450.0, doc)
    tables = list(_iter_tables(tl))
    assert len(tables) == 3
    assert "Table" in _texts(tl)
    # Each nested table lies inside its parent cell horizontally.
    for t in tables:
        for rl in t.rows:
            for cl in rl.cells:
                for item in cl.block_layouts:
                    if isinstance(item, TableLayout):
                        assert item.x >= -0.01
                        assert item.x + item.width <= cl.width - cl.mar_l - cl.mar_r + 0.01
    # TableGrid style borders reach the outer cells.
    outer_cell = tl.rows[0].cells[0]
    assert outer_cell.borders["top"].val == "single"


def test_fixture_tdf132802_indent_and_black_borders() -> None:
    from atboffice.modules.writer.io.docx_reader import DocxReader

    doc = DocxReader().read(FIXTURES + "libreoffice__tdf132802.docx")
    tbl = next(b for b in doc.main.blocks if isinstance(b, Table))
    assert tbl.tbl_pr.ind == pytest.approx(36.0)
    tl = layout_table(tbl, 450.0, doc)
    assert tl.x == pytest.approx(36.0)
    bd = tl.rows[0].cells[0].borders["left"]
    assert bd.val == "single"
    assert bd.color == "auto"


def test_auto_border_color_paints_black(qtbot) -> None:
    from PySide6.QtGui import QColor

    from atboffice.modules.writer.views.canvas_view import WriterCanvasView

    view = WriterCanvasView()
    qtbot.addWidget(view)
    pen = view._get_border_pen(BorderProperties(val="single", color="auto"), 1.0)
    assert pen is not None
    assert pen.color() == QColor(0, 0, 0)


def test_iter_table_paragraphs_reaches_nested_paragraphs_in_order() -> None:
    from atboffice.modules.writer.layout.table_layout import iter_table_paragraphs

    doc = Document()
    before, deep, after = _para("before"), _para("deep"), _para("after")
    outer = _table([before, _table([deep], grid=[100.0]), after])
    outer.tbl_pr.ind = 20.0
    tl = layout_table(outer, 400.0, doc)
    found = list(iter_table_paragraphs(tl, tl.x, 0.0))
    assert [p.id for p, *_ in found] == [before.id, deep.id, after.id]
    tops = [top for _, _, top, _ in found]
    assert tops == sorted(tops)
    # Paragraph after the nested table sits below it; nested text is further right.
    assert found[1][3] > found[0][3]
    assert found[0][3] >= 20.0


def test_unknown_style_falls_back_to_document_default_table_style() -> None:
    doc = Document()
    doc.styles["DocDefault"] = Style(
        id="DocDefault",
        name="Normal Table",
        style_type="table",
        builtin=False,
        is_default=True,
        tbl_pr={"ind": 5.0},
    )
    tbl = _table([_para("x")])
    tbl.tbl_pr.style = "MissingStyle"
    assert resolve_table_style_props(doc, tbl)["ind"] == pytest.approx(5.0)
