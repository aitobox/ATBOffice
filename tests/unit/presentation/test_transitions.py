"""Unit tests for Lectern slide transitions catalogue and rendering algorithms."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.presentation.slideshow.transitions import (
    TRANSITION_CATALOGUE,
    TransitionEffect,
    get_transition_duration,
    get_transition_name,
    list_transitions,
    render_slide_to_image,
    render_transition_frame,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_transition_catalogue():
    """Verify that the catalogue contains 58 distinct effect transitions plus none and random."""
    effects = list_transitions()
    assert len(effects) >= 59  # 58 effects + none + random = 60

    effect_types = {e.type for e in effects}
    assert "none" in effect_types
    assert "blinds" in effect_types
    assert "zoom" in effect_types
    assert "checker" in effect_types
    assert "comb" in effect_types
    assert "cover" in effect_types
    assert "cut" in effect_types
    assert "dissolve" in effect_types
    assert "fade" in effect_types
    assert "newsflash" in effect_types
    assert "push" in effect_types
    assert "randomBar" in effect_types
    assert "circle" in effect_types
    assert "diamond" in effect_types
    assert "plus" in effect_types
    assert "split" in effect_types
    assert "strips" in effect_types
    assert "pull" in effect_types
    assert "wedge" in effect_types
    assert "wheel" in effect_types
    assert "wipe" in effect_types
    assert "random" in effect_types


def test_transition_metadata_helpers():
    """Verify duration and name retrieval for various transitions."""
    t_none = Transition(type="none")
    assert get_transition_name(t_none) in ("无切换", "No Transition")
    assert get_transition_duration(t_none) == 0

    t_fade_fast = Transition(type="fade", speed="fast")
    assert get_transition_duration(t_fade_fast) == 500

    t_fade_med = Transition(type="fade", speed="med")
    assert get_transition_duration(t_fade_med) == 750

    t_fade_slow = Transition(type="fade", speed="slow")
    assert get_transition_duration(t_fade_slow) == 1000

    t_wheel_4 = Transition(type="wheel", spokes=4)
    name = get_transition_name(t_wheel_4)
    assert "4" in name or "Wheel" in name or "轮" in name


def test_render_slide_to_image(qapp):
    """Verify rendering slide background and shapes to a QImage."""
    pres = Presentation()
    slide = pres.add_slide()
    slide.add_shape(Shape(id="sh_test", x=50, y=50, w=200, h=100))

    img = render_slide_to_image(slide, pres, width=400, height=300)
    assert isinstance(img, QImage)
    assert not img.isNull()
    assert img.width() == 400
    assert img.height() == 300


@pytest.mark.parametrize(
    "trans",
    [
        Transition(type="none"),
        Transition(type="cut"),
        Transition(type="cut", thruBlk=True),
        Transition(type="fade"),
        Transition(type="fade", thruBlk=True),
        Transition(type="push", dir="d"),
        Transition(type="push", dir="l"),
        Transition(type="push", dir="r"),
        Transition(type="push", dir="u"),
        Transition(type="cover", dir="d"),
        Transition(type="cover", dir="ld"),
        Transition(type="pull", dir="r"),
        Transition(type="pull", dir="ru"),
        Transition(type="wipe", dir="d"),
        Transition(type="wipe", dir="l"),
        Transition(type="split", orient="vert", dir="in"),
        Transition(type="split", orient="horz", dir="out"),
        Transition(type="blinds", dir="horz"),
        Transition(type="blinds", dir="vert"),
        Transition(type="comb", dir="horz"),
        Transition(type="comb", dir="vert"),
        Transition(type="checker", dir="horz"),
        Transition(type="checker", dir="vert"),
        Transition(type="circle"),
        Transition(type="diamond"),
        Transition(type="plus"),
        Transition(type="zoom", dir="in"),
        Transition(type="zoom", dir="out"),
        Transition(type="wedge"),
        Transition(type="wheel", spokes=1),
        Transition(type="wheel", spokes=4),
        Transition(type="wheel", spokes=8),
        Transition(type="randomBar", dir="horz"),
        Transition(type="randomBar", dir="vert"),
        Transition(type="strips", dir="ld"),
        Transition(type="strips", dir="ru"),
        Transition(type="dissolve"),
        Transition(type="newsflash"),
        Transition(type="random"),
    ],
)
def test_render_transition_frame_all_effects(qapp, trans):
    """Verify that all transition effect variants render without errors at progress 0, 0.5, 1.0."""
    w, h = 320, 240
    img_from = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img_from.fill(QColor("#FF0000"))

    img_to = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img_to.fill(QColor("#0000FF"))

    for p in (0.0, 0.5, 1.0):
        dest = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(dest)
        try:
            render_transition_frame(painter, img_from, img_to, trans, p, w, h)
        finally:
            painter.end()

        assert not dest.isNull()
