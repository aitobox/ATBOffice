"""Unit tests for Quire document object model (DOM Tree: Document, Section, Paragraph, Run)."""

import pytest

from atboffice.modules.writer.models.properties import (
    DocGridProperties,
    IndentProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
    TabStop,
    TableProperties,
    RowProperties,
    CellProperties,
    dxa_to_pt,
    format_length,
    parse_length,
    pt_to_dxa,
    PAPER_SIZES,
)
from atboffice.modules.writer.models.document import (
    BookmarkEndItem,
    BookmarkStartItem,
    BreakItem,
    Cell,
    CommentRangeEnd,
    CommentRangeStart,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Row,
    Story,
    SymbolItem,
    TabItem,
    Table,
    TextItem,
    all_paragraphs,
    ilen,
    insert_index,
    locate,
    normalize,
    paras_between,
    plain_text,
    plen,
    ptext,
    reindex,
    sections,
    sect_for,
    slice_runs,
    split_at,
    walk,
)
from atboffice.modules.writer.models.styles import (
    Style,
    builtin_styles,
    merge_p_props,
    merge_r_props,
    resolve_p_props,
    resolve_r_props,
    style_chain,
)


def test_units_and_lengths():
    """Verify length parsing, formatting, and dxa/pt conversions."""
    assert pt_to_dxa(1.0) == 20
    assert pt_to_dxa(72.0) == 1440
    assert dxa_to_pt(1440) == 72.0
    assert dxa_to_pt(20) == 1.0

    assert parse_length("72pt") == 72.0
    assert parse_length("1in") == 72.0
    assert parse_length("1\"") == 72.0
    assert pytest.approx(parse_length("2.54cm"), 0.01) == 72.0
    assert pytest.approx(parse_length("25.4mm"), 0.01) == 72.0

    assert format_length(72.0, "in") == '1"'
    assert format_length(72.0, "pt") == "72 pt"

    assert "A4" in PAPER_SIZES
    assert "Letter" in PAPER_SIZES
    assert PAPER_SIZES["Letter"] == (612.0, 792.0)
    assert pytest.approx(PAPER_SIZES["A4"][0], 0.1) == 595.3
    assert pytest.approx(PAPER_SIZES["A4"][1], 0.1) == 841.9


def test_properties_defaults():
    """Verify default properties for section, paragraph, and run."""
    sect = SectionProperties()
    assert sect.pg_w == 612.0
    assert sect.pg_h == 792.0
    assert sect.orient == "portrait"
    assert sect.mt == 72.0
    assert sect.mb == 72.0
    assert sect.ml == 90.0
    assert sect.mr == 90.0
    assert sect.doc_grid.type == "lines"
    assert sect.doc_grid.line_pitch == 15.6

    p_pr = ParagraphProperties()
    assert p_pr.style == "Normal"
    assert p_pr.jc == "left"
    assert p_pr.widow_control is True

    r_pr = RunProperties()
    assert r_pr.sz == 12.0
    assert r_pr.font == "Times New Roman"
    assert r_pr.b is False
    assert r_pr.i is False


def test_run_items_and_lengths():
    """Verify item types, zero-length markers, and text extraction."""
    t1 = TextItem(text="Hello ")
    tab = TabItem()
    t2 = TextItem(text="World")
    br = BreakItem(break_type="line")
    bm_s = BookmarkStartItem(name="bm1", bookmark_id=1)
    bm_e = BookmarkEndItem(bookmark_id=1)
    fb = FieldBeginItem(field_type="PAGE", instr="PAGE")
    fs = FieldSeparateItem()
    fe = FieldEndItem()

    assert ilen(t1) == 6
    assert ilen(tab) == 1
    assert ilen(t2) == 5
    assert ilen(br) == 1
    assert ilen(bm_s) == 0
    assert ilen(bm_e) == 0
    assert ilen(fb) == 0
    assert ilen(fs) == 0
    assert ilen(fe) == 0

    p = Paragraph(runs=[bm_s, t1, tab, t2, br, fb, TextItem(text="1"), fe, bm_e])
    assert plen(p) == 6 + 1 + 5 + 1 + 1  # 14
    assert ptext(p) == "Hello \tWorld\n1"
    assert plain_text(p) == "Hello \tWorld\n1"


