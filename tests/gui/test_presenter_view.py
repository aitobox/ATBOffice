"""GUI and unit tests for Lectern PresenterConsole (Speaker View)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.slideshow.presenter_view import (
    InkPoint,
    InkStroke,
    InteractiveSlideCanvas,
    PresenterConsole,
    PresenterView,
)
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
    # Slide 1 (index 0)
    s1 = pres.add_slide(layout="title")
    s1.notes = "Welcome to the presentation. Here are key speaker points."
    s1.transition = Transition(type="fade", speed="fast")

    # Slide 2 (index 1)
    s2 = pres.add_slide(layout="text")
    s2.notes = "Deep dive into architecture and performance."
    s2.transition = Transition(type="push", dir="l", speed="fast")

    # Slide 3 (index 2)
    s3 = pres.add_slide(layout="blank")
    s3.add_shape(Shape(id="rect_3", x=100, y=100, w=200, h=150))
    s3.notes = ""  # Empty notes edge case

    return pres


def test_ink_stroke_and_point():
    """Verify InkPoint and InkStroke data models and attributes."""
    p1 = InkPoint(10.0, 20.0)
    assert p1.x == 10.0
    assert p1.y == 20.0

    stroke = InkStroke(
        points=[(10.0, 20.0), (30.0, 40.0)],
        color="#00FF00",
        width=3.5,
        alpha=0.8,
        is_highlighter=False,
    )
    assert len(stroke.points) == 2
    assert stroke.color == "#00FF00"
    assert stroke.width == 3.5
    assert stroke.alpha == 0.8
    assert stroke.is_highlighter is False


def test_interactive_canvas_modes_and_drawing(qapp):
    """Verify InteractiveSlideCanvas drawing, laser, eraser, and mode transitions."""
    canvas = InteractiveSlideCanvas()
    canvas.resize(960, 540)
    canvas.show()

    # Default mode
    assert canvas.mode == "arrow"

    # Advance slide click in arrow mode
    advance_called = False

    def on_advance():
        nonlocal advance_called
        advance_called = True

    canvas.slideAdvanced.connect(on_advance)
    event_click = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(400, 300),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(event_click)
    event_release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(400, 300),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(event_release)
    assert advance_called is True

    # Pen drawing mode
    canvas.set_mode("pen")
    assert canvas.mode == "pen"
    strokes_added: list[InkStroke] = []
    canvas.strokeAdded.connect(lambda idx, s: strokes_added.append(s))

    press_pen = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 100),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press_pen)
    assert canvas.current_stroke is not None

    move_pen = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(120, 130),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move_pen)
    assert len(canvas.current_stroke.points) >= 2

    release_pen = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(140, 150),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(release_pen)
    assert canvas.current_stroke is None
    assert len(canvas.strokes) == 1
    assert len(strokes_added) == 1

    # Laser pointer mode
    canvas.set_mode("laser")
    assert canvas.mode == "laser"
    laser_positions = []
    canvas.laserMoved.connect(laser_positions.append)

    move_laser = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(200, 250),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move_laser)
    assert canvas.laser_pos is not None
    assert len(laser_positions) >= 1

    # Eraser mode
    canvas.set_mode("eraser")
    assert canvas.mode == "eraser"
    press_eraser = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(100, 100),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press_eraser)
    assert len(canvas.strokes) == 0

    canvas.close()


def test_presenter_console_init_and_layout(qapp, sample_presentation):
    """Verify PresenterConsole initialization, UI elements, and alias PresenterView."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    assert PresenterView is PresenterConsole
    assert console.current_slide_index == 0
    assert (
        console.notes_edit.toPlainText()
        == "Welcome to the presentation. Here are key speaker points."
    )
    assert "00:00:00" in console.timer_label.text()
    assert console.is_timer_running is True

    # Next slide preview shows slide 1
    assert console.next_preview_label is not None
    next_title = console.next_preview_title.text()
    assert "2" in next_title or "幻灯片 2" in next_title or "2." in next_title

    console.close()


def test_presenter_console_timer_controls(qapp, sample_presentation):
    """Verify timer elapsed ticking, pause, resume, and reset."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    console.elapsed_seconds = 65  # 1 min 5 sec
    console._update_timer_display()
    assert "00:01:05" in console.timer_label.text()

    # Pause timer
    console.toggle_timer()
    assert console.is_timer_running is False
    assert "▶" in console.btn_pause_timer.text() or "继续" in console.btn_pause_timer.toolTip()

    # Resume timer
    console.toggle_timer()
    assert console.is_timer_running is True

    # Reset timer
    console.reset_timer()
    assert console.elapsed_seconds == 0
    assert "00:00:00" in console.timer_label.text()

    console.close()


def test_presenter_console_navigation(qapp, sample_presentation):
    """Verify next, prev, and goto slide navigation."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    assert console.current_slide_index == 0

    # Advance
    console.next_slide()
    assert console.current_slide_index == 1
    assert "Deep dive into architecture" in console.notes_edit.toPlainText()

    # Advance to slide 2 (empty notes edge case)
    console.next_slide()
    assert console.current_slide_index == 2
    notes_empty = console.notes_edit.toPlainText() == ""
    placeholder_ok = "无演讲者备注" in console.notes_placeholder.text()
    assert notes_empty or placeholder_ok

    # Previous back to 1
    console.prev_slide()
    assert console.current_slide_index == 1

    # Goto slide 0
    console.goto_slide(0)
    assert console.current_slide_index == 0

    console.close()


