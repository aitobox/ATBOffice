"""Interactive GUI tests for SlideShow ink annotations, pointer tools, laser overlay and exit prompt."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.slideshow.annotation_layer import (
    AnnotationStroke,
    SlideAnnotationOverlay,
)
from atboffice.modules.presentation.slideshow.slide_hud import SlideShowHud
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_presentation():
    pres = Presentation(w=960.0, h=540.0)
    s1 = pres.add_slide(layout="title")
    s1.transition = Transition(type="fade", speed="fast")

    s2 = pres.add_slide(layout="text")
    s2.transition = Transition(type="push", dir="l", speed="fast")

    s3 = pres.add_slide(layout="blank")
    s3.add_shape(Shape(id="rect_3", x=100, y=100, w=200, h=150))
    return pres


def test_annotation_overlay_modes_and_strokes(qapp):
    """Verify tool switching, ink drawing, highlighter, and eraser on SlideAnnotationOverlay."""
    overlay = SlideAnnotationOverlay(slide_w=960.0, slide_h=540.0)
    overlay.resize(960, 540)
    overlay.set_slide_index(0)

    # 1. Pen mode drawing
    overlay.set_mode("pen", color="#0000FF", width=4.0)
    assert overlay.mode == "pen"
    assert overlay.pen_color == "#0000FF"
    assert overlay.cursor().shape() == Qt.CursorShape.CrossCursor

    p_down = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 100),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(p_down)
    assert overlay.current_stroke is not None

    p_move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(150, 150),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseMoveEvent(p_move)

    p_up = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(150, 150),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(p_up)

    strokes_s0 = overlay.get_strokes(0)
    assert len(strokes_s0) == 1
    assert strokes_s0[0].color == "#0000FF"
    assert len(strokes_s0[0].points) >= 2

    # 2. Highlighter mode drawing
    overlay.set_mode("highlighter")
    assert overlay.mode == "highlighter"
    assert overlay.cursor().shape() == Qt.CursorShape.CrossCursor

    p_hl_down = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(200, 200),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(p_hl_down)
    p_hl_up = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(250, 200),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(p_hl_up)

    assert len(overlay.get_strokes(0)) == 2
    hl_stroke = overlay.get_strokes(0)[1]
    assert hl_stroke.is_highlighter is True
    assert hl_stroke.alpha < 1.0

    # 3. Eraser mode
    overlay.set_mode("eraser")
    assert overlay.mode == "eraser"
    assert overlay.cursor().shape() == Qt.CursorShape.PointingHandCursor

    p_erase = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(102, 102),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(p_erase)
    assert len(overlay.get_strokes(0)) == 1  # First stroke erased

    # 4. Clear all ink on slide
    overlay.clear_slide_ink(0)
    assert len(overlay.get_strokes(0)) == 0


def test_annotation_overlay_laser_pointer(qapp):
    """Verify laser pointer tracking and signal emission."""
    overlay = SlideAnnotationOverlay(slide_w=960.0, slide_h=540.0)
    overlay.resize(960, 540)
    overlay.set_mode("laser")
    assert overlay.mode == "laser"
    assert overlay.cursor().shape() == Qt.CursorShape.BlankCursor

    laser_updates = []
    overlay.laserMoved.connect(lambda pt: laser_updates.append(pt))

    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(300, 200),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseMoveEvent(move_event)

    assert overlay.laser_pos is not None
    assert len(laser_updates) == 1
    assert abs(overlay.laser_pos[0] - 300) < 5
    assert abs(overlay.laser_pos[1] - 200) < 5


def test_annotation_overlay_convert_to_shapes(qapp, sample_presentation):
    """Verify converting annotation strokes to DrawingML Shape models."""
    overlay = SlideAnnotationOverlay(slide_w=960.0, slide_h=540.0)
    stroke = AnnotationStroke(
        points=[(10.0, 10.0), (20.0, 20.0), (30.0, 25.0)],
        color="#FF0000",
        width=3.0,
        alpha=1.0,
    )
    overlay.set_strokes(0, [stroke])

    shapes = overlay.export_strokes_as_shapes(0)
    assert len(shapes) == 1
    sh = shapes[0]
    assert sh.geom == "freeform"
    assert sh.poly == [[10.0, 10.0], [20.0, 20.0], [30.0, 25.0]]
    assert sh.line.color == "#FF0000"


def test_slideshow_hud_laser_pointer_menu(qapp, sample_presentation):
    """Verify that SlideShowHud includes Laser Pointer option and emits pen_mode_changed."""
    hud = SlideShowHud(presentation=sample_presentation)
    emitted = []
    hud.pen_mode_changed.connect(lambda tool, color: emitted.append((tool, color)))

    # Trigger laser selection
    hud._select_pen_tool("laser")
    assert emitted[-1] == ("laser", hud.current_pen_color)
    assert hud.current_pen_tool == "laser"

    # Verify menu actions
    menu = hud.btn_pen.menu()
    assert menu is not None
    action_texts = [a.text() for a in menu.actions()]
    assert any("激光笔" in text or "Laser" in text for text in action_texts)


def test_slideshow_view_hotkeys_and_blanking(qapp, sample_presentation):
    """Verify presentation hotkeys: B (Black), W (White), E (Erase All), Ctrl+L (Laser), Ctrl+P (Pen), Ctrl+A (Arrow)."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    view.resize(960, 540)
    assert view.blank_color is None

    # 1. Hotkey 'B' -> Black Screen
    key_b = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier, "b")
    view.keyPressEvent(key_b)
    assert view.blank_color == QColor("#000000")

    # Press 'B' again -> unblank
    view.keyPressEvent(key_b)
    assert view.blank_color is None

    # 2. Hotkey 'W' -> White Screen
    key_w = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier, "w")
    view.keyPressEvent(key_w)
    assert view.blank_color == QColor("#FFFFFF")

    # Press 'W' again -> unblank
    view.keyPressEvent(key_w)
    assert view.blank_color is None

    # 3. Hotkey Ctrl+P -> Pen tool
    key_ctrl_p = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
    )
    view.keyPressEvent(key_ctrl_p)
    assert view.pen_tool == "pen"

    # 4. Hotkey Ctrl+L -> Laser pointer
    key_ctrl_l = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier
    )
    view.keyPressEvent(key_ctrl_l)
    assert view.pen_tool == "laser"

    # 5. Hotkey Ctrl+E -> Eraser
    key_ctrl_e = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier
    )
    view.keyPressEvent(key_ctrl_e)
    assert view.pen_tool == "eraser"

    # 6. Hotkey Ctrl+A -> Arrow
    key_ctrl_a = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier
    )
    view.keyPressEvent(key_ctrl_a)
    assert view.pen_tool == "arrow"

    # 7. Add stroke then Hotkey 'E' -> Erase All on slide
    view.ink_strokes[0] = [
        AnnotationStroke(points=[(10, 10), (20, 20)], color="#FF0000")
    ]
    assert len(view.ink_strokes[0]) == 1

    key_e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.NoModifier, "e")
    view.keyPressEvent(key_e)
    assert len(view.ink_strokes.get(0, [])) == 0

    view.end_show(prompt_ink=False)


def test_slideshow_view_end_show_ink_retention(qapp, sample_presentation):
    """Verify end_show preserves ink annotations as Shape objects when keep_ink=True."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    slide0 = sample_presentation.slides[0]
    initial_shape_count = len(slide0.shapes)

    # Add ink annotation on slide 0
    stroke = AnnotationStroke(points=[(50.0, 50.0), (100.0, 100.0)], color="#00AA00", width=5.0)
    view.ink_strokes[0] = [stroke]

    # End show with keep_ink=True (prompt_ink=False to bypass modal dialog)
    view.end_show(prompt_ink=False, keep_ink=True)
    assert view.is_active is False
    assert len(slide0.shapes) == initial_shape_count + 1

    added_shape = slide0.shapes[-1]
    assert added_shape.geom == "freeform"
    assert added_shape.poly == [[50.0, 50.0], [100.0, 100.0]]
    assert added_shape.line.color == "#00AA00"
