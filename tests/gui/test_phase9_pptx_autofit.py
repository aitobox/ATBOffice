"""Phase 9 PPTX Text Auto-Fitting and Vertical Anchor Alignment Tests.

Verifies:
- Parsing of a:normAutofit attributes (fontScale, lnSpcReduction, has_explicit_font_scale)
- Vertical anchor alignment ("t", "ctr", "b") and anchorCtr parsing and serialization
- a:lstStyle parsing on <p:txBody> and paragraph inheritance of margins, indents, bullets, defRPr
- Regression coverage for libreoffice__TextFittingComparisonWithMSO_3.pptx
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io import read_pptx
from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.slide_canvas import SlideCanvasView, SlideScene
from atboffice.modules.presentation.views.text_editor import solve_norm_autofit_scale

PPTX_PATH = Path("tests/docs/powerpoint/pptx/libreoffice__TextFittingComparisonWithMSO_3.pptx")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test", "-platform", "offscreen"])
    return app


def test_norm_autofit_xml_parsing() -> None:
    """Verify normAutofit fontScale and lnSpcReduction parsing."""
    xml_str = """
    <p:txBody xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
        <a:bodyPr anchor="ctr" anchorCtr="1">
            <a:normAutofit fontScale="85000" lnSpcReduction="15000"/>
        </a:bodyPr>
        <a:p>
            <a:r><a:t>Autofit Text</a:t></a:r>
        </a:p>
    </p:txBody>
    """
    elem = ET.fromstring(xml_str)
    reader = PptxReader(package=None)
    tb = reader._parse_text_body(elem)

    assert tb.autofit == "norm"
    assert abs(tb.font_scale - 0.85) < 1e-4
    assert abs(tb.ln_spc_reduction - 0.15) < 1e-4
    assert tb.has_explicit_font_scale is True
    assert tb.anchor == "ctr"
    assert tb.anchor_ctr is True


def test_vertical_anchor_and_serialization() -> None:
    """Verify anchor variants and dictionary serialization."""
    tb = TextBody(
        anchor="b",
        anchor_ctr=True,
        autofit="norm",
        font_scale=0.925,
        ln_spc_reduction=0.2,
        has_explicit_font_scale=True,
    )
    d = tb.to_dict()
    assert d["anchor"] == "b"
    assert d["anchorCtr"] is True
    assert d["hasExplicitFontScale"] is True
    assert abs(d["fontScale"] - 0.925) < 1e-4
    assert abs(d["lnSpcReduction"] - 0.2) < 1e-4

    restored = TextBody.from_dict(d)
    assert restored.anchor == "b"
    assert restored.anchor_ctr is True
    assert restored.has_explicit_font_scale is True
    assert abs(restored.font_scale - 0.925) < 1e-4
    assert abs(restored.ln_spc_reduction - 0.2) < 1e-4


def test_lst_style_parsing_and_paragraph_inheritance() -> None:
    """Verify <a:lstStyle> on <p:txBody> correctly cascades to paragraphs."""
    xml_str = """
    <p:txBody xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
        <a:bodyPr/>
        <a:lstStyle>
            <a:lvl1pPr marL="228600" indent="-228600" algn="ctr">
                <a:buChar char="•"/>
                <a:defRPr sz="2400">
                    <a:latin typeface="Helvetica"/>
                </a:defRPr>
            </a:lvl1pPr>
        </a:lstStyle>
        <a:p>
            <a:r><a:t>Bullet Item</a:t></a:r>
        </a:p>
    </p:txBody>
    """
    elem = ET.fromstring(xml_str)
    reader = PptxReader(package=None)
    tb = reader._parse_text_body(elem)

    assert len(tb.paragraphs) == 1
    p = tb.paragraphs[0]
    assert p.props.get("algn") == "ctr"
    assert abs(p.props.get("marL") - 18.0) < 1e-2
    assert abs(p.props.get("indent") - (-18.0)) < 1e-2
    assert p.props.get("bu", {}).get("t") == "char"
    assert p.props.get("bu", {}).get("ch") == "•"

    run = p.runs[0]
    assert run.size == 24.0
    assert run.font == "Helvetica"


def test_solve_norm_autofit_scale() -> None:
    """Verify solve_norm_autofit_scale produces reasonable scale factors when text overflows."""
    long_paras = [
        Paragraph(
            level=0,
            runs=[
                TextRun(
                    text=f"Line {i} with a substantial amount of text that overflows the box",
                    size=36.0,
                )
            ],
        )
        for i in range(20)
    ]
    tb = TextBody(paragraphs=long_paras, autofit="norm")
    scale, red = solve_norm_autofit_scale(tb, avail_w=300.0, avail_h=100.0)
    assert 0.2 <= scale < 1.0
    assert 0.0 <= red <= 0.2


def test_slide_canvas_view_scrollbars_disabled(qapp: QApplication) -> None:
    """Verify SlideCanvasView has scrollbars turned off to prevent canvas viewport clipping."""
    view = SlideCanvasView()
    assert view.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert view.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_mso3_text_fitting_document_load(qapp: QApplication) -> None:
    """Verify TextFittingComparisonWithMSO_3.pptx loads with correct autofit and renders."""
    if not PPTX_PATH.exists():
        pytest.skip(f"Test presentation {PPTX_PATH} not found")

    pres = read_pptx(str(PPTX_PATH))
    assert len(pres.slides) >= 1
    slide = pres.slides[0]

    # Find the shape with id=11
    s11 = next((s for s in slide.shapes if s.id == "11" or s.id == 11), None)
    assert s11 is not None, "Shape 11 not found in slide"
    assert s11.text is not None

    tb = s11.text
    assert tb.autofit == "norm"
    assert abs(tb.font_scale - 0.925) < 1e-3
    assert abs(tb.ln_spc_reduction - 0.2) < 1e-3
    assert tb.has_explicit_font_scale is True

    # Paragraphs should have inherited marL=18, indent=-18, and bu char '•'
    p0 = tb.paragraphs[0]
    assert abs(p0.props.get("marL", 0) - 18.0) < 1e-2
    assert abs(p0.props.get("indent", 0) - (-18.0)) < 1e-2
    assert p0.props.get("bu", {}).get("t") == "char"
    assert p0.props.get("bu", {}).get("ch") == "•"

    # Verify rendering offscreen does not crash and renders non-empty
    scene = SlideScene()
    scene.load_slide(slide)
    img = QImage(960, 540, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        scene.render(painter, QRectF(0, 0, 960, 540), QRectF(0, 0, 960, 540))
    finally:
        painter.end()

    assert not img.isNull()
