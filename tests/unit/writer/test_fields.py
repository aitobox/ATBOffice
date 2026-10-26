"""Unit tests for Quire dynamic fields and TOC evaluation system."""

from __future__ import annotations

import datetime

from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    plen,
)
from atboffice.modules.writer.models.field import (
    FieldContext,
    add_bookmark,
    apply_field_formatting,
    bookmark_text,
    ensure_para_bookmark,
    evaluate_field,
    find_bookmarks,
    format_field_date,
    insert_field,
    parse_field_instruction,
    remove_bookmark,
    tokenize_field_instruction,
    update_fields,
)


def test_tokenize_field_instruction() -> None:
    toks = tokenize_field_instruction('TOC \\o "1-3" \\h \\z \\u')
    assert len(toks) == 6
    assert toks[0].v == "TOC"
    assert toks[1].sw == "\\o"
    assert toks[2].v == "1-3"
    assert toks[2].q is True
    assert toks[3].sw == "\\h"
    assert toks[4].sw == "\\z"
    assert toks[5].sw == "\\u"


def test_parse_field_instruction() -> None:
    f = parse_field_instruction('DATE \\@ "yyyy-MM-dd" \\* Upper')
    assert f.type == "DATE"
    assert f.sw.get("\\@") == "yyyy-MM-dd"
    assert "Upper" in f.fmt

    toc = parse_field_instruction('TOC \\o "1-3" \\h')
    assert toc.type == "TOC"
    assert toc.sw.get("\\o") == "1-3"
    assert toc.sw.get("\\h") is True


def test_date_formatting() -> None:
    dt = datetime.datetime(2026, 10, 26, 14, 30, 45)
    assert format_field_date(dt, "yyyy-MM-dd") == "2026-10-26"
    assert format_field_date(dt, "HH:mm:ss") == "14:30:45"
    assert format_field_date(dt, "MMMM d, yyyy") == "October 26, 2026"
    assert "pm" in format_field_date(dt, "h:mm am/pm").lower()


def test_formatting_switches() -> None:
    assert apply_field_formatting("hello world", ["Upper"]) == "HELLO WORLD"
    assert apply_field_formatting("HELLO WORLD", ["Lower"]) == "hello world"
    assert apply_field_formatting("hello world", ["FirstCap"]) == "Hello world"
    assert apply_field_formatting("hello world", ["Caps"]) == "Hello World"
    assert apply_field_formatting(5, ["Roman"]) == "V"
    assert apply_field_formatting(5, ["roman"]) == "v"
    assert apply_field_formatting(1, ["Alphabetic"]) == "A"
    assert apply_field_formatting(2, ["alphabetic"]) == "b"
    assert apply_field_formatting(3, ["Ordinal"]) == "3rd"
    assert apply_field_formatting(21, ["Cardtext"]) == "twenty-one"


def test_dynamic_field_evaluation() -> None:
    doc = Document()
    doc.props["title"] = "Quarterly Report"
    doc.props["creator"] = "Alice"

    ctx = FieldContext(page_number=3, total_pages=10, section_index=0, section_pages=5)

    assert evaluate_field("PAGE", doc, ctx) == "3"
    assert evaluate_field("PAGE \\* Roman", doc, ctx) == "III"
    assert evaluate_field("NUMPAGES", doc, ctx) == "10"
    assert evaluate_field("SECTIONPAGES", doc, ctx) == "5"
    assert evaluate_field("SECTION", doc, ctx) == "1"
    assert evaluate_field("TITLE", doc, ctx) == "Quarterly Report"
    assert evaluate_field("AUTHOR", doc, ctx) == "Alice"


def test_bookmark_management() -> None:
    doc = Document()
    p1 = Paragraph(runs=[TextItem("This is heading one.")])
    p2 = Paragraph(runs=[TextItem("Paragraph content.")])
    doc.main.paras = [p1, p2]

    # Add bookmark around p1
    add_bookmark(doc, "Chapter1", p1, 8, p1, 19)
    bms = find_bookmarks(doc)
    assert "Chapter1" in bms
    assert bookmark_text(doc, "Chapter1") == "heading one"

    # Ensure para bookmark creates anchor
    bm_name = ensure_para_bookmark(doc, p1)
    assert bm_name.startswith("_Toc")
    assert bm_name in find_bookmarks(doc)

    # Calling again returns same bookmark name
    assert ensure_para_bookmark(doc, p1) == bm_name

    # Remove bookmark
    remove_bookmark(doc, "Chapter1")
    assert "Chapter1" not in find_bookmarks(doc)


def test_insert_and_update_fields() -> None:
    doc = Document()
    p = Paragraph(runs=[TextItem("Page: ")])
    doc.main.paras = [p]

    insert_field(p, offset=6, field_type="PAGE", instr="PAGE")
    assert len(p.runs) == 5  # "Page: ", fb, fs, text(""), fe

    # Update fields with ctx page 7
    class MockPagination:
        total_pages = 12
        section_pages = [12]
        pages: list = []

    changed = update_fields(doc, MockPagination())
    assert changed is True
    # Verify cached text was updated to "1" (default page 1)
    assert p.runs[3].text == "1"


