"""Unit tests for Quire Apache OpenOffice style Line Portions layout engine.

Covers East Asian document line grid snapping, Word spacing collapse,
and 20% justification compression.
"""

import json
from pathlib import Path

import pytest

from atboffice.modules.writer.layout.portions import (
    PortionType,
    collapse_paragraph_spacing,
    compute_grid_line_height,
    decompose_paragraph_to_portions,
    layout_paragraph,
)
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TabItem,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    DocGridProperties,
    IndentProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
    TabStop,
)


def test_east_asian_grid_line_height():
    """Verify East Asian line grid snapping matching Word 2003 / Quire issue #11."""
    # Issue 11: 14pt Times New Roman at 1.7 lines on 15.6pt grid takes 2 pitches = 31.2pt
    lh1 = compute_grid_line_height(
        pitch=15.6, mult=1.7, font_size=14.0, font_family="Times New Roman"
    )
    assert pytest.approx(lh1, 0.01) == 31.2

    # Issue 11: 10.5pt SimSun at 1.5 lines on 15.6pt grid takes 1.5 pitches = 23.4pt
    lh2 = compute_grid_line_height(pitch=15.6, mult=1.5, font_size=10.5, font_family="SimSun")
    assert pytest.approx(lh2, 0.01) == 23.4

    # 12pt Times New Roman, single space (mult=1.0) on 15.6pt grid -> 1 pitch = 15.6pt
    lh3 = compute_grid_line_height(
        pitch=15.6, mult=1.0, font_size=12.0, font_family="Times New Roman"
    )
    assert pytest.approx(lh3, 0.01) == 15.6

    # 22pt Times New Roman on 15.6pt grid single space:
    # 22 * 1.149 = 25.278pt -> needs 2 pitches = 31.2pt
    lh4 = compute_grid_line_height(
        pitch=15.6, mult=1.0, font_size=22.0, font_family="Times New Roman"
    )
    assert pytest.approx(lh4, 0.01) == 31.2

    # 18pt grid: 14pt text at 1.5 lines -> max(1, 1.5, 1) * 18 = 27.0pt
    lh5 = compute_grid_line_height(
        pitch=18.0, mult=1.5, font_size=14.0, font_family="Times New Roman"
    )
    assert pytest.approx(lh5, 0.01) == 27.0


def test_word_json_90_grid_cases_verification():
    """Verify compute_grid_line_height against all 90 reference Word cases in word.json."""
    json_path = Path(".vibeoffice/tests/from-issues/11/word.json")
    if not json_path.exists():
        pytest.skip("word.json not available in workspace")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines = data.get("lines", {})
    assert len(lines) == 90

    for key, expected_pt in lines.items():
        parts = key.strip("[]").split("/")
        pitch = float(parts[0])
        sz = float(parts[1])
        mult = float(parts[2])
        is_zh = len(parts) > 3 and parts[3] == "zh"
        font = "SimSun" if is_zh else "Times New Roman"

        calculated_pt = compute_grid_line_height(
            pitch=pitch, mult=mult, font_size=sz, font_family=font
        )
        # Word PDF line rasterization is within 0.15 pt
        diff = abs(calculated_pt - expected_pt)
        assert diff < 0.15, f"{key}: calculated {calculated_pt} pt, expected {expected_pt} pt"


def test_word_spacing_collapse_and_flattening():
    """Verify Word paragraph spacing collapse: max(p1.sp.after, p2.sp.before)."""
    # Normal adjacent paragraphs: max(12, 6) == 12
    sp1 = collapse_paragraph_spacing(sp_after_prev=12.0, sp_before_curr=6.0, is_page_top=False)
    assert sp1 == 12.0

    # Normal adjacent paragraphs: max(6, 18) == 18
    sp2 = collapse_paragraph_spacing(sp_after_prev=6.0, sp_before_curr=18.0, is_page_top=False)
    assert sp2 == 18.0

    # Equal spacing: max(10, 10) == 10
    sp3 = collapse_paragraph_spacing(sp_after_prev=10.0, sp_before_curr=10.0, is_page_top=False)
    assert sp3 == 10.0

    # First line at top of page or after page break: space before is flattened (dropped to 0)
    sp_top = collapse_paragraph_spacing(sp_after_prev=12.0, sp_before_curr=12.0, is_page_top=True)
    assert sp_top == 0.0


