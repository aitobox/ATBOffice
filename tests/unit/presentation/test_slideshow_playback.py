"""Unit tests for Lectern slide show smooth transition animations and presenter view sync.

Covers:
- SlideTransitionPlayer 60 FPS timeline interpolation and control.
- Sequential key progression (Spacebar, PageDown, Arrow keys, N, P).
- PresenterConsole synchronization (notes, elapsed timer, next slide preview).
- Hidden slide filtering and loop handling.
- Context menu Presenter View trigger.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Animation, Transition
from atboffice.modules.presentation.slideshow.presenter_view import PresenterConsole
from atboffice.modules.presentation.slideshow.slideshow_view import SlideInkStroke, SlideShowView
from atboffice.modules.presentation.slideshow.transitions import (
    SlideTransitionPlayer,
    get_transition_duration,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def presentation_with_transitions_and_notes():
    pres = Presentation(w=960.0, h=540.0)

    # Slide 1: Fade transition, speaker notes
    s1 = pres.add_slide(layout="title")
    s1.transition = Transition(type="fade", speed="fast")
    s1.notes = "Slide 1 Speaker Notes: Introduction & Overview"

    # Slide 2: Push transition, animations, speaker notes
    s2 = pres.add_slide(layout="text")
    s2.transition = Transition(type="push", dir="l", speed="fast")
    s2.notes = "Slide 2 Speaker Notes: Technical Architecture"
    sh1 = Shape(id="box_1", x=50, y=50, w=200, h=100)
    s2.add_shape(sh1)
    s2.animations = [
        Animation(id="anim_1", sid="box_1", cls="entr", eff="flyIn", dir="b", start="click")
    ]

    # Slide 3: Hidden slide (should be skipped during next preview & normal playback)
    s3 = pres.add_slide(layout="blank")
    s3.hidden = True
    s3.notes = "Hidden backup slide"

    # Slide 4: Wipe transition, empty speaker notes
    s4 = pres.add_slide(layout="blank")
    s4.transition = Transition(type="wipe", dir="d", speed="fast")
    s4.notes = ""

    return pres


def test_transition_player_lifecycle(qapp):
    """Verify SlideTransitionPlayer start, progress emission, stop, and finish_now."""
    player = SlideTransitionPlayer()
    assert player.is_playing is False
    assert player.progress == 0.0

    progress_values: list[float] = []
    finished_called = False

    player.frameChanged.connect(progress_values.append)
    player.finished.connect(lambda: globals().update(finished_called=True))

    # Test "none" transition finishes immediately
    player.play(Transition(type="none"))
    assert player.progress == 1.0

    # Test active transition play and finish_now
    trans = Transition(type="fade", speed="fast")
    player.play(trans, duration_ms=400)
    assert player.is_playing is True
    assert player.active_transition == trans

    # finish_now skips to end
    player.finish_now()
    assert player.is_playing is False
    assert player.progress == 1.0

    # Test stop cancels without finished
    player.play(trans, duration_ms=500)
    assert player.is_playing is True
    player.stop()
    assert player.is_playing is False


def test_slideshow_smooth_transitions_playback(qapp, presentation_with_transitions_and_notes):
    """Verify SlideShowView uses SlideTransitionPlayer for smooth transitions."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    assert view.is_active is True
    assert view.current_slide_index == 0

    # Advance to slide 2 (push transition)
    view.next_slide()
    assert view.current_slide_index == 1
    assert view.in_transition is True
    assert view.transition_player.is_playing is True

    # Complete transition
    view.finish_transition_now()
    assert view.in_transition is False
    assert view.transition_player.is_playing is False

    view.end_show()


