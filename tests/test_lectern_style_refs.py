"""Tests for Lectern shape style references, color maps, and line dash patterns.

Covers Issue #367:
- tdf126741.pptx: Line color resolves to theme accent1 and painter dash pattern has > 2 segments.
- tdf104201.pptx: Both rectangles fill green and text is white (#FFFFFF via fontRef).
- master-slides.pptx: Subtitle color matches theme green (#30BA78) within 10 per channel.
- bnc887230.pptx: Link color is theme hyperlink color at full opacity (#0000FF, not #CCCCFF).
- idx="0" shapes have Fill.none() and Line.none() applied.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtGui import QColor

from atboffice.modules.presentation.io.pptx_reader import PptxReader, read_pptx
from atboffice.modules.presentation.models.designs import resolve_color
from atboffice.modules.presentation.views.shape_item import DASH_PATTERNS

CORPUS_DIR = Path("tests/docs/powerpoint/pptx")


def test_tdf126741_line_accent1_and_dash_pattern():
    """Verify tdf126741.pptx line color resolves to theme accent1 and dash has > 2 segments."""
    pptx_path = CORPUS_DIR / "libreoffice__tdf126741.pptx"
    pres = read_pptx(pptx_path)
    slide = pres.slides[0]

    connectors = [
        s for s in slide.shapes if s.line.dash == "lgDashDotDot" or "直接连接符" in s.name
    ]
    assert len(connectors) > 0, "Expected at least one connector shape with lgDashDotDot line"

    conn = connectors[0]
    design = pres.designs.get(slide.design_id)
    assert design is not None, "Slide design must be resolved"

    resolved_color = resolve_color(conn.line.color, design=design, clr_map_ovr=slide.clr_map_ovr)
    theme_accent1 = design.colors.accent1
    c_actual = QColor(resolved_color)
    c_accent1 = QColor(theme_accent1)
    assert (
        abs(c_actual.red() - c_accent1.red()) <= 10
    ), f"Red: {c_actual.red()} vs {c_accent1.red()}"
    assert (
        abs(c_actual.green() - c_accent1.green()) <= 10
    ), f"Green: {c_actual.green()} vs {c_accent1.green()}"
    assert (
        abs(c_actual.blue() - c_accent1.blue()) <= 10
    ), f"Blue: {c_actual.blue()} vs {c_accent1.blue()}"

    # Verify dash pattern mapping in ShapeGraphicsItem / DASH_PATTERNS
    dash_pattern = DASH_PATTERNS.get(conn.line.dash)
    assert dash_pattern is not None, f"Dash pattern {conn.line.dash} must be in DASH_PATTERNS"
    assert len(dash_pattern) > 2, f"Expected > 2 segments, got {len(dash_pattern)}"


def test_tdf104201_rectangles_green_and_white_text():
    """Verify tdf104201.pptx rectangles inherit green group fill and white text via fontRef."""
    pptx_path = CORPUS_DIR / "libreoffice__tdf104201.pptx"
    pres = read_pptx(pptx_path)
    slide = pres.slides[0]

    groups = [s for s in slide.shapes if s.type == "group"]
    assert len(groups) > 0, "Expected a group shape"
    grp = groups[0]
    rects = [k for k in grp.kids if "Téglalap" in k.name or k.geom == "rect"]
    assert len(rects) >= 2, f"Expected at least two rectangles in group, got {len(rects)}"

    for rect in rects:
        # Fill should be green #00FF00 inherited from group
        assert rect.fill.type == "solid", f"Expected solid, got {rect.fill.type}"
        assert rect.fill.color.upper() == "#00FF00", f"Expected #00FF00, got {rect.fill.color}"

        # Text runs should have white color (#FFFFFF) from fontRef
        assert rect.text is not None, "Rectangle should have text"
        assert len(rect.text.paragraphs) > 0, "Rectangle text should have paragraphs"
        for p in rect.text.paragraphs:
            for r in p.runs:
                if r.text.strip():
                    assert r.color.upper() == "#FFFFFF", f"Expected #FFFFFF, got {r.color}"


def test_master_slides_subtitle_green():
    """Verify master-slides.pptx subtitle color matches theme green within 10 per channel."""
    pptx_path = CORPUS_DIR / "libreoffice__master-slides.pptx"
    pres = read_pptx(pptx_path)
    slide = pres.slides[0]
    design = pres.designs.get(slide.design_id)
    assert design is not None

    # Check theme accent1 is the green #30BA78
    assert design.colors.accent1.upper() == "#30BA78", f"Accent1: {design.colors.accent1}"

    # Shape 12 subtitle text
    sh12 = next((s for s in slide.shapes if s.id == "12"), None)
    assert sh12 is not None, "Shape 12 must exist"
    assert sh12.text is not None, "Shape 12 must have text"

    first_run = sh12.text.paragraphs[0].runs[0]
    resolved = resolve_color(first_run.color, design=design, clr_map_ovr=slide.clr_map_ovr)
    c_actual = QColor(resolved)
    c_target = QColor("#30BA78")

    assert abs(c_actual.red() - c_target.red()) <= 10, f"Red: {c_actual.red()} vs {c_target.red()}"
    assert (
        abs(c_actual.green() - c_target.green()) <= 10
    ), f"Green: {c_actual.green()} vs {c_target.green()}"
    assert (
        abs(c_actual.blue() - c_target.blue()) <= 10
    ), f"Blue: {c_actual.blue()} vs {c_target.blue()}"


def test_bnc887230_hyperlink_blue():
    """Verify bnc887230.pptx link color is theme hyperlink blue #0000FF, not #CCCCFF."""
    pptx_path = CORPUS_DIR / "libreoffice__bnc887230.pptx"
    pres = read_pptx(pptx_path)
    slide = pres.slides[0]
    design = pres.designs.get(slide.design_id)
    assert design is not None

    link_runs = []
    for sh in slide.shapes:
        if sh.text:
            for p in sh.text.paragraphs:
                for r in p.runs:
                    if r.link:
                        link_runs.append(r)

    assert len(link_runs) > 0, "Expected at least one run with hyperlink"
    for r in link_runs:
        assert r.link == "mailto:info@foo.com"
        assert r.underline is True
        resolved = resolve_color(r.color, design=design, clr_map_ovr=slide.clr_map_ovr)
        assert resolved.upper() == "#0000FF", f"Expected #0000FF, got {resolved}"
        # Ensure it does not resolve to lavender
        assert resolved.upper() != "#CCCCFF"


def test_idx_zero_no_fill_no_line():
    """Verify shapes with fillRef idx='0' and lnRef idx='0' have none applied."""
    reader = PptxReader.__new__(PptxReader)
    reader.themes = {}
    reader.theme_fmt = {}

    style_xml = ET.fromstring("""
        <p:style xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <a:lnRef idx="0"/>
            <a:fillRef idx="0"/>
            <a:fontRef idx="minor"/>
        </p:style>
    """)

    fill, line, font_color, font_type = reader._parse_style_refs(style_xml)
    assert fill is not None
    assert fill.type == "none", f"Expected Fill.none() for idx=0, got {fill}"
    assert line is not None
    assert line.type == "none", f"Expected Line.none() for idx=0, got {line}"
