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


def test_explicit_zero_spacing_overrides_doc_defaults() -> None:
    """Explicit w:after="0" and w:line="240" override docDefaults without clobbering before."""
    from atboffice.vfs import etree as ET

    from atboffice.modules.writer.io.docx_reader import DocxReader
    from atboffice.modules.writer.models.properties import ParagraphProperties, SpacingProperties
    from atboffice.modules.writer.models.styles import resolve_p_props

    doc = Document()
    doc.defaults["p_pr"] = ParagraphProperties(
        sp=SpacingProperties(before=12.0, after=10.0, line=1.15, line_rule="auto")
    )
    reader = DocxReader()
    p_pr_xml = ET.fromstring(
        '<w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        "</w:pPr>"
    )
    p = _para("compact")
    p.p_pr = reader._parse_p_pr(p_pr_xml)

    resolved = resolve_p_props(doc, p)
    assert resolved.sp.before == pytest.approx(12.0)
    assert resolved.sp.after == pytest.approx(0.0)
    assert resolved.sp.line == pytest.approx(1.0)
    assert resolved.sp.line_rule == "auto"


def test_tr_height_omitted_hrule_defaults_to_at_least() -> None:
    """ECMA-376: omitted w:hRule on w:trHeight defaults to atLeast; explicit auto stays auto."""
    from atboffice.vfs import etree as ET

    from atboffice.modules.writer.io.docx_reader import DocxReader

    doc = DocxReader().read(FIXTURES + "libreoffice__tdf131260.docx")
    outer = next(b for b in doc.main.blocks if isinstance(b, Table))
    middle = next(b for b in outer.rows[0].cells[0].blocks if isinstance(b, Table))
    inner = next(b for b in middle.rows[0].cells[0].blocks if isinstance(b, Table))
    assert inner.rows[0].tr_pr.h == pytest.approx(28.5)
    assert inner.rows[0].tr_pr.h_rule == "atLeast"

    reader = DocxReader()
    tbl_xml = ET.fromstring(
        '<w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:tblGrid><w:gridCol w:w=\"2000\"/></w:tblGrid>"
        '<w:tr><w:trPr><w:trHeight w:val="500" w:hRule="auto"/></w:trPr>'
        "<w:tc><w:p/></w:tc></w:tr>"
        "<w:tr><w:trPr><w:trHeight/></w:trPr>"
        "<w:tc><w:p/></w:tc></w:tr>"
        "</w:tbl>"
    )
    parsed = reader._parse_table(tbl_xml)
    assert parsed.rows[0].tr_pr.h == pytest.approx(25.0)
    assert parsed.rows[0].tr_pr.h_rule == "auto"
    assert parsed.rows[1].tr_pr.h is None
    assert parsed.rows[1].tr_pr.h_rule == "auto"


def test_table_style_p_pr_overrides_doc_defaults_and_default_normal() -> None:
    """Table style pPr overrides docDefaults and default Normal; non-default styles win."""
    from atboffice.modules.writer.models.properties import ParagraphProperties, SpacingProperties
    from atboffice.modules.writer.models.styles import resolve_p_props

    doc = Document()
    doc.defaults["p_pr"] = ParagraphProperties(
        sp=SpacingProperties(after=10.0, line=1.15, line_rule="auto")
    )
    doc.styles["TableGrid"] = Style(
        id="TableGrid",
        name="Table Grid",
        style_type="table",
        based_on="TableNormal",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(
                after=0.0,
                line=1.0,
                line_rule="auto",
                after_explicit=True,
                line_explicit=True,
                line_rule_explicit=True,
            )
        ),
        tbl_pr={"cell_mar": {"t": 3.0, "b": 4.0, "l": 5.4, "r": 5.4}},
    )

    p_normal = _para("normal cell")
    p_heading = Paragraph(
        runs=[TextItem("heading cell")],
        p_pr=ParagraphProperties(style="Heading1"),
    )
    tbl = _table([p_normal, p_heading])
    tbl.tbl_pr.style = "TableGrid"

    props = resolve_table_style_props(doc, tbl)
    assert props["cell_mar"]["t"] == pytest.approx(3.0)
    assert props["cell_mar"]["b"] == pytest.approx(4.0)

    ctx = {"tbl_p_pr": props["p_pr"], "tbl_r_pr": props["r_pr"]}
    res_normal = resolve_p_props(doc, p_normal, context=ctx)
    assert res_normal.sp.after == pytest.approx(0.0)
    assert res_normal.sp.line == pytest.approx(1.0)

    res_heading = resolve_p_props(doc, p_heading, context=ctx)
    assert res_heading.sp.after == pytest.approx(3.0)

    tl = layout_table(tbl, 400.0, doc)
    cl = tl.rows[0].cells[0]
    assert cl.mar_t == pytest.approx(3.0)
    assert cl.mar_b == pytest.approx(4.0)
    assert cl.paragraphs_layout[0].effective_space_after == pytest.approx(0.0)
    assert cl.paragraphs_layout[1].effective_space_after == pytest.approx(3.0)


