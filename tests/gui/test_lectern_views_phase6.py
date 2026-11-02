"""Tests for Lectern view matrix (Sorter, Notes, Master) and SlideShow HUD (Phase 6)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.slideshow.slide_hud import SlideShowHud
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView
from atboffice.modules.presentation.views.master_view import SlideMasterView
from atboffice.modules.presentation.views.notes_view import NotesPageView
from atboffice.modules.presentation.views.sorter_view import SlideSorterView
from atboffice.modules.presentation.views.workspace import LecternWorkspace
from atboffice.ui.shell.lectern_window import LecternWindow


@pytest.fixture
def phase6_presentation() -> Presentation:
    """Create a sample presentation with 4 distinct slides for view matrix testing."""
    pres = Presentation.create_new(title="Phase 6 Pres", empty=True)
    d = build_design("default", pres.w, pres.h)
    pres.designs[d.id] = d

    # Slide 1: Title slide with notes
    s1 = pres.add_slide(layout="title", design_id=d.id)
    s1.shapes[0].text = TextBody.from_plain_text("Phase 6 Title Slide")
    s1.notes = "Welcome to the presentation. This is slide 1 notes."

    # Slide 2: Text slide with transition
    s2 = pres.add_slide(layout="text", design_id=d.id)
    s2.shapes[0].text = TextBody.from_plain_text("Topic Overview")
    s2.transition = Transition(type="fade", speed="fast", after=4.0)
    s2.notes = "Discuss key agenda topics on slide 2."

    # Slide 3: Hidden slide
    s3 = pres.add_slide(layout="text", design_id=d.id)
    s3.shapes[0].text = TextBody.from_plain_text("Bonus Appendix")
    s3.hidden = True
    s3.notes = "Hidden backup material."

    # Slide 4: Regular slide
    s4 = pres.add_slide(layout="text", design_id=d.id)
    s4.shapes[0].text = TextBody.from_plain_text("Conclusion & Next Steps")
    s4.notes = "Wrap up and Q&A session."

    return pres


# ==============================================================================
# 1. Notes Page View Tests
# ==============================================================================


def test_notes_page_view_creation_and_rendering(qtbot, phase6_presentation: Presentation) -> None:
    """Test NotesPageView layout, paper elements, thumbnail preview, and initial speaker notes."""
    view = NotesPageView(presentation=phase6_presentation)
    qtbot.addWidget(view)
    view.show()

    assert view.current_slide_index == 0
    assert "1" in view.lbl_indicator.text()
    assert "4" in view.lbl_indicator.text()

    # Paper elements
    paper = view.paper
    assert paper.thumb_label.pixmap() is not None
    assert not paper.thumb_label.pixmap().isNull()
    assert "Welcome to the presentation" in paper.get_notes_text()
    assert paper.lbl_slide_num.text() == "1"


def test_notes_page_view_navigation_and_sync(qtbot, phase6_presentation: Presentation) -> None:
    """Test navigating through slides and bidirectional notes text synchronization."""
    view = NotesPageView(presentation=phase6_presentation)
    qtbot.addWidget(view)
    view.show()

    # Navigate to slide 2
    view.next_slide()
    assert view.current_slide_index == 1
    assert "2" in view.lbl_indicator.text()
    assert "Discuss key agenda topics" in view.paper.get_notes_text()

    # Edit notes in the text editor
    edited_text = "Updated speaker notes for slide 2."
    notes_events: list[tuple[int, str]] = []
    view.notes_changed.connect(lambda idx, txt: notes_events.append((idx, txt)))

    view.paper.notes_edit.setPlainText(edited_text)
    assert phase6_presentation.slides[1].notes == edited_text
    assert len(notes_events) > 0
    assert notes_events[-1] == (1, edited_text)

    # Navigate back to slide 1
    view.prev_slide()
    assert view.current_slide_index == 0
    assert "Welcome to the presentation" in view.paper.get_notes_text()

    # Return to slide 2 and verify persisted edited text
    view.next_slide()
    assert view.paper.get_notes_text() == edited_text

    # Zoom controls
    view.zoom_in()
    assert "110%" in view.lbl_zoom.text()
    view.zoom_out()
    assert "100%" in view.lbl_zoom.text()


def test_notes_page_view_empty_presentation(qtbot) -> None:
    """Test NotesPageView handles empty presentation gracefully without errors."""
    empty_pres = Presentation.create_new(title="Empty", empty=True)
    view = NotesPageView(presentation=empty_pres)
    qtbot.addWidget(view)
    view.show()

    assert not view.btn_prev.isEnabled()
    assert not view.btn_next.isEnabled()
    assert view.paper.notes_edit.toPlainText() == ""


# ==============================================================================
# 2. Slide Master View Tests
# ==============================================================================


def test_slide_master_view_creation_and_hierarchy(qtbot, phase6_presentation: Presentation) -> None:
    """Test SlideMasterView hierarchy tree, canvas loading, and placeholders."""
    master_view = SlideMasterView(presentation=phase6_presentation)
    qtbot.addWidget(master_view)
    master_view.show()

    # Verify hierarchy items
    assert master_view.master_list.count() == 2
    assert "幻灯片母版" in master_view.master_list.item(0).text()
    assert "标题母版" in master_view.master_list.item(1).text()

    # Verify default slide master has title, body, date, footer placeholders
    ms = master_view.master_slide
    assert ms is not None
    assert ms.is_master is True
    assert master_view.master_kind == "slide"

    placeholder_types = [s.placeholder.type for s in ms.shapes if s.placeholder]
    assert "title" in placeholder_types
    assert "body" in placeholder_types

    # Switch to title master
    master_view.set_master_kind("title")
    assert master_view.master_kind == "title"
    tm_placeholders = [s.placeholder.type for s in master_view.master_slide.shapes if s.placeholder]
    assert "ctrTitle" in tm_placeholders
    assert "subTitle" in tm_placeholders

    # Test close button emits signal
    close_emitted = []
    master_view.close_requested.connect(lambda: close_emitted.append(True))
    master_view.toolbar.btn_close.click()
    assert len(close_emitted) == 1


# ==============================================================================
# 3. Slide Sorter View Tests
# ==============================================================================


def test_slide_sorter_view_operations(qtbot, phase6_presentation: Presentation) -> None:
    """Test SlideSorterView multi-selection, drag reordering, and card interactions."""
    sorter = SlideSorterView(presentation=phase6_presentation)
    qtbot.addWidget(sorter)
    sorter.show()

    assert len(sorter.cards) == 4

    # Single selection
    sorter.select_slide(1)
    assert sorter.get_selected_indices() == {1}
    assert sorter.cards[1].is_selected

    # Multi selection range (Shift+Click)
    sorter.select_range(0, 2)
    assert sorter.get_selected_indices() == {0, 1, 2}

    # Reorder slides (move slide 0 to index 2)
    reordered_events = []
    sorter.slides_reordered.connect(lambda src, tgt: reordered_events.append((src, tgt)))
    sorter.move_slides([0], 2)
    assert len(reordered_events) == 1
    assert len(sorter.cards) == 4

    # Duplicate selected slides
    sorter.select_slide(1)
    orig_count = len(phase6_presentation.slides)
    sorter.duplicate_selected_slides()
    assert len(phase6_presentation.slides) == orig_count + 1

    # Delete selected slides
    sorter.select_slide(1)
    sorter.delete_selected_slides()
    assert len(phase6_presentation.slides) == orig_count


# ==============================================================================
# 4. SlideShow HUD Tests
# ==============================================================================


def test_slideshow_hud_controls_and_signals(qtbot, phase6_presentation: Presentation) -> None:
    """Test SlideShowHud button clicks, menus, and signal emissions."""
    hud = SlideShowHud(presentation=phase6_presentation)
    qtbot.addWidget(hud)
    hud.show()

    prev_called = []
    next_called = []
    end_called = []
    pen_events = []
    goto_events = []
    blank_events = []

    hud.prev_clicked.connect(lambda: prev_called.append(True))
    hud.next_clicked.connect(lambda: next_called.append(True))
    hud.end_clicked.connect(lambda: end_called.append(True))
    hud.pen_mode_changed.connect(lambda tool, col: pen_events.append((tool, col)))
    hud.goto_slide_requested.connect(lambda idx: goto_events.append(idx))
    hud.blank_screen_requested.connect(lambda col: blank_events.append(col))

    # Test prev / next / end buttons
    hud.btn_prev.click()
    assert len(prev_called) == 1

    hud.btn_next.click()
    assert len(next_called) == 1

    hud.btn_end.click()
    assert len(end_called) == 1

    # Test pen mode selection
    hud._select_pen_tool("pen")
    assert len(pen_events) > 0
    assert pen_events[-1][0] == "pen"

    hud._select_pen_color("#0066FF")
    assert pen_events[-1][1] == "#0066FF"

    hud._select_pen_tool("highlighter")
    assert pen_events[-1][0] == "highlighter"

    hud._select_pen_tool("eraser")
    assert pen_events[-1][0] == "eraser"

    hud._select_pen_tool("clear")
    assert pen_events[-1][0] == "clear"

    # Test fade in / fade out
    hud.fade_in()
    hud.fade_out()


def test_slideshow_view_hud_and_drawing(qtbot, phase6_presentation: Presentation) -> None:
    """Test SlideShowView integrates SlideShowHud, enables ink drawing, and exits safely."""
    view = SlideShowView(presentation=phase6_presentation, fullscreen=False)
    qtbot.addWidget(view)
    view.show()

    assert hasattr(view, "hud")
    assert view.hud is not None
    assert view.hud.parent() == view

    # Trigger HUD fade-in via bottom-left mouse hover
    pos_hover = QPointF(50.0, float(view.height() - 50))
    hover_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos_hover,
        pos_hover,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseMoveEvent(hover_event)

    # Switch to Pen mode and draw an ink stroke
    view._on_hud_pen_mode_changed("pen", "#FF0000")
    assert view.pen_tool == "pen"

    # Simulate mouse press & move to draw stroke
    p1 = QPointF(200.0, 200.0)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        p1,
        p1,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(press_event)

    p2 = QPointF(240.0, 240.0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseMoveEvent(move_event)

    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        p2,
        p2,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseReleaseEvent(release_event)

    # Verify ink stroke was recorded
    curr_idx = view.current_slide_index
    assert curr_idx in view.ink_strokes
    assert len(view.ink_strokes[curr_idx]) > 0
    stroke = view.ink_strokes[curr_idx][0]
    assert len(stroke.points) >= 1
    assert stroke.color == "#FF0000"

    # Test Clear Ink
    view._on_hud_pen_mode_changed("clear", "")
    assert len(view.ink_strokes.get(curr_idx, [])) == 0

    # Test Escape key exits show safely
    ended = []
    view.showEnded.connect(lambda: ended.append(True))
    esc_event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    view.keyPressEvent(esc_event)
    assert view.is_ended or len(ended) > 0


# ==============================================================================
# 5. Lectern Workspace & Window Integration Tests
# ==============================================================================


def test_lectern_workspace_all_four_views(qtbot, phase6_presentation: Presentation) -> None:
    """Test LecternWorkspace smooth transitions between Normal, Sorter, Notes, and Master views."""
    ws = LecternWorkspace(presentation=phase6_presentation)
    qtbot.addWidget(ws)
    ws.show()

    # 1. Normal View
    assert ws.view_mode == "normal"
    assert ws.center_normal_widget.isVisible()

    # 2. Sorter View
    ws.set_view_mode("sorter")
    assert ws.view_mode == "sorter"
    assert ws.sorter_view.isVisible()

    # 3. Notes Page View
    ws.set_view_mode("notes")
    assert ws.view_mode == "notes"
    assert ws.notes_view.isVisible()

    # Edit notes in notes_view and check sync to slide model
    ws.notes_view.paper.notes_edit.setPlainText("Notes from NotesPageView")
    assert phase6_presentation.slides[ws.current_slide_index].notes == "Notes from NotesPageView"

    # 4. Master View
    ws.set_view_mode("master")
    assert ws.view_mode == "master"
    assert ws.master_close_bar.isVisible()

    # Exit Master View
    ws.exit_master_view()
    assert ws.view_mode == "normal"
    assert not ws.master_close_bar.isVisible()


def test_lectern_window_status_bar_and_actions(qtbot, phase6_presentation: Presentation) -> None:
    """Test LecternWindow status bar buttons, viewMode actions, and retranslate_ui."""
    win = LecternWindow()
    qtbot.addWidget(win)
    win.presentation_view.load_presentation(phase6_presentation)
    win.show()

    # Check status bar view switcher buttons exist
    assert hasattr(win, "btn_view_normal")
    assert hasattr(win, "btn_view_sorter")
    assert hasattr(win, "btn_view_notes")
    assert hasattr(win, "btn_view_show")

    # Switch to sorter view via button
    win.btn_view_sorter.click()
    assert win.presentation_view.view_mode == "sorter"
    assert win.btn_view_sorter.isChecked()

    # Switch to notes view via button
    win.btn_view_notes.click()
    assert win.presentation_view.view_mode == "notes"
    assert win.btn_view_notes.isChecked()

    # Switch to normal view via action
    win.action_registry.trigger_action("viewNormal")
    assert win.presentation_view.view_mode == "normal"
    assert win.btn_view_normal.isChecked()

    # Switch to notes view via action
    win.action_registry.trigger_action("viewNotesPage")
    assert win.presentation_view.view_mode == "notes"
    assert win.btn_view_notes.isChecked()

    # Verify retranslate_ui executes cleanly without errors
    win.retranslate_ui()
    assert win.presentation_view.view_mode == "notes"
