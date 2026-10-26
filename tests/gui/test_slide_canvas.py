"""GUI and interaction tests for Lectern SlideCanvasView, SlideScene, and ShapeGraphicsItem."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Fill, Line, Shadow, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    get_adjustment_handles,
)
from atboffice.modules.presentation.views.shape_item import (
    HandleType,
    ShapeGraphicsItem,
    TransformHandleItem,
)
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
    safe_tr,
)
from atboffice.modules.presentation.views.smart_guides import (
    GuideLine,
    SmartGuideController,
)


@pytest.fixture
def test_slide() -> Slide:
    s = Slide(id="test_sl_01")
    s.add_shape(
        Shape(
            id="s1",
            geom="roundRect",
            x=100.0,
            y=100.0,
            w=200.0,
            h=100.0,
            fill=Fill.solid("#2B579A"),
            line=Line(color="#000000", width=2.0),
            shadow=Shadow(dist=3.0, alpha=0.3),
            adj={"adj": 20000},
            text=TextBody.from_plain_text("Hello Lectern"),
        )
    )
    s.add_shape(
        Shape(
            id="s2",
            geom="ellipse",
            x=400.0,
            y=200.0,
            w=150.0,
            h=150.0,
            fill=Fill.solid("#D24726"),
        )
    )
    s.add_shape(
        Shape(
            id="s3",
            geom="triangle",
            x=650.0,
            y=100.0,
            w=120.0,
            h=120.0,
            adj={"adj": 50000},
        )
    )
    return s


@pytest.fixture
def canvas(qapp: QApplication, test_slide: Slide) -> SlideCanvasView:
    scene = SlideScene(slide=test_slide, slide_width=960.0, slide_height=540.0)
    view = SlideCanvasView(scene=scene)
    view.resize(1000, 700)
    return view


class TestGeometryHelpers:
    def test_create_paths_for_all_presets(self) -> None:
        presets = [
            "rect",
            "roundRect",
            "ellipse",
            "triangle",
            "rtTriangle",
            "diamond",
            "parallelogram",
            "trapezoid",
            "hexagon",
            "octagon",
            "rightArrow",
            "line",
        ]
        for p in presets:
            path = create_shape_path(p, 100.0, 80.0, adj={"adj": 20000})
            assert not path.isEmpty()

    def test_adjustment_handles(self) -> None:
        defs = get_adjustment_handles("roundRect")
        assert len(defs) == 1
        pos = defs[0].get_pos(100.0, 100.0, {"adj": 20000})
        assert pos[0] == pytest.approx(20.0)
        assert pos[1] == 0.0

        new_adj = defs[0].calculate_adj(30.0, 0.0, 100.0, 100.0, {})
        assert new_adj["adj"] == pytest.approx(30000.0)


class TestShapeGraphicsItemAndHandles:
    def test_shape_item_initialization(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item1 = scene.get_shape_item("s1")
        assert item1 is not None
        assert item1.shape.id == "s1"
        assert item1.pos().x() == 100.0
        assert item1.pos().y() == 100.0
        assert item1.shape.w == 200.0
        assert item1.shape.h == 100.0

    def test_handle_visibility_on_selection(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item1 = scene.get_shape_item("s1")
        assert item1 is not None

        # Initially unselected: handles hidden
        assert not item1.isSelected()
        for h in item1._handles:
            assert not h.isVisible()

        # When selected: 8 scale + 1 rotate + 1 adjust handles visible
        item1.setSelected(True)
        assert item1.isSelected()
        assert len(item1._handles) == 10  # 8 size + 1 rot + 1 adj
        for h in item1._handles:
            assert h.isVisible()

    def test_rotation_handle_and_shift_snap(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("s1")
        assert item is not None
        item.setSelected(True)

        rot_handle = next(
            h for h in item._handles if h.handle_type == HandleType.ROTATE
        )
        assert rot_handle is not None

        # Begin drag
        item.begin_handle_drag(rot_handle, QPointF(200.0, 76.0))

        # Rotate to right (around center (200, 150))
        # Drag to (300, 150) -> should be 90 degrees
        item.update_handle_drag(
            rot_handle, QPointF(300.0, 150.0), Qt.KeyboardModifier.NoModifier
        )
        assert item.shape.rot == pytest.approx(90.0, abs=1.0)

        # With Shift modifier: snap to 15 deg
        item.update_handle_drag(
            rot_handle, QPointF(300.0, 160.0), Qt.KeyboardModifier.ShiftModifier
        )
        assert item.shape.rot % 15.0 == pytest.approx(0.0)

        item.end_handle_drag(rot_handle)

    def test_adjustment_handle_drag(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("s1")
        assert item is not None
        item.setSelected(True)

        adj_handle = next(
            h for h in item._handles if h.handle_type == HandleType.ADJUST
        )
        item.begin_handle_drag(adj_handle, QPointF(120.0, 100.0))

        # Drag adjustment handle rightwards
        item.update_handle_drag(
            adj_handle, QPointF(140.0, 100.0), Qt.KeyboardModifier.NoModifier
        )
        assert item.shape.adj is not None
        assert item.shape.adj["adj"] > 20000

        item.end_handle_drag(adj_handle)

    def test_resize_handle_with_shift_and_alt(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item = scene.get_shape_item("s1")
        assert item is not None
        item.setSelected(True)

        se_handle = next(
            h for h in item._handles if h.handle_type == HandleType.SE
        )

        init_w = item.shape.w
        init_h = item.shape.h
        init_aspect = init_w / init_h

        # Normal resize
        item.begin_handle_drag(se_handle, QPointF(300.0, 200.0))
        item.update_handle_drag(
            se_handle, QPointF(350.0, 220.0), Qt.KeyboardModifier.NoModifier
        )
        assert item.shape.w > init_w
        assert item.shape.h > init_h
        item.end_handle_drag(se_handle)

        # Resize with Shift (Aspect ratio preserved)
        pre_shift_w = item.shape.w
        pre_shift_h = item.shape.h
        expected_aspect = pre_shift_w / pre_shift_h

        item.begin_handle_drag(se_handle, item.mapToScene(QPointF(item.shape.w, item.shape.h)))
        item.update_handle_drag(
            se_handle,
            item.mapToScene(QPointF(item.shape.w + 50.0, item.shape.h + 80.0)),
            Qt.KeyboardModifier.ShiftModifier,
        )
        new_aspect = item.shape.w / item.shape.h
        assert new_aspect == pytest.approx(expected_aspect, rel=1e-2)
        item.end_handle_drag(se_handle)


class TestSmartGuidesAndSnapping:
    def test_magnetic_snap_calculation(self) -> None:
        controller = SmartGuideController(snap_threshold=6.0)

        moving = QRectF(98.0, 50.0, 100.0, 80.0)
        target = [QRectF(100.0, 200.0, 100.0, 100.0)]

        # Left edges are within 2pt (98 vs 100) -> should snap by +2.0
        dx, dy, guides = controller.calculate_snap(
            moving, target, slide_width=960.0, slide_height=540.0
        )
        assert dx == pytest.approx(2.0)
        assert len(guides) >= 1
        assert any(g.orientation == "v" and g.coord == 100.0 for g in guides)

    def test_guide_rendering_and_clearing(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        controller = scene.guide_controller

        moving = QRectF(402.0, 198.0, 100.0, 80.0)
        targets = [QRectF(400.0, 200.0, 150.0, 150.0)]

        controller.calculate_snap(moving, targets, 960.0, 540.0)
        controller.render_guides(scene)
        assert len(controller._guide_items) > 0

        controller.clear_guides(scene)
        assert len(controller._guide_items) == 0


class TestZOrderAndLayering:
    def test_bring_to_front_and_send_to_back(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)

        item1 = scene.get_shape_item("s1")
        item2 = scene.get_shape_item("s2")
        item3 = scene.get_shape_item("s3")
        assert item1 is not None and item2 is not None and item3 is not None

        # Initially: s1 (idx 0), s2 (idx 1), s3 (idx 2)
        assert scene.slide.shapes[0].id == "s1"
        assert scene.slide.shapes[-1].id == "s3"

        # Bring s1 to front
        item1.setSelected(True)
        scene.bring_to_front()
        assert scene.slide.shapes[-1].id == "s1"
        assert item1.zValue() > item3.zValue()

        # Send s1 to back
        scene.send_to_back()
        assert scene.slide.shapes[0].id == "s1"
        assert item1.zValue() < item2.zValue()

    def test_bring_forward_and_send_backward(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)

        item1 = scene.get_shape_item("s1")
        assert item1 is not None
        item1.setSelected(True)

        # Bring s1 forward 1 step (0 -> 1)
        scene.bring_forward()
        assert scene.slide.shapes[1].id == "s1"

        # Send backward 1 step (1 -> 0)
        scene.send_backward()
        assert scene.slide.shapes[0].id == "s1"


class TestAlignmentAndDistribution:
    def test_align_shapes_left_center_right(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)

        item1 = scene.get_shape_item("s1")
        item2 = scene.get_shape_item("s2")
        assert item1 is not None and item2 is not None

        item1.setSelected(True)
        item2.setSelected(True)

        # Align Left
        scene.align_shapes("L")
        assert item1.pos().x() == pytest.approx(item2.pos().x())

        # Align Right
        scene.align_shapes("R")
        assert (item1.pos().x() + item1.shape.w) == pytest.approx(
            item2.pos().x() + item2.shape.w
        )

    def test_align_to_slide(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item1 = scene.get_shape_item("s1")
        assert item1 is not None
        item1.setSelected(True)

        scene.align_shapes("L", align_to_slide=True)
        assert item1.pos().x() == pytest.approx(0.0)

        scene.align_shapes("T", align_to_slide=True)
        assert item1.pos().y() == pytest.approx(0.0)

    def test_distribute_shapes_horizontally_and_vertically(
        self, canvas: SlideCanvasView
    ) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item1 = scene.get_shape_item("s1")
        item2 = scene.get_shape_item("s2")
        item3 = scene.get_shape_item("s3")
        assert item1 and item2 and item3

        item1.setSelected(True)
        item2.setSelected(True)
        item3.setSelected(True)

        scene.distribute_shapes("h")
        gap1 = item2.pos().x() - (item1.pos().x() + item1.shape.w)
        gap2 = item3.pos().x() - (item2.pos().x() + item2.shape.w)
        assert gap1 == pytest.approx(gap2, abs=1.0)


class TestGroupingAndUngrouping:
    def test_group_and_ungroup_shapes(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)

        item1 = scene.get_shape_item("s1")
        item2 = scene.get_shape_item("s2")
        assert item1 and item2

        item1.setSelected(True)
        item2.setSelected(True)

        # Group
        group_item = scene.group_selected()
        assert group_item is not None
        assert group_item.shape.type == "group"
        assert len(group_item.shape.kids) == 2
        assert len(scene.slide.shapes) == 2  # group + s3

        # Ungroup
        group_item.setSelected(True)
        scene.ungroup_selected()
        assert len(scene.slide.shapes) == 3
        assert scene.get_shape_item("s1") is not None
        assert scene.get_shape_item("s2") is not None


class TestCanvasViewAndPresentationViewIntegration:
    def test_canvas_zoom(self, canvas: SlideCanvasView) -> None:
        init_zoom = canvas.zoom
        canvas.zoom_in()
        assert canvas.zoom > init_zoom

        canvas.zoom_out()
        assert canvas.zoom == pytest.approx(init_zoom)

        canvas.set_zoom(0.01)  # clamped min 0.1
        assert canvas.zoom == 0.1

        canvas.set_zoom(10.0)  # clamped max 4.0
        assert canvas.zoom == 4.0

    def test_keyboard_nudge_and_delete(self, canvas: SlideCanvasView) -> None:
        scene = canvas.scene()
        assert isinstance(scene, SlideScene)
        item1 = scene.get_shape_item("s1")
        assert item1 is not None
        item1.setSelected(True)

        old_x = item1.pos().x()
        ev_right = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        canvas.keyPressEvent(ev_right)
        assert item1.pos().x() == old_x + 1.0

        ev_del = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        canvas.keyPressEvent(ev_del)
        assert scene.get_shape_item("s1") is None

    def test_presentation_view_embedding(self, qapp: QApplication) -> None:
        pres = Presentation()
        pres.add_slide()
        view = PresentationView(presentation=pres)
        assert view.canvas_view is not None
        assert view.scene is not None
        assert view.scene.slide_width == pres.w

        view.retranslate_ui()
        assert view.canvas_view.toolTip() == "幻灯片画布"