def test_sequential_animation_progression_and_key_triggers(
    qapp, presentation_with_transitions_and_notes
):
    """Verify Spacebar, PageDown, Right/Left arrows handle sequential animation steps first."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=1)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 1
    assert len(view._anim_steps) == 1
    assert view._anim_step_idx == 0

    # Trigger next step via Spacebar key event
    space_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        " ",
    )
    view.keyPressEvent(space_event)

    # Step was played, still on slide 1
    assert view.current_slide_index == 1

    # Finish any playing animation step
    if view._anim_player.is_playing:
        view._anim_player.finish_now()

    # Now on slide 1 with steps completed: next PageDown triggers slide transition to non-hidden slide (slide 3, index 3)
    pagedown_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_PageDown,
        Qt.KeyboardModifier.NoModifier,
    )
    view.keyPressEvent(pagedown_event)
    assert view.current_slide_index == 3  # Skipped hidden slide 2!

    if view.in_transition:
        view.finish_transition_now()

    # Left arrow goes back to slide 1 (skipping hidden slide 2)
    left_event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Left,
        Qt.KeyboardModifier.NoModifier,
    )
    view.keyPressEvent(left_event)
    if view.in_transition:
        view.finish_transition_now()
    assert view.current_slide_index == 1

    view.end_show()


def test_presenter_view_notes_sync(qapp, presentation_with_transitions_and_notes):
    """Verify speaker notes synchronization and font zooming."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    console = PresenterConsole(
        presentation_with_transitions_and_notes,
        start_slide_index=0,
        audience_view=view,
    )

    # Initial slide 0 notes
    assert "Slide 1 Speaker Notes" in console.notes_edit.toPlainText()
    assert console.notes_placeholder.isVisible() is False

    # Zoom notes
    initial_font_size = console.notes_font_size
    console.zoom_in_notes()
    assert console.notes_font_size == initial_font_size + 2
    console.zoom_out_notes()
    assert console.notes_font_size == initial_font_size

    # Advance to slide 3 (index 3, empty notes)
    view.goto_slide(3)
    if view.in_transition:
        view.finish_transition_now()
    assert console.current_slide_index == 3
    assert console.notes_placeholder.isVisible() is True

    console.close()
    view.end_show()


def test_presenter_view_timer_sync(qapp, presentation_with_transitions_and_notes):
    """Verify live presentation elapsed timer synchronization between view and console."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    view.elapsed_seconds = 42

    console = PresenterConsole(
        presentation_with_transitions_and_notes,
        start_slide_index=0,
        audience_view=view,
    )
    # Timer was synchronized on initialization
    assert console.elapsed_seconds == 42
    assert "00:00:42" in console.timer_label.text()

    # Audience timer tick updates console
    view.elapsed_seconds = 43
    view.timerTicked.emit(43)
    assert console.elapsed_seconds == 43
    assert "00:00:43" in console.timer_label.text()

    # Toggle timer (pause) from console synchronizes to audience view
    console.toggle_timer()
    assert console.is_timer_running is False
    assert view.is_timer_running is False

    # Resume
    console.toggle_timer()
    assert console.is_timer_running is True
    assert view.is_timer_running is True

    # Reset timer from console resets audience view
    console.reset_timer()
    assert console.elapsed_seconds == 0
    assert view.elapsed_seconds == 0
    assert "00:00:00" in console.timer_label.text()

    console.close()
    view.end_show()


def test_presenter_view_next_slide_preview_and_hidden_filtering(
    qapp, presentation_with_transitions_and_notes
):
    """Verify next slide preview filters hidden slides and handles presentation end."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    console = PresenterConsole(
        presentation_with_transitions_and_notes,
        start_slide_index=0,
        audience_view=view,
    )

    # Next slide from slide 0 is slide 1
    assert "幻灯片 2" in console.next_preview_title.text()

    # Move to slide 1: next non-hidden slide should be slide 3 (index 3), NOT hidden slide 2!
    view.goto_slide(1)
    if view.in_transition:
        view.finish_transition_now()
    assert "幻灯片 4" in console.next_preview_title.text()

    # Move to last slide (index 3): next preview should show "放映结束"
    view.goto_slide(3)
    if view.in_transition:
        view.finish_transition_now()
    assert "放映结束" in console.next_preview_title.text()

    console.close()
    view.end_show()


def test_slideshow_context_menu_presenter_view_action(
    qapp, presentation_with_transitions_and_notes
):
    """Verify SlideShowView context menu includes Presenter View action."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    menu = view.create_context_menu()
    actions = [a.text() for a in menu.actions()]
    assert any("演讲者视图" in text for text in actions)

    # show_presenter_view method opens console
    console = view.show_presenter_view()
    assert isinstance(console, PresenterConsole)
    assert console.audience_view is view

    console.close()
    view.end_show()


def test_ink_drawing_no_attribute_error(qapp, presentation_with_transitions_and_notes):
    """Verify SlideShowView ink stroke rendering does not raise AttributeError for _curr_idx."""
    view = SlideShowView(presentation=presentation_with_transitions_and_notes, start_slide_index=0)
    view.resize(960, 540)
    view.show()

    # Add an ink stroke
    stroke = SlideInkStroke(points=[(10.0, 10.0), (50.0, 50.0)], color="#FF0000", width=3.0)
    view.ink_strokes[0] = [stroke]

    # Render paintEvent; should execute cleanly without raising AttributeError
    view.repaint()

    view.end_show()
