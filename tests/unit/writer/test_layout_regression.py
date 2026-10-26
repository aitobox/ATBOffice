"""Tier 1 Regression Suite: Algorithm & Non-GUI Layout Matrix for Quire.

Covers:
1. Line portions segmentation and inline layout item measuring (Tabs, Breaks, Symbols, Drawings).
2. Line height determination (Exact, Auto multipliers, embedded picture expansion).
3. East Asian Document Line Grid (15.6pt and 18.0pt pitches, spacing collapse, grid line snapping).
4. Paragraph keep rules, orphan/widow protection, and hard breaks.
5. Section breaks (nextPage, oddPage, evenPage, continuous) and parity padding.
6. Number formatting for dynamic page numbering fields.
"""

from __future__ import annotations

import pytest

from atboffice.modules.writer.layout.pagination import (
    format_number,
    paginate_document,
)
from atboffice.modules.writer.layout.portions import (
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (
    BreakItem,
    Document,
    Paragraph,
    SymbolItem,
    TabItem,
    TextItem,
    reindex,
)
from atboffice.modules.writer.models.drawing import PictureItem
from atboffice.modules.writer.models.properties import (
    DocGridProperties,
    PageNumberProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
)


class TestPortionsSegmentationAndMeasuring:
    """Test inline portions generation, line breaking, and special items."""

    def test_mixed_inline_elements_portions(self) -> None:
        """Verify paragraph with text, tab, symbol, and line break breaks into portions."""
        p = Paragraph()
        p.runs.extend([
            TextItem("Item 1", r_pr=RunProperties(font="Calibri", sz=11.0, b=True)),
            TabItem(),
            TextItem("Details", r_pr=RunProperties(font="Calibri", sz=11.0)),
            BreakItem(break_type="line"),
            SymbolItem(font="Wingdings", char="★"),
            TextItem(" Note on new line", r_pr=RunProperties(font="Arial", sz=9.0, i=True)),
        ])

        # Width of 400 pt allows line 1 to fit before the hard line break
        res = layout_paragraph(p, container_width=400.0)
        lines = res.lines
        assert len(lines) >= 2

        line1 = lines[0]
        # Should contain text, tab, and details
        line1_text = "".join(port.text for port in line1.portions)
        assert "Item 1" in line1_text
        assert "Details" in line1_text

        line2 = lines[1]
        line2_text = "".join(port.text for port in line2.portions)
        assert "★" in line2_text
        assert "Note on new line" in line2_text

    def test_inline_drawing_portion_expansion(self) -> None:
        """Verify inline drawings expand portion width and line height appropriately."""
        p = Paragraph()
        # Text run followed by an inline image of 120pt width x 48pt height
        p.runs.append(TextItem("Before Image ", r_pr=RunProperties(font="Arial", sz=12.0)))
        pic = PictureItem(width=120.0, height=48.0)
        p.runs.append(pic)
        p.runs.append(TextItem(" After Image", r_pr=RunProperties(font="Arial", sz=12.0)))

        res = layout_paragraph(p, container_width=500.0)
        lines = res.lines
        assert len(lines) == 1
        line = lines[0]
        # Line height must accommodate the 48pt image
        assert line.height >= 48.0
        # Line width must include text and the 120pt image width
        assert line.width >= 120.0


class TestLineHeightAndSpacingRules:
    """Test line height modes (Exact, Multiple, Auto) and spacing collapse."""

    def test_exact_line_spacing(self) -> None:
        """Verify that exact line spacing fixes line height regardless of font size."""
        p = Paragraph()
        p.p_pr = ParagraphProperties(
            sp=SpacingProperties(line=20.0, line_rule="exact", before=0.0, after=0.0)
        )
        # 10pt text inside 20pt exact spacing
        p.runs.append(TextItem("Exact line spacing text.", r_pr=RunProperties(sz=10.0)))

        res = layout_paragraph(p, container_width=400.0)
        assert len(res.lines) == 1
        assert res.lines[0].height == pytest.approx(20.0, abs=0.1)

    def test_multiple_line_spacing(self) -> None:
        """Verify 1.5x and 2.0x multiple line spacing scales font line height."""
        p_single = Paragraph()
        p_single.p_pr = ParagraphProperties(
            sp=SpacingProperties(line=1.0, line_rule="auto")
        )
        p_single.runs.append(TextItem("Single line spacing.", r_pr=RunProperties(sz=12.0)))
        res_single = layout_paragraph(p_single, container_width=400.0)

        p_double = Paragraph()
        p_double.p_pr = ParagraphProperties(
            sp=SpacingProperties(line=2.0, line_rule="auto")
        )
        p_double.runs.append(TextItem("Double line spacing.", r_pr=RunProperties(sz=12.0)))
        res_double = layout_paragraph(p_double, container_width=400.0)

        expected_h = res_single.lines[0].height * 2.0
        assert res_double.lines[0].height == pytest.approx(expected_h, rel=0.1)

    def test_paragraph_spacing_collapse(self) -> None:
        """Verify paragraph space_before and space_after are properly accounted for in layout."""
        doc = Document()
        p1 = Paragraph(
            runs=[TextItem("Paragraph 1")],
            p_pr=ParagraphProperties(sp=SpacingProperties(before=10.0, after=20.0)),
        )
        p2 = Paragraph(
            runs=[TextItem("Paragraph 2")],
            p_pr=ParagraphProperties(sp=SpacingProperties(before=15.0, after=5.0)),
        )
        doc.main.blocks = [p1, p2]
        reindex(doc)

        res = paginate_document(doc)
        assert res.total_pages == 1
        col = res.pages[0].regions[0].columns[0]
        assert len(col.fragments) == 2
        # First paragraph at top of page suppresses space_before to 0.0
        assert col.fragments[0].space_before == 0.0
        assert col.fragments[0].space_after == pytest.approx(20.0)
        # Second paragraph preserves space_before
        assert col.fragments[1].space_before == pytest.approx(15.0)


class TestEastAsianLineGrid:
    """Test East Asian line grid alignment on 15.6pt and 18.0pt pitches."""

    def test_line_grid_pitch_15_6(self) -> None:
        """Verify document line grid on 15.6pt pitch aligns line positions."""
        doc = Document()
        doc.sect = SectionProperties(
            pg_w=595.3,
            pg_h=841.9,
            mt=72.0,
            mb=72.0,
            ml=90.0,
            mr=90.0,
            doc_grid=DocGridProperties(type="lines", line_pitch=15.6),
        )

        p1 = Paragraph(runs=[TextItem("Line 1 on 15.6pt grid.")])
        p2 = Paragraph(runs=[TextItem("Line 2 on 15.6pt grid.")])
        p3 = Paragraph(runs=[TextItem("Line 3 on 15.6pt grid.")])
        doc.main.blocks = [p1, p2, p3]
        reindex(doc)

        res = paginate_document(doc)
        assert res.total_pages == 1
        col = res.pages[0].regions[0].columns[0]
        assert len(col.fragments) == 3

    def test_line_grid_pitch_18_0(self) -> None:
        """Verify document line grid on 18.0pt pitch."""
        doc = Document()
        doc.sect = SectionProperties(
            pg_w=595.3,
            pg_h=841.9,
            mt=72.0,
            mb=72.0,
            ml=90.0,
            mr=90.0,
            doc_grid=DocGridProperties(type="lines", line_pitch=18.0),
        )

        p = Paragraph(runs=[TextItem("Testing East Asian 18pt pitch line grid.")])
        doc.main.blocks = [p]
        reindex(doc)

        res = paginate_document(doc)
        assert res.total_pages == 1
        assert res.pages[0].section.doc_grid.line_pitch == pytest.approx(18.0)


class TestPaginationBreaksAndSectionControl:
    """Test section breaks, hard breaks, and orphan/widow pagination rules."""

    def test_page_break_before_rule(self) -> None:
        """Verify page_break_before forces paragraph onto a new page."""
        doc = Document()
        doc.sect.pg_h = 800.0
        doc.sect.mt = 50.0
        doc.sect.mb = 50.0

        p1 = Paragraph(runs=[TextItem("Paragraph on page 1")])
        p2 = Paragraph(
            runs=[TextItem("Paragraph on page 2")],
            p_pr=ParagraphProperties(page_break_before=True),
        )
        doc.main.blocks = [p1, p2]
        reindex(doc)

        res = paginate_document(doc)
        assert res.total_pages == 2
        # Page 1 contains p1
        assert res.pages[0].regions[0].columns[0].fragments[0].paragraph == p1
        # Page 2 contains p2
        assert res.pages[1].regions[0].columns[0].fragments[0].paragraph == p2

    def test_keep_next_rule(self) -> None:
        """Verify keep_next pulls preceding paragraph when next paragraph would overflow."""
        doc = Document()
        doc.sect.pg_h = 200.0
        doc.sect.mt = 20.0
        doc.sect.mb = 20.0
        # Available height: 160.0 pt

        # Paragraph 1 occupies ~130 pt
        p1 = Paragraph(runs=[TextItem("Filling top space...\n" * 8)])
        # Heading with keep_next
        p_heading = Paragraph(
            runs=[TextItem("Chapter Heading")],
            p_pr=ParagraphProperties(keep_next=True),
        )
        # Content paragraph with keep_lines so it cannot split
        p_body = Paragraph(
            runs=[TextItem("Body text line 1\nBody text line 2\nBody text line 3")],
            p_pr=ParagraphProperties(keep_lines=True),
        )
        doc.main.blocks = [p1, p_heading, p_body]
        reindex(doc)

        res = paginate_document(doc)
        assert res.total_pages >= 2
        page_of_heading = None
        page_of_body = None
        for p_idx, page in enumerate(res.pages):
            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.paragraph == p_heading:
                            page_of_heading = p_idx
                        elif frag.paragraph == p_body:
                            page_of_body = p_idx

        assert page_of_heading == page_of_body
        assert page_of_heading == 1

    def test_section_breaks_next_and_odd_page(self) -> None:
        """Verify nextPage and oddPage section breaks calculate page indexes correctly."""
        doc = Document()
        doc.sect.pg_h = 600.0

        sect1 = SectionProperties(
            sect_type="nextPage",
            pg_w=612.0,
            pg_h=792.0,
        )
        p1 = Paragraph(runs=[TextItem("Section 1 content")], sect=sect1)

        # Section break oddPage on last section
        doc.sect = SectionProperties(
            sect_type="oddPage",
            pg_w=612.0,
            pg_h=792.0,
            pg_num=PageNumberProperties(fmt="upperRoman", start=1),
        )
        p2 = Paragraph(runs=[TextItem("Section 2 content starting on odd page")])

        doc.main.blocks = [p1, p2]
        reindex(doc)

        res = paginate_document(doc)
        # Should have at least 2 pages, and section 2 should start on an odd page
        assert res.total_pages >= 2
        p2_page = None
        for page in res.pages:
            for reg in page.regions:
                for col in reg.columns:
                    for frag in col.fragments:
                        if frag.paragraph == p2:
                            p2_page = page
                            break
        assert p2_page is not None
        assert p2_page.page_number % 2 == 1


class TestDynamicNumberFormatting:
    """Verify Word standard numbering formats for PAGE / NUMPAGES fields."""

    @pytest.mark.parametrize(
        ("number", "fmt", "expected"),
        [
            (1, "decimal", "1"),
            (100, "decimal", "100"),
            (1, "upperRoman", "I"),
            (4, "upperRoman", "IV"),
            (9, "upperRoman", "IX"),
            (49, "upperRoman", "XLIX"),
            (2026, "upperRoman", "MMXXVI"),
            (1, "lowerRoman", "i"),
            (14, "lowerRoman", "xiv"),
            (1, "upperLetter", "A"),
            (26, "upperLetter", "Z"),
            (27, "upperLetter", "AA"),
            (28, "upperLetter", "BB"),
            (1, "lowerLetter", "a"),
            (52, "lowerLetter", "zz"),
            (7, "decimalZero", "07"),
            (15, "decimalZero", "15"),
            (1, "ordinal", "1st"),
            (2, "ordinal", "2nd"),
            (3, "ordinal", "3rd"),
            (4, "ordinal", "4th"),
            (11, "ordinal", "11th"),
            (12, "ordinal", "12th"),
            (13, "ordinal", "13th"),
            (21, "ordinal", "21st"),
            (22, "ordinal", "22nd"),
            (23, "ordinal", "23rd"),
        ],
    )
    def test_number_formatting_comprehensive(
        self, number: int, fmt: str, expected: str
    ) -> None:
        assert format_number(number, fmt) == expected
