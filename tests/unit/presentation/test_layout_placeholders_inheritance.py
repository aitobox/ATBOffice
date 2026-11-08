"""Unit tests for dynamic slide layout and master placeholder inheritance (Issue #312)."""

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.placeholder_resolver import (
    apply_cascading_placeholder_styles,
    evaluate_field_text,
    resolve_unoverridden_placeholders,
)
from atboffice.modules.presentation.models.presentation import HeaderFooterSettings, Presentation
from atboffice.modules.presentation.models.shape import PlaceholderInfo, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.modules.presentation.views.slide_canvas import SlideScene


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_cascading_placeholder_text_styles():
    """Verify placeholder shapes inherit font family, size, color, and alignment from master."""
    design = build_design("default", 960.0, 540.0)

    # 1. Title placeholder
    title_sh = Shape(
        id="s_title",
        type="text",
        placeholder=PlaceholderInfo(type="title", idx=0),
        text=TextBody(
            paragraphs=[
                Paragraph(
                    level=0,
                    runs=[TextRun(text="Quarterly Results")],
                )
            ]
        ),
    )
    apply_cascading_placeholder_styles(title_sh, design)
    p0 = title_sh.text.paragraphs[0]
    r0 = p0.runs[0]
    assert r0.font == design.fonts["major"]
    assert r0.size == 36.0
    assert r0.color == design.colors.dk2 or r0.color == design.colors.dk1
    assert p0.props.get("algn") in ("l", "ctr")

    # 2. Body placeholder with levels
    body_sh = Shape(
        id="s_body",
        type="text",
        placeholder=PlaceholderInfo(type="body", idx=1),
        text=TextBody(
            paragraphs=[
                Paragraph(level=0, runs=[TextRun(text="Bullet 1")]),
                Paragraph(level=1, runs=[TextRun(text="Sub bullet")]),
            ]
        ),
    )
    apply_cascading_placeholder_styles(body_sh, design)
    b_p0 = body_sh.text.paragraphs[0]
    b_p1 = body_sh.text.paragraphs[1]
    assert b_p0.runs[0].font == design.fonts["minor"]
    assert b_p0.runs[0].size in (24.0, 28.0, 32.0)
    assert b_p1.runs[0].size < b_p0.runs[0].size
    assert b_p0.props.get("bu") is not None


def test_unoverridden_layout_placeholders_resolution():
    """Verify that unoverridden placeholders from layout are synthesized when missing on slide."""
    pres = Presentation.create_new(w=960.0, h=540.0, empty=True)
    d = next(iter(pres.designs.values()))

    # Create a slide with layout "text", but ONLY supply a title shape
    slide = Slide(
        id="sl_test",
        layout="text",
        design_id=d.id,
        shapes=[
            Shape(
                id="s_title",
                type="text",
                name="Title",
                x=48.0,
                y=21.6,
                w=864.0,
                h=90.0,
                placeholder=PlaceholderInfo(type="title", idx=0),
                text=TextBody.from_text("My Title"),
            )
        ],
    )
    pres.slides.append(slide)

    unoverridden = resolve_unoverridden_placeholders(slide, pres)
    # The slide already has title, so unoverridden should contain the body placeholder
    types = [s.placeholder.type for s in unoverridden if s.placeholder]
    assert "body" in types
    assert "title" not in types

    body_sh = next(s for s in unoverridden if s.placeholder.type == "body")
    assert body_sh.w > 0 and body_sh.h > 0
    assert "Click to add text" in body_sh.text.plain_text or body_sh.text.is_empty()