def test_toc_generation_and_updating() -> None:
    from atboffice.modules.writer.layout.toc import (
        build_toc,
        collect_toc_entries,
        insert_or_update_toc,
    )
    from atboffice.modules.writer.models.properties import ParagraphProperties

    doc = Document()
    p_intro = Paragraph(runs=[TextItem("Introduction")], p_pr=ParagraphProperties(style="Heading1"))
    p_body1 = Paragraph(runs=[TextItem("Body text...")])
    p_arch = Paragraph(runs=[TextItem("System Architecture")], p_pr=ParagraphProperties(style="Heading2"))
    p_sub = Paragraph(runs=[TextItem("Detailed Design")], p_pr=ParagraphProperties(style="Heading3"))
    doc.main.paras = [p_intro, p_body1, p_arch, p_sub]

    # Test collect TOC entries
    entries = collect_toc_entries(doc, 'TOC \\o "1-2" \\h')
    assert len(entries) == 2
    assert entries[0].text == "Introduction"
    assert entries[0].level == 1
    assert entries[1].text == "System Architecture"
    assert entries[1].level == 2

    # Test build TOC
    toc_blocks = build_toc(doc, 'TOC \\o "1-3" \\h')
    assert len(toc_blocks) == 3
    assert toc_blocks[0].p_pr.style == "TOC1"
    assert toc_blocks[1].p_pr.style == "TOC2"
    assert toc_blocks[2].p_pr.style == "TOC3"

    # Tab stop check
    tab = toc_blocks[0].p_pr.tabs[0]
    assert tab.align == "right"
    assert tab.leader == "dot"

    # Check hyperlink anchor
    assert toc_blocks[0].runs[0].r_pr.link is not None
    assert "anchor" in toc_blocks[0].runs[0].r_pr.link
    assert toc_blocks[0].runs[0].r_pr.link["anchor"].startswith("_Toc")

    # Check insert and update TOC in document
    inserted = insert_or_update_toc(doc, 'TOC \\o "1-3" \\h', at_idx=0)
    assert len(inserted) == 3
    assert doc.main.paras[0].p_pr.style == "TOC1"
    assert len(doc.main.paras) == 7  # 3 TOC + 4 original

    # Updating TOC replaces the existing 3 TOC blocks without duplication
    for run in p_sub.runs:
        if isinstance(run, TextItem):
            run.text = "Updated Design"
    updated = insert_or_update_toc(doc, 'TOC \\o "1-3" \\h')
    assert len(updated) == 3
    assert len(doc.main.paras) == 7
    assert "Updated Design" in doc.main.paras[2].runs[0].text


def test_pagination_with_dynamic_fields_and_toc() -> None:
    from atboffice.modules.writer.layout.pagination import paginate_document
    from atboffice.modules.writer.layout.toc import insert_or_update_toc
    from atboffice.modules.writer.models.document import BreakItem, Story
    from atboffice.modules.writer.models.properties import ParagraphProperties

    doc = Document()
    # Header with PAGE of NUMPAGES
    p_hdr = Paragraph(runs=[TextItem("Page ")])
    insert_field(p_hdr, 5, "PAGE", "PAGE")
    p_hdr.runs.append(TextItem(" of "))
    insert_field(p_hdr, plen(p_hdr), "NUMPAGES", "NUMPAGES")
    doc.hf["header_default"] = Story(kind="header", paras=[p_hdr], blocks=[p_hdr])
    doc.sect.refs["hdr"]["default"] = "header_default"

    # Headings on different pages
    p_toc_placeholder = Paragraph(runs=[TextItem("TOC here")])
    p_break1 = Paragraph(runs=[BreakItem("page")])
    p_ch1 = Paragraph(runs=[TextItem("Chapter 1: The Beginning")], p_pr=ParagraphProperties(style="Heading1"))
    p_break2 = Paragraph(runs=[BreakItem("page")])
    p_ch2 = Paragraph(runs=[TextItem("Chapter 2: The Middle")], p_pr=ParagraphProperties(style="Heading1"))

    doc.main.paras = [p_toc_placeholder, p_break1, p_ch1, p_break2, p_ch2]
    doc.main.blocks = list(doc.main.paras)

    # Insert TOC at index 0
    insert_or_update_toc(doc, 'TOC \\o "1-3" \\h', at_idx=0)

    # Paginate document
    res = paginate_document(doc)
    assert res.total_pages >= 3

    # Check header field evaluation
    assert p_hdr.runs[3].text in ("1", "2", "3")

    # Check that TOC PAGEREF fields were resolved with valid page numbers
    # doc.main.paras[0] is TOC for Chapter 1, which is on page 2
    # doc.main.paras[1] is TOC for Chapter 2, which is on page 3
    toc1_runs = doc.main.paras[0].runs
    page_ref_run = [r for r in toc1_runs if isinstance(r, TextItem) and r.text.isdigit()]
    assert len(page_ref_run) > 0
    assert page_ref_run[-1].text == "2"


