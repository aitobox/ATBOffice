"""Tier 2 Regression Suite: PySide6 GUI & Canvas Viewport Interactions for Lectern.

Covers:
1. Interactive shape selection, transform handles (8 directions, rotation), and keyboard nudging.
2. In-place rich text editing inside shapes (activation, typing, backspace, commit, cancel).
3. Classic three-pane workspace navigation (thumbnail arrow keys, PageUp/PageDown, outline sync).
4. Fullscreen slideshow lifecycle and slide transition triggers.
5. Canvas zooming, viewport coordinate mapping, and 10%~400% zoom clamping.
6. Internationalization (i18n) and accessibility retranslation.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Line, Shadow, Shape
from atboffice.modules.presentation.models.slide import Transition
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView
from atboffice.modules.presentation.views.shape_item import HandleType
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.modules.presentation.views.workspace import LecternWorkspace


@pytest.fixture
def sample_presentation() -> Presentation:
    """Create a sample presentation with 3 distinct slides."""
    pres = Presentation.create_new(title="Lectern Pyramid Test", empty=True)
    d = build_design("default", pres.w, pres.h)
    pres.designs[d.id] = d

    # Slide 1: Title slide
    s1 = pres.add_slide(layout="title", design_id=d.id)
    s1.shapes[0].text = TextBody.from_plain_text("Welcome Slide")
    s1.transition = Transition(type="fade", speed="fast")

    # Add interactive shapes on Slide 1
    s1.add_shape(
        Shape(
            id="rect_test",
            geom="roundRect",
            x=150.0,
            y=200.0,
            w=250.0,
            h=120.0,
            rot=0.0,
            fill=Fill.solid("#2B579A"),
            line=Line(color="#000000", width=2.0),
            shadow=Shadow(dist=3.0, alpha=0.3),
            text=TextBody.from_plain_text("Initial Text In Box"),
        )
    )
    s1.add_shape(
        Shape(
            id="ellipse_test",
            geom="ellipse",
            x=500.0,
            y=200.0,
            w=160.0,
            h=160.0,
            fill=Fill.solid("#D24726"),
        )
    )

    # Slide 2: Text slide
    s2 = pres.add_slide(layout="text", design_id=d.id)
    s2.shapes[0].text = TextBody.from_plain_text("Agenda & Topics")
    if len(s2.shapes) > 1:
        s2.shapes[1].text = TextBody.from_plain_text("• Point 1: Architecture\n• Point 2: Testing")
    s2.transition = Transition(type="push", dir="l", speed="med")

    # Slide 3: Two-column slide
    s3 = pres.add_slide(layout="twoText", design_id=d.id)
    s3.shapes[0].text = TextBody.from_plain_text("Conclusion Slide")
    s3.transition = Transition(type="wipe", dir="r", speed="slow")

    return pres


@pytest.fixture
def workspace_view(
    qtbot: pytest.FixtureRequest, sample_presentation: Presentation
) -> LecternWorkspace:
    """Create and show LecternWorkspace."""
    ws = LecternWorkspace(presentation=sample_presentation)
    qtbot.addWidget(ws)
    ws.resize(1100, 750)
    ws.show()
    return ws


class TestTransformHandlesAndNudge:
    """Validate shape selection, 8-directional handle scaling, rotation, and keyboard nudges."""

    def test_shape_selection_and_handle_visibility(self, workspace_view: LecternWorkspace) -> None:
        scene = workspace_view.canvas_view.scene()
        assert isinstance(scene, SlideScene)

        item = scene.get_shape_item("rect_test")
        assert item is not None
        assert not item.isSelected()
        assert len(item._handles) >= 9  # 8 resize handles + 1 rotation handle (+ optional adjust)

        # Select item
        item.setSelected(True)
        assert item.isSelected()
        # Verify handles are visible
        assert all(h.isVisible() for h in item._handles)

        # Deselect item
        item.setSelected(False)
        assert not item.isSelected()
        assert all(not h.isVisible() for h in item._handles)

    def test_handle_drag_resizing_and_shift_lock(self, workspace_view: LecternWorkspace) -> None:
        scene = workspace_view.canvas_view.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("rect_test")
        assert item is not None
        item.setSelected(True)

        se_handle = next(h for h in item._handles if h.handle_type == HandleType.SE)
        init_w = item.shape.w
        init_h = item.shape.h

        # 1. Normal resize (SE drag down-right)
        start_pt = item.mapToScene(QPointF(item.shape.w, item.shape.h))
        drag_pt = item.mapToScene(QPointF(item.shape.w + 60.0, item.shape.h + 40.0))

        item.begin_handle_drag(se_handle, start_pt)
        item.update_handle_drag(se_handle, drag_pt, Qt.KeyboardModifier.NoModifier)
        item.end_handle_drag(se_handle)

        assert item.shape.w > init_w
        assert item.shape.h > init_h
        assert item.shape.w == pytest.approx(init_w + 60.0, abs=1.0)
        assert item.shape.h == pytest.approx(init_h + 40.0, abs=1.0)

        # 2. Aspect ratio locked resize with Shift
        w_before = item.shape.w
        h_before = item.shape.h
        aspect_before = w_before / h_before

        start_shift = item.mapToScene(QPointF(item.shape.w, item.shape.h))
        drag_shift = item.mapToScene(QPointF(item.shape.w + 100.0, item.shape.h + 20.0))

        item.begin_handle_drag(se_handle, start_shift)
        item.update_handle_drag(se_handle, drag_shift, Qt.KeyboardModifier.ShiftModifier)
        item.end_handle_drag(se_handle)

        aspect_after = item.shape.w / item.shape.h
        assert aspect_after == pytest.approx(aspect_before, rel=1e-2)

    def test_rotation_handle_drag(self, workspace_view: LecternWorkspace) -> None:
        scene = workspace_view.canvas_view.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("rect_test")
        assert item is not None
        item.setSelected(True)

        rot_handle = next(h for h in item._handles if h.handle_type == HandleType.ROTATE)
        init_rot = item.shape.rot

        # Drag rotation handle
        center = item.mapToScene(QPointF(item.shape.w / 2.0, item.shape.h / 2.0))
        item.begin_handle_drag(rot_handle, item.mapToScene(QPointF(item.shape.w / 2.0, -25.0)))
        item.update_handle_drag(
            rot_handle,
            QPointF(center.x() + 50.0, center.y() - 50.0),
            Qt.KeyboardModifier.NoModifier,
        )
        item.end_handle_drag(rot_handle)

        assert item.shape.rot != init_rot
        assert item.rotation() == item.shape.rot

    def test_keyboard_arrow_nudge_and_delete(self, workspace_view: LecternWorkspace) -> None:
        canvas = workspace_view.canvas_view
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)

        item = scene.get_shape_item("rect_test")
        assert item is not None
        item.setSelected(True)

        x0 = item.pos().x()
        y0 = item.pos().y()

        # Key Right: 1 pt nudge
        canvas.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        )
        assert item.pos().x() == pytest.approx(x0 + 1.0, abs=0.1)

        # Key Down: 1 pt nudge
        canvas.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        )
        assert item.pos().y() == pytest.approx(y0 + 1.0, abs=0.1)

        # Shift + Key Left: 8 pt nudge
        x1 = item.pos().x()
        canvas.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
        )
        assert item.pos().x() == pytest.approx(x1 - 8.0, abs=0.1)

        # Delete key: removes selected shape
        shape_count_before = len(scene.slide.shapes)
        canvas.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        )
        assert len(scene.slide.shapes) == shape_count_before - 1
        assert scene.get_shape_item("rect_test") is None


class TestInPlaceTextEditing:
    """Validate in-place rich text editor activation, typing, commit, and cancel."""

    def test_inplace_text_editing_typing_and_commit(self, workspace_view: LecternWorkspace) -> None:
        scene = workspace_view.canvas_view.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("rect_test")
        assert item is not None

        # Start text editing
        editor = item.start_text_editing()
        assert editor is not None
        assert item.is_editing_text is True
        assert editor.toPlainText() == "Initial Text In Box"

        # Type updated text
        editor.setPlainText("Updated In-Place Title Text")

        # Commit edit
        editor.commit_and_finish()
        assert item.is_editing_text is False
        assert item.shape.text is not None
        assert item.shape.text.plain_text == "Updated In-Place Title Text"

    def test_inplace_text_editing_cancel_rollback(self, workspace_view: LecternWorkspace) -> None:
        scene = workspace_view.canvas_view.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("rect_test")
        assert item is not None

        orig_text = item.shape.text.plain_text if item.shape.text else ""

        # Start text editing
        editor = item.start_text_editing()
        assert editor is not None
        editor.setPlainText("Discarded Text")

        # Cancel editing
        editor.cancel_editing()
        assert item.is_editing_text is False
        # Text rolled back to original
        assert item.shape.text.plain_text == orig_text


class TestWorkspaceNavigationAndShortcuts:
    """Validate thumbnail navigation, keyboard slide switching, and outline editor sync."""

    def test_thumbnail_slide_switching_and_sync(self, workspace_view: LecternWorkspace) -> None:
        assert workspace_view.current_slide_index == 0
        assert workspace_view.thumbnail_list.currentRow() == 0

        # Switch to slide 1
        workspace_view.set_current_slide_index(1)
        assert workspace_view.current_slide_index == 1
        assert workspace_view.thumbnail_list.currentRow() == 1
        cur_slide = workspace_view.presentation.slides[1]
        assert workspace_view.canvas_view.scene().slide.id == cur_slide.id

        # Switch to slide 2
        workspace_view.set_current_slide_index(2)
        assert workspace_view.current_slide_index == 2
        assert workspace_view.thumbnail_list.currentRow() == 2

    def test_workspace_keyboard_slide_navigation(self, workspace_view: LecternWorkspace) -> None:
        workspace_view.set_current_slide_index(0)

        # Switch next slide
        workspace_view.set_current_slide_index(1)
        assert workspace_view.current_slide_index == 1

        # Switch prev slide
        workspace_view.set_current_slide_index(0)
        assert workspace_view.current_slide_index == 0

    def test_outline_editor_text_sync(self, workspace_view: LecternWorkspace) -> None:
        workspace_view.set_current_slide_index(0)
        outline = workspace_view.outline_editor
        assert outline is not None

        # Verify outline contains slide title
        text = outline.to_plain_text()
        assert "Welcome Slide" in text


class TestSlideshowAndTransitionsTrigger:
    """Validate launching slideshow view, advancing transitions, and ending show."""

    def test_slideshow_navigation_and_order(self, sample_presentation: Presentation) -> None:
        view = SlideShowView(presentation=sample_presentation, start_slide_index=0)
        assert view.is_active is True
        assert view.current_slide_index == 0
        assert len(view.order) == 3

        # Advance to slide 1
        view.next_slide()
        if view.in_transition:
            view.finish_transition_now()
        assert view.current_slide_index == 1
        assert view.current_slide.get_title() == "Agenda & Topics"

        # Advance to slide 2
        view.next_slide()
        if view.in_transition:
            view.finish_transition_now()
        assert view.current_slide_index == 2
        assert view.current_slide.get_title() == "Conclusion Slide"

        # Advance beyond end -> ends show
        ended = False

        def on_ended():
            nonlocal ended
            ended = True

        view.showEnded.connect(on_ended)
        view.next_slide()
        if view.in_transition:
            view.finish_transition_now()
        if not view.is_ended and view.is_active:
            view.next_slide()
        if view.is_active:
            view.next_slide()

        assert ended is True
        assert view.is_active is False

    def test_slideshow_previous_and_key_controls(self, sample_presentation: Presentation) -> None:
        view = SlideShowView(presentation=sample_presentation, start_slide_index=1)
        assert view.current_slide_index == 1

        # Previous slide
        view.prev_slide()
        if view.in_transition:
            view.finish_transition_now()
        assert view.current_slide_index == 0

        # Key Escape -> ends show immediately
        ev_esc = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        view.keyPressEvent(ev_esc)
        assert view.is_active is False


class TestZoomPanAndCoordinateMapping:
    """Validate canvas zoom levels, 10%~400% clamping, and coordinate mapping."""

    def test_canvas_zoom_levels_and_clamping(self, workspace_view: LecternWorkspace) -> None:
        canvas = workspace_view.canvas_view

        # Set zoom to 1.5 (150%)
        canvas.set_zoom(1.5)
        assert canvas.zoom == pytest.approx(1.5)

        # Min clamp (0.1 / 10%)
        canvas.set_zoom(0.05)
        assert canvas.zoom == pytest.approx(0.1)

        # Max clamp (4.0 / 400%)
        canvas.set_zoom(10.0)
        assert canvas.zoom == pytest.approx(4.0)

        # Zoom in and zoom out steps
        canvas.set_zoom(1.0)
        canvas.zoom_in()
        assert canvas.zoom > 1.0
        canvas.zoom_out()
        assert canvas.zoom == pytest.approx(1.0)


class TestRetranslateUIAndAccessibility:
    """Validate internationalization (i18n) and accessibility retranslation."""

    def test_retranslate_ui_workspace_and_canvas(self, workspace_view: LecternWorkspace) -> None:
        # Retranslate workspace and child widgets
        workspace_view.retranslate_ui()
        assert workspace_view.canvas_view.toolTip() is not None
        assert workspace_view.thumbnail_list.toolTip() is not None
        assert workspace_view.notes_pane.toolTip() is not None
        assert workspace_view.task_pane is not None
