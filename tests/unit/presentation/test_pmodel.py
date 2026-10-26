"""Unit tests for Lectern Presentation Models (Issue #39)."""

import pytest

from atboffice.modules.presentation.models.text import (
    BulletInfo,
    Paragraph,
    TextBody,
    TextRun,
    TextStyleLevel,
)
from atboffice.modules.presentation.models.shape import (
    Fill,
    Line,
    PlaceholderInfo,
    Shadow,
    Shape,
)


def test_text_run_and_paragraph_basics():
    run1 = TextRun(text="Hello ", bold=True, size=32.0, color="tx1")
    run2 = TextRun(text="World", italic=True, size=32.0, color="accent1")
    para = Paragraph(level=0, runs=[run1, run2])

    assert para.plain_text == "Hello World"
    assert len(para.runs) == 2
    assert para.level == 0


def test_text_body_operations():
    body = TextBody.from_plain_text("Line 1\nLine 2")
    assert not body.is_empty()
    assert body.plain_text == "Line 1\nLine 2"
    assert len(body.paragraphs) == 2
    assert body.paragraphs[0].plain_text == "Line 1"
    assert body.paragraphs[1].plain_text == "Line 2"

    empty_body = TextBody.create_empty()
    assert empty_body.is_empty()
    assert empty_body.plain_text == ""


def test_shape_basics_and_serialization():
    fill = Fill.solid("accent1", alpha=0.9)
    line = Line(color="tx1", width=1.5, dash="solid")
    sh = Shape(
        id="s1",
        type="shape",
        name="Rectangle 1",
        geom="rect",
        x=100.0,
        y=50.0,
        w=200.0,
        h=150.0,
        fill=fill,
        line=line,
        placeholder=PlaceholderInfo(type="title", idx=0),
    )

    data = sh.to_dict()
    restored = Shape.from_dict(data)

    assert restored.id == "s1"
    assert restored.geom == "rect"
    assert restored.x == 100.0
    assert restored.fill.color == "accent1"
    assert restored.fill.alpha == 0.9
    assert restored.placeholder.type == "title"
    assert restored.placeholder.idx == 0


def test_15_design_templates_and_color_resolver():
    from atboffice.modules.presentation.models.designs import (
        DESIGNS,
        DesignTemplate,
        build_design,
        resolve_color,
    )

    expected_keys = [
        "default",
        "azure",
        "night",
        "meadow",
        "ember",
        "graphite",
        "blueprint",
        "capsule",
        "ocean",
        "parchment",
        "pixel",
        "crimson",
        "glass",
        "radial",
        "evergreen",
    ]
    assert len(DESIGNS) == 15
    for key in expected_keys:
        assert any(d.key == key for d in DESIGNS), f"Missing design key: {key}"

    # Build concrete designs for 16:9
    d_azure = build_design("azure", 960.0, 540.0)
    assert d_azure.key == "azure"
    assert d_azure.fonts["major"] == "Trebuchet MS"
    assert len(d_azure.decorations) >= 2
    assert d_azure.title_decorations is not None

    # Color resolution
    assert resolve_color("#123456", d_azure) == "#123456"
    lt1 = d_azure.colors.lt1
    assert resolve_color("bg1", d_azure) == lt1
    assert resolve_color("lt1", d_azure) == lt1
    assert resolve_color("accent1", d_azure) == d_azure.colors.accent1
    assert resolve_color("unknown_slot", d_azure, fallback="#111111") == "#111111"


