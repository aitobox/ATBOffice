"""Regression tests for hard Qt/Python crash vectors and LecternWindow state bugs."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtWidgets import QGraphicsSceneMouseEvent

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.placeholder_resolver import (
    resolve_unoverridden_placeholders,
)
from atboffice.modules.presentation.models.presentation import (
    HeaderFooterSettings,
    Presentation,
)
from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.shape_item import (
    HandleType,
    ShapeGraphicsItem,
)
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.ui.shell.lectern_window import LecternWindow


def test_transform_handle_right_click_no_typeerror(qapp) -> None:
    """Non-left button events on TransformHandleItem must not raise TypeError."""
    slide = Slide(id="s1")
    shape = Shape(id="sh1", x=100.0, y=100.0, w=120.0, h=80.0, fill=Fill.solid("#FFFFFF"))
    slide.add_shape(shape)
    scene = SlideScene(slide=slide)
    item = scene.get_shape_item("sh1")
    assert item is not None
    handle = next(h for h in item._handles if h.handle_type == HandleType.SE)

    for ev_type in (
        QEvent.Type.GraphicsSceneMousePress,
        QEvent.Type.GraphicsSceneMouseMove,
        QEvent.Type.GraphicsSceneMouseRelease,
    ):
        ev = QGraphicsSceneMouseEvent(ev_type)
        ev.setButton(Qt.MouseButton.RightButton)
        ev.setButtons(Qt.MouseButton.RightButton)
        ev.setScenePos(QPointF(220.0, 180.0))
        if ev_type == QEvent.Type.GraphicsSceneMousePress:
            handle.mousePressEvent(ev)
        elif ev_type == QEvent.Type.GraphicsSceneMouseMove:
            handle.mouseMoveEvent(ev)
        else:
            handle.mouseReleaseEvent(ev)


def test_slide_scene_mouse_press_without_views_no_typeerror(qapp) -> None:
    """Clicking a standalone SlideScene with no attached views must not pass None to itemAt."""
    slide = Slide(id="s1")
    slide.add_shape(Shape(id="sh1", x=50.0, y=50.0, w=100.0, h=60.0))
    scene = SlideScene(slide=slide)
    assert scene.views() == []

    ev = QGraphicsSceneMouseEvent(QEvent.Type.GraphicsSceneMousePress)
    ev.setButton(Qt.MouseButton.LeftButton)
    ev.setButtons(Qt.MouseButton.LeftButton)
    ev.setScenePos(QPointF(75.0, 75.0))
    scene.mousePressEvent(ev)


def test_connector_cycle_does_not_recurse_infinitely(qapp) -> None:
    """Two mutually connected connectors must terminate cleanly without RecursionError."""
    slide = Slide(id="s1")
    conn_a = Shape(
        id="connA",
        type="line",
        geom="straightConnector1",
        x=10.0,
        y=10.0,
        w=100.0,
        h=40.0,
        line=Line(color="#000000", width=1.0),
        cxn_start={"id": "connB", "idx": 0},
    )
    conn_b = Shape(
        id="connB",
        type="line",
        geom="straightConnector1",
        x=120.0,
        y=60.0,
        w=100.0,
        h=40.0,
        line=Line(color="#000000", width=1.0),
        cxn_start={"id": "connA", "idx": 0},
    )
    slide.add_shape(conn_a)
    slide.add_shape(conn_b)
    scene = SlideScene(slide=slide)

    scene.update_connected_connectors("connA")
    item_b = scene.get_shape_item("connB")
    assert isinstance(item_b, ShapeGraphicsItem)
    item_b.update_connector_endpoints((0.0, 0.0), (50.0, 50.0))


def test_placeholder_resolver_empty_lt1_color_does_not_typeerror() -> None:
    """Empty lt1 string on ColorScheme must not cause round('', 2) TypeError."""
    design = build_design("default", 960.0, 540.0)
    design.colors.lt1 = ""
    design.placeholder_frames.pop("sldNum", None)
    pres = Presentation(
        designs={design.id: design},
        hf=HeaderFooterSettings(num=True),
    )
    slide = Slide(id="s1", design_id=design.id, layout="text")
    pres.slides.append(slide)

    resolved = resolve_unoverridden_placeholders(slide, pres)
    assert any(sh.placeholder and sh.placeholder.type == "sldNum" for sh in resolved)


def test_switching_slide_in_lectern_window_does_not_mark_dirty(qapp) -> None:
    """Navigating to another slide must update status bar without marking document modified."""
    win = LecternWindow(file_path=None)
    try:
        pres = Presentation.create_new()
        pres.add_slide(layout="text")
        win.presentation_view.load_presentation(pres)
        win.set_modified(False)
        assert not win.is_modified

        win.presentation_view.workspace.set_current_slide_index(1)
        qapp.processEvents()

        assert not win.is_modified
        assert "2 / 2" in win.lbl_status_slide.text()
    finally:
        win.close()
        win.deleteLater()