def test_presenter_console_notes_zoom(qapp, sample_presentation):
    """Verify speaker notes zoom in and zoom out controls."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    init_size = console.notes_font_size

    console.zoom_in_notes()
    assert console.notes_font_size == init_size + 2

    console.zoom_out_notes()
    assert console.notes_font_size == init_size

    # Zoom out repeatedly to test min bound
    for _ in range(20):
        console.zoom_out_notes()
    assert console.notes_font_size >= 8

    console.close()


def test_presenter_console_thumbnail_drawer(qapp, sample_presentation):
    """Verify thumbnail drawer toggle and direct jumping."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    assert console.drawer_widget.isVisible() is False

    console.toggle_drawer()
    assert console.drawer_widget.isVisible() is True

    # Click jump to slide 2
    console.select_slide_from_drawer(2)
    assert console.current_slide_index == 2

    console.toggle_drawer()
    assert console.drawer_widget.isVisible() is False

    console.close()


def test_presenter_console_dual_screen_sync(qapp, sample_presentation):
    """Verify bidirectional synchronization with audience SlideShowView."""
    audience = SlideShowView(sample_presentation, start_slide_index=0)
    console = PresenterConsole(sample_presentation, start_slide_index=0, audience_view=audience)

    # Slide navigation sync
    console.next_slide()
    assert audience.current_slide_index == 1

    audience.next_slide()
    if audience.in_transition:
        audience.finish_transition_now()
    assert console.current_slide_index == 2

    # Black screen sync
    console.toggle_black()
    assert audience.blank_color == QColor(0, 0, 0)
    console.toggle_black()
    assert audience.blank_color is None

    # White screen sync
    console.toggle_white()
    assert audience.blank_color == QColor(255, 255, 255)
    console.toggle_white()
    assert audience.blank_color is None

    # Laser pointer sync
    console.canvas.laser_pos = (150.0, 200.0)
    console.canvas.laserMoved.emit((150.0, 200.0))
    assert audience.laser_pos == (150.0, 200.0)

    # Ink annotations sync
    stroke = InkStroke(points=[(50, 50), (100, 100)], color="#FF0000", width=3.0)
    console.canvas.strokes.append(stroke)
    console.canvas.strokeAdded.emit(2, stroke)
    assert 2 in audience.ink_strokes
    assert len(audience.ink_strokes[2]) == 1

    console.close()
    audience.close()


def test_presenter_console_end_show_ink_retention(qapp, sample_presentation):
    """Verify ink annotation prompt and shape conversion upon show ending."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    stroke = InkStroke(points=[(10, 10), (50, 60), (100, 120)], color="#0000FF", width=4.0)
    console.ink_strokes[0] = [stroke]

    initial_shape_count = len(sample_presentation.slides[0].shapes)
    console.end_show(prompt_ink=False, keep_ink=True)
    assert len(sample_presentation.slides[0].shapes) == initial_shape_count + 1
    new_shape = sample_presentation.slides[0].shapes[-1]
    assert new_shape.poly == [[10, 10], [50, 60], [100, 120]]
    assert new_shape.line.color == "#0000FF"

    console.close()


def test_presenter_console_keyboard_shortcuts(qapp, sample_presentation):
    """Verify key shortcuts for next, prev, black screen, tools, and exit."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)

    # Next via Space
    key_space = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    console.keyPressEvent(key_space)
    assert console.current_slide_index == 1

    # Prev via Backspace
    key_back = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier
    )
    console.keyPressEvent(key_back)
    assert console.current_slide_index == 0

    # Black screen via B
    key_b = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier)
    console.keyPressEvent(key_b)
    assert console.canvas.blank_color == QColor(0, 0, 0)
    console.keyPressEvent(key_b)
    assert console.canvas.blank_color is None

    # White screen via W
    key_w = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier)
    console.keyPressEvent(key_w)
    assert console.canvas.blank_color == QColor(255, 255, 255)
    console.keyPressEvent(key_w)
    assert console.canvas.blank_color is None

    # Pen shortcut (Ctrl+P)
    key_pen = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier)
    console.keyPressEvent(key_pen)
    assert console.canvas.mode == "pen"

    # Laser shortcut (Ctrl+L)
    key_laser = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier
    )
    console.keyPressEvent(key_laser)
    assert console.canvas.mode == "laser"

    # Eraser shortcut (Ctrl+E)
    key_eraser = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier
    )
    console.keyPressEvent(key_eraser)
    assert console.canvas.mode == "eraser"

    # Arrow shortcut (Ctrl+A)
    key_arrow = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier
    )
    console.keyPressEvent(key_arrow)
    assert console.canvas.mode == "arrow"

    console.close()


def test_presenter_console_retranslate_ui(qapp, sample_presentation):
    """Verify retranslate_ui executes cleanly without exceptions."""
    console = PresenterConsole(sample_presentation, start_slide_index=0)
    console.retranslate_ui()
    assert console.windowTitle() != ""
    console.close()