def test_nested_table_row_heights_and_padding_applied_once() -> None:
    """Row heights and cell padding apply once per nesting level without outer style bleed."""
    from atboffice.modules.writer.models.properties import (
        ParagraphProperties,
        RowProperties,
        SpacingProperties,
        TableProperties,
    )

    doc = Document()
    doc.defaults["p_pr"] = ParagraphProperties(
        sp=SpacingProperties(after=10.0, line=1.15, line_rule="auto")
    )
    doc.styles["TableGrid"] = Style(
        id="TableGrid",
        name="Table Grid",
        style_type="table",
        based_on="TableNormal",
        p_pr=ParagraphProperties(
            sp=SpacingProperties(
                after=0.0,
                line=1.0,
                line_rule="auto",
                after_explicit=True,
                line_explicit=True,
                line_rule_explicit=True,
            )
        ),
    )

    inner_para = Paragraph(
        runs=[TextItem("inner")],
        p_pr=ParagraphProperties(
            sp=SpacingProperties(after=0.0, line=1.0, after_explicit=True, line_explicit=True)
        ),
    )
    inner = Table(
        grid=[120.0],
        tbl_pr=TableProperties(
            style="TableNormal",
            cell_mar={"t": 4.0, "b": 5.0, "l": 5.4, "r": 5.4},
            cell_mar_explicit=True,
        ),
        rows=[
            Row(
                cells=[Cell(blocks=[inner_para])],
                tr_pr=RowProperties(h=30.0, h_rule="atLeast"),
            )
        ],
    )
    outer_before = _para("before")
    outer_after = _para("after")
    outer = Table(
        grid=[300.0],
        tbl_pr=TableProperties(
            style="TableGrid",
            cell_mar={"t": 6.0, "b": 8.0, "l": 5.4, "r": 5.4},
            cell_mar_explicit=True,
        ),
        rows=[Row(cells=[Cell(blocks=[outer_before, inner, outer_after])])],
    )

    tl = layout_table(outer, 400.0, doc)
    outer_cl = tl.rows[0].cells[0]
    p_before_l, inner_tl, p_after_l = outer_cl.block_layouts
    assert isinstance(p_before_l, ParagraphLayout)
    assert isinstance(inner_tl, TableLayout)
    assert isinstance(p_after_l, ParagraphLayout)

    # Outer TableGrid suppresses docDefaults space_after on outer cell paragraphs.
    assert p_before_l.effective_space_after == pytest.approx(0.0)
    assert p_after_l.effective_space_after == pytest.approx(0.0)

    # Inner table honors trHeight=30 atLeast and applies its own padding once.
    inner_cl = inner_tl.rows[0].cells[0]
    inner_p_l = inner_cl.paragraphs_layout[0]
    expected_inner_content = 4.0 + inner_p_l.height + 5.0
    assert inner_cl.content_height == pytest.approx(expected_inner_content)
    assert inner_tl.height == pytest.approx(max(30.0, expected_inner_content))

    # Outer cell applies its own top/bottom padding once around before + inner + after.
    expected_outer_h = 6.0 + p_before_l.height + inner_tl.height + p_after_l.height + 8.0
    assert outer_cl.content_height == pytest.approx(expected_outer_h)
    assert tl.height == pytest.approx(expected_outer_h)
    assert outer_cl.block_tops[1] == pytest.approx(p_before_l.height)
    assert outer_cl.block_tops[2] == pytest.approx(p_before_l.height + inner_tl.height)

    # Outer TableGrid pPr must not bleed into an inner TableNormal cell without direct spacing.
    inner_default_para = _para("inherits docDefaults")
    inner_no_override = Table(
        grid=[120.0],
        tbl_pr=TableProperties(style="TableNormal"),
        rows=[Row(cells=[Cell(blocks=[inner_default_para])])],
    )
    outer_wrap = Table(
        grid=[300.0],
        tbl_pr=TableProperties(style="TableGrid"),
        rows=[Row(cells=[Cell(blocks=[inner_no_override])])],
    )
    wrap_tl = layout_table(outer_wrap, 400.0, doc)
    nested_tl = wrap_tl.rows[0].cells[0].block_layouts[0]
    assert isinstance(nested_tl, TableLayout)
    assert nested_tl.rows[0].cells[0].paragraphs_layout[0].effective_space_after == pytest.approx(
        10.0
    )


