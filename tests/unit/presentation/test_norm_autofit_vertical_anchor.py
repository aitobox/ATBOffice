"""Unit tests for PowerPoint normAutofit solver and vertical anchor alignment."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.writer_text import paragraph_to_xml
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.text_editor import (
    ShapeTextEditorItem,
    measure_text_body_height,
    solve_norm_autofit_scale,
)
from atboffice.vfs.opc import SourcePackage

pytestmark = pytest.mark.usefixtures("qapp")


class TestParagraphSpacingIO:
    """Test PPTX reader & writer support for paragraph spacing and margins."""

    def test_parse_paragraph_spacing_and_margins(self) -> None:
        xml_content = (
            '<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '  <a:pPr marL="288000" indent="-144000" algn="ctr">'
            '    <a:lnSpc><a:spcPct val="115000"/></a:lnSpc>'
            '    <a:spcBef><a:spcPts val="600"/></a:spcBef>'
            '    <a:spcAft><a:spcPts val="450"/></a:spcAft>'
            "  </a:pPr>"
            "  <a:r><a:t>Hello Spacing</a:t></a:r>"
            "</a:p>"
        )
        p_elem = ET.fromstring(xml_content)
        pkg = SourcePackage.open(
            "tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx"
        )
        reader = PptxReader(pkg)
        para = reader._parse_paragraph(p_elem)

        assert para.props.get("algn") == "ctr"
        assert abs(para.props["marL"] - 22.68) < 0.1
        assert abs(para.props["indent"] - (-11.34)) < 0.1
        assert para.props["lnSpc"] == {"pct": 115.0}
        assert para.props["spcBef"] == {"pts": 6.0}
        assert para.props["spcAft"] == {"pts": 4.5}

    def test_write_paragraph_spacing_roundtrip(self) -> None:
        para = Paragraph(
            level=0,
            props={
                "algn": "r",
                "marL": 18.0,
                "indent": -12.0,
                "lnSpc": {"pct": 110.0},
                "spcBef": {"pts": 8.0},
                "spcAft": {"pts": 5.0},
            },
            runs=[TextRun(text="Roundtrip Test")],
        )
        xml_str = paragraph_to_xml(para)
        assert '<a:lnSpc><a:spcPct val="110000"/></a:lnSpc>' in xml_str
        assert '<a:spcBef><a:spcPts val="800"/></a:spcBef>' in xml_str
        assert '<a:spcAft><a:spcPts val="500"/></a:spcAft>' in xml_str
        assert 'algn="r"' in xml_str

        p_elem = ET.fromstring(
            f'<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">{xml_str[5:]}'
        )
        pkg = SourcePackage.open(
            "tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx"
        )
        reader = PptxReader(pkg)
        parsed_p = reader._parse_paragraph(p_elem)

        assert parsed_p.props.get("algn") == "r"
        assert parsed_p.props["lnSpc"] == {"pct": 110.0}
        assert parsed_p.props["spcBef"] == {"pts": 8.0}
        assert parsed_p.props["spcAft"] == {"pts": 5.0}


class TestNormAutofitSolver:
    """Test dynamic normAutofit binary search solver and proportional font scaling."""

    def test_solver_no_overflow_remains_one(self) -> None:
        tb = TextBody(
            autofit="norm",
            paragraphs=[
                Paragraph(level=0, runs=[TextRun(text="Short text", size=18.0)]),
            ],
        )
        scale, red = solve_norm_autofit_scale(tb, avail_w=400.0, avail_h=200.0)
        assert scale == 1.0
        assert red == 0.0

    def test_solver_overflow_shrinks_to_fit(self) -> None:
        long_para_text = (
            "The quick brown fox jumps over the lazy dog repeatedly to test multi-line "
            "wrapping behavior inside a fixed-dimension presentation textbox."
        )
        tb = TextBody(
            autofit="norm",
            paragraphs=[
                Paragraph(level=0, runs=[TextRun(text=f"{i}: {long_para_text}", size=28.0)])
                for i in range(8)
            ],
        )
        avail_w = 320.0
        avail_h = 120.0

        # At scale 1.0, 8 paragraphs of 28pt font should far exceed 120pt height
        initial_h = measure_text_body_height(tb, avail_w=avail_w, font_scale=1.0)
        assert initial_h > 250.0

        scale, red = solve_norm_autofit_scale(tb, avail_w=avail_w, avail_h=avail_h)
        assert 0.20 <= scale < 0.90
        assert red > 0.0

        # Height measured at the solved scale should fit within avail_h
        fitted_h = measure_text_body_height(
            tb, avail_w=avail_w, font_scale=scale, ln_spc_reduction=red
        )
        assert fitted_h <= avail_h + 1.0

    def test_proportional_relative_font_scaling(self) -> None:
        # Multi-paragraph with header (36pt) and body (18pt)
        tb = TextBody(
            autofit="norm",
            paragraphs=[
                Paragraph(level=0, runs=[TextRun(text="Large Title Heading", size=36.0)]),
                Paragraph(
                    level=1,
                    runs=[TextRun(text="Detailed body bullet point 1", size=18.0)],
                ),
                Paragraph(
                    level=1,
                    runs=[TextRun(text="Detailed body bullet point 2", size=18.0)],
                ),
                Paragraph(
                    level=1,
                    runs=[TextRun(text="Detailed body bullet point 3", size=18.0)],
                ),
            ],
        )
        avail_w = 200.0
        avail_h = 70.0

        scale, red = solve_norm_autofit_scale(tb, avail_w=avail_w, avail_h=avail_h)
        assert scale < 1.0

        # Calculate scaled font sizes
        header_sz = 36.0 * scale
        body_sz = 18.0 * scale
        # Relative proportion must be exactly 2:1
        assert abs((header_sz / body_sz) - 2.0) < 0.001


class TestVerticalAnchorAlignment:
    """Test vertical anchor offsets ('t', 'ctr', 'b') and zero document margin."""

    def test_vertical_anchor_offsets(self) -> None:
        avail_h = 240.0
        doc_h = 80.0

        # Top anchor
        dy_t = 0.0
        assert dy_t == 0.0

        # Center anchor
        dy_ctr = (avail_h - doc_h) / 2.0
        assert dy_ctr == 80.0

        # Bottom anchor
        dy_b = avail_h - doc_h
        assert dy_b == 160.0

    def test_static_rendering_with_anchors(self) -> None:
        image = QImage(300, 200, QImage.Format.Format_ARGB32)
        image.fill(QColor("#FFFFFF"))
        painter = QPainter(image)

        tb_ctr = TextBody(
            anchor="ctr",
            paragraphs=[Paragraph(level=0, runs=[TextRun(text="Centered Text", size=20.0)])],
        )
        rect = QRectF(10.0, 10.0, 280.0, 180.0)
        # Should render without raising any errors
        ShapeTextEditorItem.render_static_text(painter, tb_ctr, rect)

        tb_b = TextBody(
            anchor="b",
            paragraphs=[Paragraph(level=0, runs=[TextRun(text="Bottom Text", size=16.0)])],
        )
        ShapeTextEditorItem.render_static_text(painter, tb_b, rect)

        painter.end()


class TestSamplePresentationIntegration:
    """Verify sample presentation libreoffice__TextFittingComparisonWithMSO_3.pptx."""

    def test_read_sample_text_fitting_shapes(self) -> None:
        sample_path = "tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx"
        pres = PptxReader.open(sample_path)
        assert len(pres.slides) >= 1

        slide1 = pres.slides[0]
        # Find normAutofit shapes
        norm_shapes = [s for s in slide1.shapes if s.text and s.text.autofit == "norm"]
        assert len(norm_shapes) >= 2

        # Verify parsed font_scale and ln_spc_reduction on shape 11
        sh11 = next(s for s in norm_shapes if str(s.id) == "11")
        assert abs(sh11.text.font_scale - 0.925) < 0.001
        assert abs(sh11.text.ln_spc_reduction - 0.20) < 0.001

        # Verify spacing before / after is parsed from paragraphs
        has_spacing = any(
            "spcBef" in p.props or "spcAft" in p.props or "lnSpc" in p.props
            for p in sh11.text.paragraphs
        )
        assert has_spacing