def test_header_footer_placeholders_resolution():
    """Verify header and footer placeholders (dt, ftr, sldNum) are resolved from presentation.hf."""
    pres = Presentation.create_new(w=960.0, h=540.0, empty=True)
    d = next(iter(pres.designs.values()))
    pres.hf = HeaderFooterSettings(
        dt=True,
        dt_auto=True,
        dt_fmt="datetime1",
        num=True,
        ftr=True,
        ftr_text="Confidential Project",
        not_on_title=True,
    )

    slide1 = Slide(id="sl_1", layout="text", design_id=d.id)
    pres.slides.append(slide1)

    unoverridden = resolve_unoverridden_placeholders(slide1, pres)
    types = [s.placeholder.type for s in unoverridden if s.placeholder]
    assert "dt" in types
    assert "ftr" in types
    assert "sldNum" in types

    ftr_sh = next(s for s in unoverridden if s.placeholder.type == "ftr")
    assert ftr_sh.text.plain_text == "Confidential Project"

    sld_sh = next(s for s in unoverridden if s.placeholder.type == "sldNum")
    run = sld_sh.text.paragraphs[0].runs[0]
    assert run.field in ("slNum", "slidenum", "sldNum") or run.text == "1"

    # Test not_on_title suppression
    title_slide = Slide(id="sl_title", layout="title", design_id=d.id)
    pres.slides.append(title_slide)
    title_unoverridden = resolve_unoverridden_placeholders(title_slide, pres)
    title_types = [s.placeholder.type for s in title_unoverridden if s.placeholder]
    assert "sldNum" not in title_types
    assert "ftr" not in title_types
    assert "dt" not in title_types


def test_dynamic_slide_number_evaluation():
    """Verify evaluation of slide number fields and offsets."""
    pres = Presentation.create_new(w=960.0, h=540.0, empty=True)
    pres.first_num = 1
    s0 = Slide(id="s0")
    s1 = Slide(id="s1")
    s2 = Slide(id="s2")
    pres.slides.extend([s0, s1, s2])

    run_field = TextRun(text="", field="slNum")
    run_marker = TextRun(text="‹#›")

    assert evaluate_field_text(run_field, slide_index=0, presentation=pres) == "1"
    assert evaluate_field_text(run_field, slide_index=2, presentation=pres) == "3"
    assert evaluate_field_text(run_marker, slide_index=1, presentation=pres) == "2"

    # Custom first_num = 5
    pres.first_num = 5
    assert evaluate_field_text(run_field, slide_index=0, presentation=pres) == "5"
    assert evaluate_field_text(run_field, slide_index=1, presentation=pres) == "6"


def test_hide_master_suppression():
    """Verify that hide_master=True suppresses unoverridden master/layout placeholders."""
    pres = Presentation.create_new(w=960.0, h=540.0, empty=True)
    d = next(iter(pres.designs.values()))
    pres.hf = HeaderFooterSettings(num=True, ftr=True, ftr_text="Secret")

    slide = Slide(id="sl_hide", layout="text", design_id=d.id, hide_master=True)
    pres.slides.append(slide)

    unoverridden = resolve_unoverridden_placeholders(slide, pres)
    # Master footer placeholders should be suppressed
    types = [s.placeholder.type for s in unoverridden if s.placeholder]
    assert "sldNum" not in types
    assert "ftr" not in types


def test_slide_canvas_dynamic_binding(qapp):
    """Verify SlideCanvas dynamically populates unoverridden placeholders and slide numbers."""
    pres = Presentation.create_new(w=960.0, h=540.0, empty=True)
    d = next(iter(pres.designs.values()))
    pres.hf = HeaderFooterSettings(num=True, ftr=True, ftr_text="ATBOffice Test")

    slide = Slide(
        id="sl_canvas_test",
        layout="text",
        design_id=d.id,
        shapes=[
            Shape(
                id="s_title",
                type="text",
                x=48.0,
                y=21.6,
                w=864.0,
                h=90.0,
                placeholder=PlaceholderInfo(type="title", idx=0),
                text=TextBody.from_text("Canvas Test Title"),
            )
        ],
    )
    pres.slides.append(slide)

    canvas = SlideScene(slide=slide, presentation=pres, slide_width=960.0, slide_height=540.0)
    canvas.load_slide(slide)

    # Check canvas items
    items = canvas.items()
    # Should include title shape, unoverridden body placeholder, and footer placeholders
    shape_items = [it for it in items if hasattr(it, "model") and hasattr(it.model, "placeholder")]
    ph_types = {it.model.placeholder.type for it in shape_items if it.model.placeholder}

    assert "title" in ph_types
    assert "body" in ph_types
    assert "sldNum" in ph_types
    assert "ftr" in ph_types
