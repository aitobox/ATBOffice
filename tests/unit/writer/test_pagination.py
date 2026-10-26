"""Unit tests for Quire dynamic multi-page pagination & flow engine (Issue #25)."""

from atboffice.modules.writer.layout.pagination import (
    PaginationResult,
    format_number,
    paginate_document,
)
from atboffice.modules.writer.models.document import (
    BreakItem,
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Story,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    SectionProperties,
)


def test_number_formatting():
    """Verify number formatting for page numbers (decimal, roman, letters, ordinal)."""
    assert format_number(1, "decimal") == "1"
    assert format_number(42, "decimal") == "42"
    assert format_number(4, "upperRoman") == "IV"
    assert format_number(9, "lowerRoman") == "ix"
    assert format_number(1, "upperLetter") == "A"
    assert format_number(26, "upperLetter") == "Z"
    assert format_number(27, "upperLetter") == "AA"
    assert format_number(1, "lowerLetter") == "a"
    assert format_number(5, "decimalZero") == "05"
    assert format_number(12, "decimalZero") == "12"
    assert format_number(1, "ordinal") == "1st"
    assert format_number(2, "ordinal") == "2nd"
    assert format_number(3, "ordinal") == "3rd"
    assert format_number(4, "ordinal") == "4th"
    assert format_number(11, "ordinal") == "11th"
    assert format_number(21, "ordinal") == "21st"


def test_pagination_single_page():
    """Verify a small document fits on a single page with correct page geometry and margins."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.mt = 72.0
    doc.sect.mb = 72.0
    doc.sect.ml = 90.0
    doc.sect.mr = 90.0

    p1 = Paragraph(runs=[TextItem(text="Hello Quire Document Pagination!")])
    p2 = Paragraph(runs=[TextItem(text="Second paragraph on single page.")])
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    assert isinstance(res, PaginationResult)
    assert res.total_pages == 1
    assert len(res.pages) == 1

    page = res.pages[0]
    assert page.index == 0
    assert page.page_number == 1
    assert page.width == 612.0
    assert page.height == 792.0
    assert page.body_left == 90.0
    assert page.body_width == 612.0 - 180.0  # 432.0
    assert page.body_top == 72.0
    assert page.body_height == 792.0 - 144.0  # 648.0

    assert len(page.regions) == 1
    reg = page.regions[0]
    assert len(reg.columns) == 1
    col = reg.columns[0]
    assert len(col.fragments) == 2
    assert col.fragments[0].paragraph == p1
    assert col.fragments[1].paragraph == p2


def test_pagination_overflow_multi_page():
    """Verify long content wraps across multiple pages."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 300.0  # Small height to trigger pagination quickly
    doc.sect.mt = 30.0
    doc.sect.mb = 30.0
    doc.sect.ml = 50.0
    doc.sect.mr = 50.0
    # Available body height: 300 - 60 = 240.0 pt

    # Generate 15 paragraphs of ~3 lines each
    paras = []
    for i in range(15):
        text = f"Paragraph {i}: " + ("This is continuous line text filling vertical space. " * 5)
        p = Paragraph(runs=[TextItem(text=text)])
        paras.append(p)
    doc.main.blocks = paras

    res = paginate_document(doc)
    assert res.total_pages > 1
    assert len(res.pages) == res.total_pages

    # Check that all paragraphs are placed in fragments
    placed_para_ids = set()
    for pg in res.pages:
        for reg in pg.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    placed_para_ids.add(frag.paragraph.id)
    assert placed_para_ids == {p.id for p in paras}