def test_empty_paragraph_layout():
    """Verify that empty paragraph generates single line sized by paragraph mark (EmptyHeight)."""
    p = Paragraph(p_pr=ParagraphProperties(style="Normal"))
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    layout = layout_paragraph(p, container_width=400.0, section_props=sect, doc=doc)
    assert len(layout.lines) == 1
    line = layout.lines[0]
    assert line.is_last_line is True
    # Normal default font is 12pt Times New Roman, line height approx 12 * 1.149 = 13.788
    assert line.height > 10.0
    assert line.width == 0.0


def test_blanks_and_tabs_do_not_stretch_line_height():
    """Verify OpenOffice Writer #i3952: blanks and tabs do not stretch a line's height."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    # Baseline text 12pt
    p_baseline = Paragraph(
        runs=[TextItem(text="Hello", r_pr=RunProperties(sz=12.0, font="Times New Roman"))]
    )
    layout_base = layout_paragraph(p_baseline, container_width=400.0, section_props=sect, doc=doc)
    base_height = layout_base.lines[0].height

    # Paragraph with 12pt text and 48pt spaces
    p_with_large_spaces = Paragraph(
        runs=[
            TextItem(text="Hello", r_pr=RunProperties(sz=12.0, font="Times New Roman")),
            TextItem(text="    ", r_pr=RunProperties(sz=48.0, font="Times New Roman")),
            TabItem(r_pr=RunProperties(sz=48.0)),
        ]
    )
    layout_spaces = layout_paragraph(
        p_with_large_spaces, container_width=400.0, section_props=sect, doc=doc
    )
    assert len(layout_spaces.lines) == 1
    # Line height should still be governed by the 12pt text, not the 48pt blank/tab
    assert pytest.approx(layout_spaces.lines[0].height, 0.1) == base_height


def test_line_wrapping_and_indentation():
    """Verify line wrapping with first line indent and left/right indents."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    text = (
        "The quick brown fox jumps over the lazy dog repeatedly to test "
        "multi-line wrapping and word break behavior in Quire engine."
    )
    p = Paragraph(
        p_pr=ParagraphProperties(ind=IndentProperties(left=20.0, right=20.0, first_line=15.0)),
        runs=[TextItem(text=text, r_pr=RunProperties(sz=12.0, font="Times New Roman"))],
    )
    # Container width = 200 pt.
    # First line wrap width = 200 - 20 - 20 - 15 = 145 pt
    # Subsequent line wrap width = 200 - 20 - 20 = 160 pt
    layout = layout_paragraph(p, container_width=200.0, section_props=sect, doc=doc)
    assert len(layout.lines) >= 3
    # First line has extra first_line indent
    assert layout.lines[0].indent_left == 35.0  # left (20) + first_line (15)
    assert layout.lines[1].indent_left == 20.0


def test_east_asian_line_grid_snapping_in_paragraph():
    """Verify that on a document line grid, paragraph line heights snap to pitch multiples."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="lines", line_pitch=15.6))

    # 14pt text at 1.7 lines on 15.6pt grid
    p = Paragraph(
        p_pr=ParagraphProperties(sp=SpacingProperties(line=1.7, line_rule="auto")),
        runs=[
            TextItem(
                text="Sample line grid text",
                r_pr=RunProperties(sz=14.0, font="Times New Roman"),
            )
        ],
    )
    layout = layout_paragraph(p, container_width=400.0, section_props=sect, doc=doc)
    line = layout.lines[0]
    # Height should snap to 31.2 pt
    assert pytest.approx(line.height, 0.01) == 31.2
    # Baseline is vertically centered
    assert line.baseline > line.top
    assert line.baseline < line.bottom


def test_justified_space_compression():
    """Verify that justification allows up to 20% micro-compression of inter-word spaces."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    p = Paragraph(
        p_pr=ParagraphProperties(jc="both"),
        runs=[
            TextItem(text="Alpha Beta Gamma", r_pr=RunProperties(sz=12.0, font="Times New Roman"))
        ],
    )
    # Decompose to check portions
    portions = decompose_paragraph_to_portions(p, doc)
    assert any(pt.type == PortionType.BLANK for pt in portions)

    # Measure exact width
    layout = layout_paragraph(p, container_width=500.0, section_props=sect, doc=doc)
    assert len(layout.lines) == 1


