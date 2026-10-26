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