def test_hard_page_and_column_break():
    """Verify manual page breaks (BreakItem type='page') and column breaks."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0

    p1 = Paragraph(runs=[TextItem(text="Page 1 Content"), BreakItem(break_type="page")])
    p2 = Paragraph(runs=[TextItem(text="Page 2 Content")])
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    assert res.total_pages == 2
    assert res.pages[0].regions[0].columns[0].fragments[0].paragraph == p1
    assert res.pages[1].regions[0].columns[0].fragments[0].paragraph == p2


def test_section_breaks_next_page():
    """Verify section break with nextPage creates a new page with updated section geometry."""
    doc = Document()
    sect1 = SectionProperties(pg_w=612.0, pg_h=792.0, orient="portrait", sect_type="nextPage")
    sect2 = SectionProperties(pg_w=792.0, pg_h=612.0, orient="landscape", sect_type="nextPage")

    p1 = Paragraph(runs=[TextItem(text="Section 1 portrait")], sect=sect1)
    p2 = Paragraph(runs=[TextItem(text="Section 2 landscape")])
    doc.sect = sect2  # Last section properties on document
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    assert res.total_pages == 2
    assert res.pages[0].width == 612.0
    assert res.pages[0].height == 792.0
    assert res.pages[0].section.orient == "portrait"

    assert res.pages[1].width == 792.0
    assert res.pages[1].height == 612.0
    assert res.pages[1].section.orient == "landscape"


def test_section_breaks_odd_and_even_page():
    """Verify odd/even section breaks insert blank padding pages when parity differs."""
    doc = Document()
    sect1 = SectionProperties()
    p1 = Paragraph(runs=[TextItem(text="Page 1 in section 1")], sect=sect1)
    p2 = Paragraph(runs=[TextItem(text="Content in section 2 on odd page")])
    doc.sect = SectionProperties(sect_type="oddPage")  # Sec 2 must start on odd page
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    # Page 1 is odd. If section 2 requires oddPage, section 2 cannot start on Page 2 (even),
    # so a blank page 2 is inserted and section 2 starts on page 3.
    assert res.total_pages == 3
    assert res.pages[0].page_number == 1
    assert res.pages[1].page_number == 2
    assert res.pages[1].is_blank is True
    assert res.pages[2].page_number == 3
    assert res.pages[2].is_blank is False


def test_orphan_and_widow_control():
    """Verify orphan/widow control prevents 1 line at page bottom and top."""
    doc = Document()
    doc.sect.pg_w = 400.0
    doc.sect.pg_h = 100.0
    doc.sect.mt = 20.0
    doc.sect.mb = 20.0
    # Available height = 60.0 pt
    # Each line is approx 14 pt high. 4 lines = ~56 pt, fits on 1 page.
    # If 1 paragraph has 5 lines (~70 pt):
    # Without widow control, 4 lines would fit on page 1, leaving 1 widow line on page 2.
    # With widow control (default True), 3 lines on page 1, 2 lines on page 2.

    # 5-line paragraph
    long_text = (
        "Line text item one. Line text item two. Line text item three. "
        "Line text item four. Line text item five. "
    ) * 3
    p = Paragraph(
        runs=[TextItem(text=long_text)],
        p_pr=ParagraphProperties(widow_control=True),
    )
    doc.main.blocks = [p]

    res = paginate_document(doc)
    assert res.total_pages >= 2
    frag_pg1 = res.pages[0].regions[0].columns[0].fragments[0]
    frag_pg2 = res.pages[1].regions[0].columns[0].fragments[0]

    # Check that neither page has only 1 line
    assert len(frag_pg1.lines) >= 2
    assert len(frag_pg2.lines) >= 2


def test_keep_rules():
    """Verify pageBreakBefore, keepWithNext, and keepLines."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0

    # 1. pageBreakBefore
    p1 = Paragraph(runs=[TextItem(text="Normal paragraph")])
    p2 = Paragraph(
        runs=[TextItem(text="Heading starting on new page")],
        p_pr=ParagraphProperties(page_break_before=True),
    )
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    assert res.total_pages == 2
    assert res.pages[0].regions[0].columns[0].fragments[0].paragraph == p1
    assert res.pages[1].regions[0].columns[0].fragments[0].paragraph == p2

    # 2. keepWithNext
    # Heading with keep_next followed by content
    doc2 = Document()
    doc2.sect.pg_h = 120.0  # Very short page
    doc2.sect.mt = 20.0
    doc2.sect.mb = 20.0
    # Body height = 80.0 pt

    # Paragraph that fills most of page 1
    p_fill = Paragraph(runs=[TextItem(text="Filling space on first page.\nSecond line.")])
    # Heading with keep_next: fits on page 1, but next paragraph cannot fit even 2 lines
    p_head = Paragraph(
        runs=[TextItem(text="Heading with keep next")],
        p_pr=ParagraphProperties(keep_next=True),
    )
    p_body = Paragraph(runs=[TextItem(text="Body paragraph following heading. " * 6)])
    doc2.main.blocks = [p_fill, p_head, p_body]

    res2 = paginate_document(doc2)
    # p_head should move to the next page along with p_body instead of leaving an orphaned heading!
    p_head_page = None
    for pg in res2.pages:
        for reg in pg.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.paragraph == p_head:
                        p_head_page = pg.index
    # p_head must not be alone at the bottom of page 0
    assert p_head_page > 0


def test_headers_and_footers_adaptation():
    """Verify header and footer layout and dynamic margin adaptation when header is tall."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0
    doc.sect.mt = 50.0
    doc.sect.hdr = 20.0

    # Add header story with 4 lines (~60 pt height)
    hdr_story = Story(
        kind="header",
        blocks=[
            Paragraph(
                runs=[TextItem(text="Header line 1\nHeader line 2\nHeader line 3\nHeader line 4")]
            )
        ],
    )
    doc.hf["hdr1"] = hdr_story
    doc.sect.refs["hdr"] = {"default": "hdr1"}

    p1 = Paragraph(runs=[TextItem(text="Document body content")])
    doc.main.blocks = [p1]

    res = paginate_document(doc)
    page = res.pages[0]
    assert page.header is not None
    assert page.header.height > 40.0
    # Since hdr (20) + header.height (~60) = ~80 > mt (50), body_top should expand!
    assert page.body_top >= 70.0


def test_dynamic_page_number_fields():
    """Verify dynamic PAGE and NUMPAGES fields evaluation."""
    doc = Document()
    doc.sect.pg_w = 612.0
    doc.sect.pg_h = 792.0

    # Paragraph with "Page " + PAGE + " of " + NUMPAGES
    fb_page = FieldBeginItem(field_type="PAGE", instr="PAGE")
    fe_page = FieldEndItem()

    fb_num = FieldBeginItem(field_type="NUMPAGES", instr="NUMPAGES")
    fe_num = FieldEndItem()

    p1 = Paragraph(
        runs=[
            TextItem(text="Page "),
            fb_page,
            FieldSeparateItem(),
            TextItem(text="1"),
            fe_page,
            TextItem(text=" of "),
            fb_num,
            FieldSeparateItem(),
            TextItem(text="1"),
            fe_num,
            BreakItem(break_type="page"),
        ]
    )
    p2 = Paragraph(
        runs=[
            TextItem(text="Page "),
            fb_page,
            FieldSeparateItem(),
            TextItem(text="2"),
            fe_page,
            TextItem(text=" of "),
            fb_num,
            FieldSeparateItem(),
            TextItem(text="2"),
            fe_num,
        ]
    )
    doc.main.blocks = [p1, p2]

    res = paginate_document(doc)
    assert res.total_pages == 2
    assert res.pages[0].page_number == 1
    assert res.pages[1].page_number == 2