def test_fixture_tdf131260_nested_table_heights_match_reference() -> None:
    """libreoffice__tdf131260.docx outer and nested table heights match .vibeoffice within 5 px."""
    from atboffice.modules.writer.io.docx_reader import DocxReader

    doc = DocxReader().read(FIXTURES + "libreoffice__tdf131260.docx")
    top = next(b for b in doc.main.blocks if isinstance(b, Table))
    tl = layout_table(top, 468.0, doc)

    # Reference (.vibeoffice) at 96 DPI (4/3 px/pt):
    # outer=256px (192pt), middle=147px (110.25pt), inner=38px (28.5pt).
    assert abs(tl.height - 192.0) <= 3.75  # <= 5 px at 96 DPI

    outer_cl = tl.rows[0].cells[0]
    middle_idx = next(
        i for i, item in enumerate(outer_cl.block_layouts) if isinstance(item, TableLayout)
    )
    middle_tl = outer_cl.block_layouts[middle_idx]
    assert isinstance(middle_tl, TableLayout)
    assert abs(middle_tl.height - 110.25) <= 3.75

    middle_cl = middle_tl.rows[0].cells[0]
    inner_idx = next(
        i for i, item in enumerate(middle_cl.block_layouts) if isinstance(item, TableLayout)
    )
    inner_tl = middle_cl.block_layouts[inner_idx]
    assert isinstance(inner_tl, TableLayout)
    assert inner_tl.height == pytest.approx(28.5, abs=0.5)

    # Innermost cell has vAlign="bottom" and "Table" fits cleanly below the top without overlap.
    inner_cl = inner_tl.rows[0].cells[0]
    assert inner_cl.v_align == "bottom"
    assert inner_cl.paragraphs_layout[0].effective_space_after == pytest.approx(0.0)
    assert inner_cl.content_offset_y > 0.0
    assert inner_cl.content_offset_y + inner_cl.content_height <= inner_cl.height + 0.01

    # Verify sibling blocks never overlap vertically at any nesting level.
    for cell_layout in (outer_cl, middle_cl):
        prev_bottom = 0.0
        for item, top_y in zip(cell_layout.block_layouts, cell_layout.block_tops):
            assert top_y >= prev_bottom - 0.01
            if isinstance(item, TableLayout):
                prev_bottom = top_y + item.height
            else:
                prev_bottom = (
                    top_y + item.effective_space_before + item.height + item.effective_space_after
                )