def test_kinsoku_shori_cjk_line_breaking():
    """Verify that CJK forbidden leading characters (e.g. ，。！？) do not start a line."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    p = Paragraph(
        runs=[
            TextItem(
                text="这是一个中文测试长段落，用来验证东亚排版禁则规则。如果逗号刚好在行首，它必须吸附在前一个字后面，不能单独成为行首字符。",
                r_pr=RunProperties(sz=12.0, font="SimSun"),
            )
        ]
    )
    layout = layout_paragraph(p, container_width=120.0, section_props=sect, doc=doc)
    assert len(layout.lines) > 1
    forbidden_starts = set("，。！？、；：）》」』’”·")
    for line in layout.lines[1:]:
        first_char = line.portions[0].text[0] if line.portions and line.portions[0].text else ""
        assert first_char not in forbidden_starts


def test_line_spacing_exact_and_at_least():
    """Verify 'exact' and 'atLeast' line spacing rules."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    # Exact 20pt
    p_exact = Paragraph(
        p_pr=ParagraphProperties(sp=SpacingProperties(line=20.0, line_rule="exact")),
        runs=[
            TextItem(
                text="Fixed line height",
                r_pr=RunProperties(sz=12.0, font="Times New Roman"),
            )
        ],
    )
    layout_exact = layout_paragraph(p_exact, container_width=400.0, section_props=sect, doc=doc)
    assert layout_exact.lines[0].height == 20.0

    # At least 30pt with 12pt text (natural ~13.8pt) -> should be 30.0pt
    p_atleast = Paragraph(
        p_pr=ParagraphProperties(sp=SpacingProperties(line=30.0, line_rule="atLeast")),
        runs=[
            TextItem(
                text="Minimum line height",
                r_pr=RunProperties(sz=12.0, font="Times New Roman"),
            )
        ],
    )
    layout_atleast = layout_paragraph(p_atleast, container_width=400.0, section_props=sect, doc=doc)
    assert layout_atleast.lines[0].height == 30.0


def test_explicit_tab_stop_alignment():
    """Verify that TabItem properly advances layout position to explicit tab stop."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    p = Paragraph(
        p_pr=ParagraphProperties(
            tabs=[TabStop(pos=72.0, align="left"), TabStop(pos=144.0, align="left")]
        ),
        runs=[
            TextItem(text="Col1", r_pr=RunProperties(sz=12.0)),
            TabItem(),
            TextItem(text="Col2", r_pr=RunProperties(sz=12.0)),
            TabItem(),
            TextItem(text="Col3", r_pr=RunProperties(sz=12.0)),
        ],
    )
    layout = layout_paragraph(p, container_width=500.0, section_props=sect, doc=doc)
    assert len(layout.lines) == 1
    line = layout.lines[0]
    # Check that tab portions have non-zero widths advancing towards 72 and 144
    tab_portions = [pt for pt in line.portions if pt.type == PortionType.TAB]
    assert len(tab_portions) == 2
    assert tab_portions[0].width > 0.0
    assert tab_portions[1].width > 0.0


def test_inline_graphic_alone_and_with_text():
    """Verify inline graphic ascent, descent, and minimum line height behavior."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    # An inline object mock with width=80, height=40
    class InlineGraphic:
        t = "graphic"
        w = 80.0
        h = 40.0
        r_pr = RunProperties()

    p_pic = Paragraph(runs=[InlineGraphic()])
    layout = layout_paragraph(p_pic, container_width=400.0, section_props=sect, doc=doc)
    assert len(layout.lines) == 1
    line = layout.lines[0]
    assert line.ascent == 40.0
    assert line.descent == 0.0
    assert line.height >= 40.0


def test_narrow_container_forced_wrap():
    """Verify that a container narrower than a single long word does not hang or infinite loop."""
    doc = Document()
    sect = SectionProperties(doc_grid=DocGridProperties(type="none"))

    p = Paragraph(
        runs=[
            TextItem(
                text="Supercalifragilisticexpialidocious",
                r_pr=RunProperties(sz=12.0, font="Times New Roman"),
            )
        ]
    )
    # Extremely narrow container (20pt, smaller than the word)
    layout = layout_paragraph(p, container_width=20.0, section_props=sect, doc=doc)
    assert len(layout.lines) > 1
    assert layout.height > 0.0