def test_locate_split_and_insert_index():
    """Verify character offset location, splitting at boundary/internal, and insert index."""
    t1 = TextItem(text="ABCDE")  # 0..5
    t2 = TextItem(text="FGHIJ")  # 5..10
    p = Paragraph(runs=[t1, t2])

    loc = locate(p, 3)
    assert loc == (0, 3, 0)

    loc2 = locate(p, 7)
    assert loc2 == (1, 2, 5)

    # Split at offset 3
    idx = split_at(p, 3)
    assert idx == 1
    assert len(p.runs) == 3
    assert p.runs[0].text == "ABC"
    assert p.runs[1].text == "DE"
    assert p.runs[2].text == "FGHIJ"

    # Insert index with markers
    p2 = Paragraph(runs=[TextItem(text="Test"), BookmarkEndItem(bookmark_id=1), TextItem(text="Content")])
    ins_idx = insert_index(p2, 4)
    assert ins_idx == 2  # After the bookmark end


def test_normalize_and_slice():
    """Verify run normalization (merging adjacent runs with same format) and slicing."""
    r_pr_a = RunProperties(b=True, sz=14.0)
    r_pr_b = RunProperties(b=True, sz=14.0)
    r_pr_c = RunProperties(i=True, sz=14.0)

    p = Paragraph(runs=[
        TextItem(text="Hello ", r_pr=r_pr_a),
        TextItem(text="World", r_pr=r_pr_b),
        TextItem(text="", r_pr=r_pr_b),
        TextItem(text="!", r_pr=r_pr_c),
    ])

    normalize(p)
    assert len(p.runs) == 2
    assert p.runs[0].text == "Hello World"
    assert p.runs[0].r_pr.b is True
    assert p.runs[1].text == "!"
    assert p.runs[1].r_pr.i is True

    # Slicing
    sliced = slice_runs(p, 6, 12)  # "World!"
    assert len(sliced) == 2
    assert sliced[0].text == "World"
    assert sliced[1].text == "!"


def test_document_structure_and_traversal():
    """Verify document tree creation, walking, reindexing, and paragraph query."""
    doc = Document()
    p1 = Paragraph(runs=[TextItem(text="First paragraph")])
    p2 = Paragraph(runs=[TextItem(text="Cell paragraph")])
    cell = Cell(blocks=[p2])
    row = Row(cells=[cell])
    table = Table(rows=[row], grid=[200.0])
    p3 = Paragraph(runs=[TextItem(text="Third paragraph")])

    doc.main.blocks = [p1, table, p3]

    paras = all_paragraphs(doc)
    assert len(paras) == 3
    assert paras[0] == p1
    assert paras[1] == p2
    assert paras[2] == p3

    between = paras_between(doc, p1, p3)
    assert between == [p1, p2, p3]

    visited = []
    walk(doc.main, lambda block, cont, i, story, parents: visited.append(block))
    assert visited == [p1, table, p2, p3]


def test_sections_and_breaks():
    """Verify section extraction and sect_for resolution."""
    doc = Document()
    sect1 = SectionProperties(orient="landscape")
    p1 = Paragraph(runs=[TextItem(text="Sect 1 end")], sect=sect1)
    p2 = Paragraph(runs=[TextItem(text="Sect 2 content")])
    doc.main.blocks = [p1, p2]

    secs = sections(doc)
    assert len(secs) == 2
    assert secs[0]["sect"].orient == "landscape"
    assert secs[0]["end_para"] == p1
    assert secs[1]["sect"].orient == "portrait"
    assert secs[1]["end_para"] is None

    assert sect_for(doc, p1).orient == "landscape"
    assert sect_for(doc, p2).orient == "portrait"


def test_styles_and_cascade_resolution():
    """Verify built-in Word 2003 styles, style chains, and cascading property resolution."""
    styles = builtin_styles()
    assert "Normal" in styles
    assert "Heading1" in styles
    assert "Heading2" in styles
    assert "TableGrid" in styles

    doc = Document()
    chain = style_chain(doc, "Heading2")
    assert [s.id for s in chain] == ["Normal", "Heading2"]

    p = Paragraph(runs=[TextItem(text="Heading title")], p_pr=ParagraphProperties(style="Heading1"))
    resolved_p = resolve_p_props(doc, p)
    assert resolved_p.keep_next is True
    assert resolved_p.outline_level == 0

    resolved_r = resolve_r_props(doc, p, p.runs[0])
    assert resolved_r.font == "Arial"
    assert resolved_r.b is True
    assert resolved_r.sz == 16.0
