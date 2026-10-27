"""GUI tests for Lectern fullscreen SlideShowView, navigation, transitions, and context menu."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView
from atboffice.modules.presentation.views.workspace import LecternWorkspace


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_presentation():
    pres = Presentation(w=960.0, h=540.0)
    # Slide 1
    s1 = pres.add_slide(layout="title")
    s1.transition = Transition(type="fade", speed="fast")

    # Slide 2
    s2 = pres.add_slide(layout="text")
    s2.transition = Transition(type="push", dir="l", speed="fast")

    # Slide 3
    s3 = pres.add_slide(layout="blank")
    s3.add_shape(Shape(id="rect_3", x=100, y=100, w=200, h=150))
    s3.transition = Transition(type="wipe", dir="d", speed="fast")

    return pres


def test_slideshow_init_and_lifecycle(qapp, sample_presentation):
    """Verify initialization, slide indexing, and ending of SlideShowView."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    assert view.is_active is True
    assert view.current_slide_index == 0
    assert len(view.order) == 3

    ended_signal_received = False

    def on_show_ended():
        nonlocal ended_signal_received
        ended_signal_received = True

    view.showEnded.connect(on_show_ended)

    # End show
    view.end_show()
    assert view.is_active is False
    assert ended_signal_received is True


def test_slideshow_navigation(qapp, sample_presentation):
    """Verify programmatic and interactive next, prev, goto navigation."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    changed_indices = []
    view.slideChanged.connect(changed_indices.append)

    # Advance to slide 1
    view.next_slide()
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 1
    assert 1 in changed_indices

    # Advance to slide 2
    view.next_slide()
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 2

    # Previous back to slide 1
    view.prev_slide()
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 1

    # Direct goto slide 0
    view.goto_slide(0)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 0

    view.end_show()


def test_slideshow_keyboard_navigation(qapp, sample_presentation):
    """Verify keyboard shortcuts for slide navigation, blanking, and exit."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)

    # Space -> Next slide
    event_space = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " "
    )
    view.keyPressEvent(event_space)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 1

    # Backspace -> Previous slide
    event_bs = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier
    )
    view.keyPressEvent(event_bs)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 0

    # Key 'B' -> Toggle black screen
    event_b = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier, "b")
    view.keyPressEvent(event_b)
    assert view.blank_color == "#000000"

    # Any key unblanks screen without changing slide
    view.keyPressEvent(event_space)
    assert view.blank_color is None
    assert view.current_slide_index == 0

    # Key 'W' -> Toggle white screen
    event_w = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier, "w")
    view.keyPressEvent(event_w)
    assert view.blank_color == "#FFFFFF"
    view.keyPressEvent(event_w)
    assert view.blank_color is None

    # Key 'End' -> Jump to last slide
    event_end = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(event_end)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 2

    # Key 'Home' -> Jump to first slide
    event_home = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(event_home)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 0

    # Key Escape -> End show
    event_esc = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    view.keyPressEvent(event_esc)
    assert view.is_active is False


def test_slideshow_direct_goto_buffer(qapp, sample_presentation):
    """Verify typing digit + Enter jumps to slide number."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)

    # Type '2'
    ev_2 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
    view.keyPressEvent(ev_2)
    assert view.goto_buf == "2"

    # Type Enter
    ev_enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(ev_enter)
    if view.in_transition:
        view.finish_transition_now()

    # Slide number 2 corresponds to index 1 (1-based to 0-based)
    assert view.current_slide_index == 1
    assert view.goto_buf == ""

    view.end_show()


def test_slideshow_hidden_slide_skipping(qapp, sample_presentation):
    """Verify that hidden slides are skipped during regular linear presentation."""
    # Hide slide 1 (the middle slide)
    sample_presentation.slides[1].hidden = True

    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    assert view.current_slide_index == 0

    # Advance
    view.next_slide()
    if view.in_transition:
        view.finish_transition_now()

    # Should jump directly to slide 2, skipping hidden slide 1
    assert view.current_slide_index == 2

    # Backwards
    view.prev_slide()
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 0

    view.end_show()


def test_slideshow_end_screen_and_loop(qapp, sample_presentation):
    """Verify end of slide show screen and loop playback."""
    # Non-loop mode
    sample_presentation.show.loop = False
    view = SlideShowView(presentation=sample_presentation, start_slide_index=2)
    assert view.current_slide_index == 2

    # Advance past end
    view.next_slide()
    assert view.is_ended is True

    # Click on end screen ends show
    view.next_slide()
    assert view.is_active is False

    # Loop mode
    sample_presentation.show.loop = True
    view_loop = SlideShowView(presentation=sample_presentation, start_slide_index=2)
    view_loop.next_slide()
    if view_loop.in_transition:
        view_loop.finish_transition_now()
    assert view_loop.current_slide_index == 0
    view_loop.end_show()


def test_slideshow_context_menu(qapp, sample_presentation):
    """Verify right-click context menu options."""
    view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
    menu = view.create_context_menu()
    actions = [a.text() for a in menu.actions() if not a.isSeparator()]

    assert any("下一页" in a or "Next" in a for a in actions)
    assert any("上一页" in a or "Previous" in a for a in actions)
    assert any("定位到幻灯片" in a or "Go to" in a for a in actions)
    assert any("屏幕" in a or "Screen" in a for a in actions)
    assert any("结束放映" in a or "End Show" in a for a in actions)

    view.end_show()


def test_workspace_slideshow_launch(qapp, sample_presentation):
    """Verify launching slideshow from LecternWorkspace via F5 and Shift+F5 methods."""
    ws = LecternWorkspace(presentation=sample_presentation)

    # 1. Start from beginning
    show_from_start = ws.start_slideshow(from_current=False)
    assert show_from_start is not None
    assert show_from_start.current_slide_index == 0
    show_from_start.end_show()

    # 2. Switch active slide in workspace to 2
    ws.set_current_slide(2)
    assert ws.current_slide_index == 2

    # Start from current
    show_from_current = ws.start_slideshow(from_current=True)
    assert show_from_current is not None
    assert show_from_current.current_slide_index == 2
    show_from_current.end_show()