def test_21_layouts_and_frame_calculator():
    from atboffice.modules.presentation.models.designs import build_design
    from atboffice.modules.presentation.models.layouts import (
        LAYOUTS,
        layout_frames,
        make_placeholder,
    )

    assert len(LAYOUTS) == 21
    layout_keys = [l.key for l in LAYOUTS]
    assert "title" in layout_keys
    assert "twoText" in layout_keys
    assert "fourContent" in layout_keys
    assert "blank" in layout_keys
    assert "vertTitleText" in layout_keys

    design = build_design("default", 960.0, 540.0)

    # 1. Blank layout has 0 frames
    blank_frames = layout_frames("blank", design)
    assert len(blank_frames) == 0

    # 2. Title layout has 2 frames: ctrTitle and subTitle
    title_frames = layout_frames("title", design)
    assert len(title_frames) == 2
    types = [f["type"] for f in title_frames]
    assert "ctrTitle" in types
    assert "subTitle" in types

    # 3. FourContent layout has 5 frames: title + 4 obj
    four_frames = layout_frames("fourContent", design)
    assert len(four_frames) == 5
    assert four_frames[0]["type"] == "title"
    assert [f["type"] for f in four_frames[1:]] == ["obj", "obj", "obj", "obj"]

    # 4. Check placeholder shape creation
    sh = make_placeholder(title_frames[0], design)
    assert sh.type == "text"
    assert sh.placeholder is not None
    assert sh.placeholder.type == "ctrTitle"
    assert sh.text is not None
    assert sh.text.is_empty()


def test_slide_lifecycle_and_duplication():
    from atboffice.modules.presentation.models.designs import build_design
    from atboffice.modules.presentation.models.slide import (
        Slide,
        Transition,
        create_slide,
        dup_slide,
    )

    design = build_design("azure", 960.0, 540.0)
    slide = create_slide(layout="text", design=design)

    assert slide.layout == "text"
    assert slide.design_id == design.id
    assert len(slide.shapes) == 2  # title + body
    assert slide.transition.type == "none"

    # Set text on body placeholder
    body_sh = slide.shapes[1]
    body_sh.text.set_plain_text("Item 1\nItem 2")
    assert body_sh.text.plain_text == "Item 1\nItem 2"

    # Clone slide
    copy_slide = dup_slide(slide)
    assert copy_slide.id != slide.id
    assert len(copy_slide.shapes) == len(slide.shapes)
    assert copy_slide.shapes[0].id != slide.shapes[0].id
    assert copy_slide.shapes[1].id != slide.shapes[1].id
    assert copy_slide.shapes[1].text.plain_text == "Item 1\nItem 2"

    # Serialization
    data = slide.to_dict()
    restored = Slide.from_dict(data)
    assert restored.id == slide.id
    assert len(restored.shapes) == 2
    assert restored.shapes[1].text.plain_text == "Item 1\nItem 2"


def test_presentation_container_operations():
    from atboffice.modules.presentation.models.presentation import Presentation

    # 1. Create new presentation (default 16:9, 960x540)
    pres = Presentation.create_new(title="Demo Presentation", design_key="default")
    assert pres.w == 960.0
    assert pres.h == 540.0
    assert len(pres.slides) == 1
    assert pres.slides[0].layout == "title"

    # 2. Add slide with 'twoText' layout
    s2 = pres.add_slide(layout="twoText")
    assert len(pres.slides) == 2
    assert s2.layout == "twoText"
    assert len(s2.shapes) == 3  # title + 2 column body

    # Populate text in s2
    s2.shapes[0].text.set_plain_text("Comparison")
    s2.shapes[1].text.set_plain_text("Left Column")
    s2.shapes[2].text.set_plain_text("Right Column")

    # 3. Apply layout: change s2 from 'twoText' to 'text'
    pres.apply_layout(s2, "text")
    assert s2.layout == "text"
    # Should keep title and first column text, while retaining user content
    assert s2.get_title() == "Comparison"
    assert "Left Column" in s2.all_text()

    # 4. Apply design: change presentation design to 'evergreen'
    new_dsn_id = pres.apply_design("evergreen")
    assert pres.slides[0].design_id == new_dsn_id
    assert pres.designs[new_dsn_id].key == "evergreen"

    # 5. Aspect ratio conversion: switch from 16:9 (960x540) to 4:3 (720x540)
    pres.change_size(720.0, 540.0, scale_content=True)
    assert pres.w == 720.0
    assert pres.h == 540.0
    # Placeholders should be within 720 width
    for sh in pres.slides[0].shapes:
        assert sh.x + sh.w <= 720.0 + 1.0

    # 6. Serialization roundtrip
    data = pres.to_dict()
    restored_pres = Presentation.from_dict(data)
    assert restored_pres.w == 720.0
    assert restored_pres.h == 540.0
    assert len(restored_pres.slides) == 2
    assert restored_pres.title == "Demo Presentation"




