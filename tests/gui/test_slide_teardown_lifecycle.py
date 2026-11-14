"""GUI lifecycle tests for SlideScene teardown, text focus, and open rollback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.views.slide_canvas import SlideCanvasView, SlideScene
from atboffice.ui.shell.lectern_window import LecternWindow


def test_load_slide_while_text_editor_focused_no_crash_or_runtimeerror(qapp) -> None:
    """Reloading slides while ShapeTextEditorItem owns focus finishes editing safely."""
    slide1 = Slide(id="s1")
    slide1.add_shape(
        Shape(id="sh1", x=40.0, y=40.0, w=200.0, h=80.0, text=TextBody.from_text("Hello"))
    )
    slide2 = Slide(id="s2")
    slide2.add_shape(Shape(id="sh2", x=60.0, y=60.0, w=200.0, h=80.0))

    scene = SlideScene(slide=slide1)
    view = SlideCanvasView(scene)
    view.show()
    qapp.processEvents()

    item = scene.get_shape_item("sh1")
    assert item is not None
    editor = item.start_text_editing()
    assert item.is_editing_text
    assert editor is not None
    qapp.processEvents()

    # Track any signal emitted during scene load teardown
    reentrant_selected: list[int] = []
    scene.selectionChanged.connect(lambda: reentrant_selected.append(len(scene._items_by_id)))

    scene.load_slide(slide2)
    qapp.processEvents()

    assert not item.is_editing_text
    assert scene.slide is slide2
    assert not scene._is_loading_slide
    view.close()
    view.deleteLater()


def test_load_slide_resets_drag_state_and_handles_duplicate_shape_ids(qapp) -> None:
    """Reloading a slide must reset stale drag state and avoid losing duplicate shape IDs."""
    slide1 = Slide(id="s1")
    slide1.add_shape(Shape(id="dup", x=10.0, y=10.0, w=80.0, h=50.0))
    scene = SlideScene(slide=slide1)
    scene._dragged_item = scene.get_shape_item("dup")
    scene._is_dragging_item = True

    slide2 = Slide(id="s2")
    s_a = Shape(id="dup_id", name="A", x=10.0, y=10.0, w=80.0, h=50.0)
    s_b = Shape(id="dup_id", name="B", x=120.0, y=10.0, w=80.0, h=50.0)
    slide2.add_shape(s_a)
    slide2.add_shape(s_b)

    scene.load_slide(slide2)

    assert scene._dragged_item is None
    assert scene._is_dragging_item is False
    assert len(scene._items_by_id) == 2
    assert s_a.id != s_b.id


def test_focus_out_after_scene_clear_is_noop(qapp) -> None:
    """Calling focusOutEvent on a detached/stale ShapeTextEditorItem must not crash."""
    slide = Slide(id="s1")
    slide.add_shape(
        Shape(id="sh1", x=20.0, y=20.0, w=150.0, h=60.0, text=TextBody.from_text("Text"))
    )
    scene = SlideScene(slide=slide)
    item = scene.get_shape_item("sh1")
    assert item is not None
    editor = item.start_text_editing()
    assert editor is not None

    # Simulate scene clearing before stale focusOut arrives
    scene._is_loading_slide = True
    try:
        ev = QFocusEvent(QFocusEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason)
        editor.focusOutEvent(ev)
    finally:
        scene._is_loading_slide = False

    # Now finish editing cleanly and fire another focusOut when orphaned
    scene.finish_active_text_editing(commit=False)
    ev2 = QFocusEvent(QFocusEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason)
    editor.focusOutEvent(ev2)


def test_lectern_do_open_closes_editing_and_preserves_clean_state_on_failure(
    qapp, tmp_path: Path
) -> None:
    """do_open ends active editing cleanly and preserves prior state if open fails."""
    win = LecternWindow(file_path=None)
    try:
        pres = Presentation.create_new()
        sh = Shape(id="edit_me", x=50.0, y=50.0, w=180.0, h=70.0, text=TextBody.from_text("Old"))
        pres.slides[0].add_shape(sh)
        win.presentation_view.load_presentation(pres)
        win.set_modified(False)

        ws = win.presentation_view.workspace
        item = ws.scene.get_shape_item("edit_me")
        assert item is not None
        item.start_text_editing()
        assert item.is_editing_text

        bad_file = tmp_path / "broken.pptx"
        bad_file.write_bytes(b"not-a-zip")

        with patch(
            "atboffice.modules.presentation.io.pptx_reader.read_pptx",
            side_effect=ValueError("simulated corrupt pptx"),
        ):
            raised = False
            try:
                win.do_open(bad_file)
            except ValueError:
                raised = True
            assert raised

        assert not item.is_editing_text
        assert win.presentation_view.presentation is pres
        assert not win.is_modified
    finally:
        win.close()
        win.deleteLater()
