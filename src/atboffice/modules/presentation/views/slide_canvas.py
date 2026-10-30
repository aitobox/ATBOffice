"""High-performance interactive SlideCanvasView and SlideScene for Lectern."""

from __future__ import annotations

import uuid
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QMenu,
    QWidget,
)

from atboffice.modules.presentation.models.comment import Comment
from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.views.comment_overlay import (
    CommentCardWidget,
    CommentMarkerItem,
)
from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem
from atboffice.modules.presentation.views.smart_guides import SmartGuideController


def safe_tr(text: str) -> str:
    """Translate UI text with fallbacks."""
    app = QApplication.instance()
    if app:
        translated = app.translate("SlideCanvas", text)
        if translated and translated != text:
            return translated
    # Default to Chinese native text for ATBOffice
    return text


class SlideScene(QGraphicsScene):
    """QGraphicsScene representing a single Slide canvas with Smart Guides & layout tools."""

    selectionChangedCustom = Signal()
    commentClicked = Signal(object)
    shapeCreated = Signal(object)
    toolChanged = Signal(object)

    def __init__(
        self,
        slide: Slide | None = None,
        slide_width: float = 960.0,
        slide_height: float = 540.0,
        presentation: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide_width = float(slide_width)
        self.slide_height = float(slide_height)
        self.presentation = presentation
        self.slide: Slide = slide or Slide(id=f"sl_{uuid.uuid4().hex[:8]}")

        self.current_tool: dict[str, Any] | None = None
        self._is_drawing_shape: bool = False
        self._draw_start_pos: QPointF | None = None

        self.guide_controller = SmartGuideController(snap_threshold=6.0)
        self._items_by_id: dict[str, ShapeGraphicsItem] = {}
        self._comment_items: list[CommentMarkerItem] = []
        self._is_dragging_item = False
        self._dragged_item: ShapeGraphicsItem | None = None

        self.setSceneRect(
            -150.0,
            -100.0,
            self.slide_width + 300.0,
            self.slide_height + 200.0,
        )
        self.load_slide(self.slide)

    def load_slide(self, slide: Slide) -> None:
        """Load a slide model and populate graphics items."""
        self.slide = slide
        self.clear()
        self._items_by_id.clear()
        self._comment_items.clear()

        for idx, sh in enumerate(slide.shapes):
            if sh.is_chart:
                from atboffice.modules.presentation.views.chart_item import ChartGraphicsItem

                item = ChartGraphicsItem(sh)
            else:
                item = ShapeGraphicsItem(sh)
            item.setZValue(float(idx))
            self.addItem(item)
            self._items_by_id[sh.id] = item

        for cm in slide.comments:
            marker = CommentMarkerItem(
                cm,
                self.presentation,
                on_click=self._on_comment_marker_clicked,
            )
            self.addItem(marker)
            self._comment_items.append(marker)

    def _on_comment_marker_clicked(self, marker: CommentMarkerItem) -> None:
        self.commentClicked.emit(marker.comment)
        for v in self.views():
            if hasattr(v, "show_comment_card"):
                v.show_comment_card(marker.comment)

    def add_comment_at(self, x: float, y: float, text: str = "") -> Comment:
        """Create and add a new Comment at (x, y) coordinates."""
        pres = self.presentation
        author_id = "0"
        if pres:
            author = pres.get_or_create_author(safe_tr("审阅人"))
            author_id = author.id

        idx = 1
        for cm in self.slide.comments:
            if cm.author_id == author_id:
                idx = max(idx, cm.idx + 1)

        new_cm = Comment(
            id=f"cm_{uuid.uuid4().hex[:8]}",
            author_id=author_id,
            text=text,
            x=round(x, 2),
            y=round(y, 2),
            idx=idx,
        )
        self.slide.comments.append(new_cm)
        marker = CommentMarkerItem(
            new_cm,
            self.presentation,
            on_click=self._on_comment_marker_clicked,
        )
        self.addItem(marker)
        self._comment_items.append(marker)
        self.commentClicked.emit(new_cm)
        self.update()
        return new_cm

    def remove_comment(self, comment: Comment) -> None:
        """Remove a comment and its marker item from the scene."""
        if comment in self.slide.comments:
            self.slide.comments.remove(comment)
        to_remove = [m for m in self._comment_items if m.comment == comment]
        for m in to_remove:
            self.removeItem(m)
            self._comment_items.remove(m)
        self.update()

    def get_comment_markers(self) -> list[CommentMarkerItem]:
        return list(self._comment_items)

    def get_shape_item(self, shape_id: str) -> ShapeGraphicsItem | None:
        return self._items_by_id.get(shape_id)

    def selected_shape_items(self) -> list[ShapeGraphicsItem]:
        return [
            item for item in self.selectedItems() if isinstance(item, ShapeGraphicsItem)
        ]

    # ------------------------------------------------------------------
    # Background rendering (Slide paper & shadow)
    # ------------------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        # Fill whole canvas workspace with neutral gray
        painter.fillRect(rect, QColor("#EBEBEB"))

        slide_rect = QRectF(0.0, 0.0, self.slide_width, self.slide_height)

        # Drop shadow around slide
        shadow_rect = slide_rect.translated(4.0, 4.0)
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 40))

        # White slide paper
        painter.fillRect(slide_rect, QColor("#FFFFFF"))

        # Thin border around slide
        border_pen = QPen(QColor(180, 180, 180), 1.0)
        painter.setPen(border_pen)
        painter.drawRect(slide_rect)

    # ------------------------------------------------------------------
    # Drawing Tool & Shape Creation
    # ------------------------------------------------------------------
    def set_drawing_tool(self, tool: dict[str, Any] | None) -> None:
        """Activate or cancel drawing tool mode."""
        self.current_tool = tool
        self._is_drawing_shape = False
        self._draw_start_pos = None
        for v in self.views():
            if hasattr(v, "update_tool_cursor"):
                v.update_tool_cursor()
        self.toolChanged.emit(tool)

    def _create_shape_from_tool(self, tool: dict[str, Any], p0: QPointF, p1: QPointF) -> Shape:
        x0, y0 = p0.x(), p0.y()
        x1, y1 = p1.x(), p1.y()
        x = min(x0, x1)
        y = min(y0, y1)
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        kind = tool.get("kind", "shape")
        geom = tool.get("geom", "rect")

        shape_id = f"sh_{uuid.uuid4().hex[:8]}"

        if kind == "text":
            w = max(w, 100.0)
            h = max(h, 28.8)
            new_sh = Shape(
                id=shape_id,
                type="text",
                geom="rect",
                name="TextBox",
                x=round(x, 2),
                y=round(y, 2),
                w=round(w, 2),
                h=round(h, 2),
                fill=Fill.none(),
                line=Line.none(),
                text=TextBody.from_text(safe_tr("单击此处添加文本")),
            )
        elif kind == "line":
            if geom == "rightArrow" or tool.get("arrows") == "end":
                w = max(w, 60.0)
                h = max(h, 24.0)
                new_sh = Shape(
                    id=shape_id,
                    type="shape",
                    geom="rightArrow",
                    name="Arrow",
                    x=round(x, 2),
                    y=round(y, 2),
                    w=round(w, 2),
                    h=round(h, 2),
                    fill=Fill.solid("#4B9CD3"),
                    line=Line(color="#2E6B9E", width=1.0),
                )
            else:
                w = max(w, 60.0)
                h = max(h, 2.0)
                new_sh = Shape(
                    id=shape_id,
                    type="line",
                    geom="line",
                    name="Line",
                    x=round(x, 2),
                    y=round(y, 2),
                    w=round(w, 2),
                    h=round(h, 2),
                    fill=Fill.none(),
                    line=Line(color="#000000", width=1.5),
                )
        elif geom in ("ellipse", "oval"):
            w = max(w, 60.0)
            h = max(h, 60.0)
            new_sh = Shape(
                id=shape_id,
                type="shape",
                geom="ellipse",
                name="Oval",
                x=round(x, 2),
                y=round(y, 2),
                w=round(w, 2),
                h=round(h, 2),
                fill=Fill.solid("#5B9BD5"),
                line=Line(color="#41719C", width=1.0),
            )
        else:
            w = max(w, 60.0)
            h = max(h, 60.0)
            new_sh = Shape(
                id=shape_id,
                type="shape",
                geom=geom,
                name="Rectangle",
                x=round(x, 2),
                y=round(y, 2),
                w=round(w, 2),
                h=round(h, 2),
                fill=Fill.solid("#5B9BD5"),
                line=Line(color="#41719C", width=1.0),
            )

        self.slide.shapes.append(new_sh)
        item = ShapeGraphicsItem(new_sh)
        item.setZValue(float(len(self.slide.shapes) - 1))
        self.addItem(item)
        self._items_by_id[new_sh.id] = item
        item.setSelected(True)
        self.shapeCreated.emit(new_sh)
        self.update()
        return new_sh

    # ------------------------------------------------------------------
    # Mouse events & Smart Guide magnetic snapping
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.current_tool and event.button() == Qt.MouseButton.LeftButton:
            self.clearSelection()
            self._is_drawing_shape = True
            self._draw_start_pos = event.scenePos()
            event.accept()
            return

        item = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else None)
        # Commit any active text editor if clicked outside
        for it in list(self._items_by_id.values()):
            if it.is_editing_text and it != item and getattr(it, "_text_editor", None) != item:
                it.finish_text_editing()

        if isinstance(item, ShapeGraphicsItem):
            self._dragged_item = item
            self._is_dragging_item = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._is_drawing_shape:
            event.accept()
            return

        super().mouseMoveEvent(event)

        is_dragging = (
            self._is_dragging_item
            and self._dragged_item
            and bool(event.buttons() & Qt.MouseButton.LeftButton)
        )
        if is_dragging and self._dragged_item:
            moving_rect = QRectF(
                self._dragged_item.pos().x(),
                self._dragged_item.pos().y(),
                self._dragged_item.shape.w,
                self._dragged_item.shape.h,
            )

            # Target rects from other shapes
            target_rects: list[QRectF] = []
            for other in self._items_by_id.values():
                if other is not self._dragged_item:
                    target_rects.append(
                        QRectF(
                            other.pos().x(),
                            other.pos().y(),
                            other.shape.w,
                            other.shape.h,
                        )
                    )

            dx, dy, guides = self.guide_controller.calculate_snap(
                moving_rect, target_rects, self.slide_width, self.slide_height
            )

            if abs(dx) > 0.001 or abs(dy) > 0.001:
                new_pos = self._dragged_item.pos() + QPointF(dx, dy)
                self._dragged_item.setPos(new_pos)

            self.guide_controller.render_guides(self)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if (
            self._is_drawing_shape
            and self._draw_start_pos
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._is_drawing_shape = False
            p0 = self._draw_start_pos
            p1 = event.scenePos()
            self._draw_start_pos = None

            tool = self.current_tool or {}
            self._create_shape_from_tool(tool, p0, p1)
            self.set_drawing_tool(None)
            event.accept()
            return

        super().mouseReleaseEvent(event)
        self._is_dragging_item = False
        self._dragged_item = None
        self.guide_controller.clear_guides(self)

    # ------------------------------------------------------------------
    # Z-Order Operations
    # ------------------------------------------------------------------
    def bring_to_front(self) -> None:
        selected = self.selected_shape_items()
        if not selected:
            return
        for item in selected:
            if item.shape in self.slide.shapes:
                self.slide.shapes.remove(item.shape)
                self.slide.shapes.append(item.shape)
        self._sync_z_values()

    def send_to_back(self) -> None:
        selected = self.selected_shape_items()
        if not selected:
            return
        for item in reversed(selected):
            if item.shape in self.slide.shapes:
                self.slide.shapes.remove(item.shape)
                self.slide.shapes.insert(0, item.shape)
        self._sync_z_values()

    def bring_forward(self) -> None:
        selected = self.selected_shape_items()
        if not selected:
            return
        for item in reversed(selected):
            sh = item.shape
            if sh in self.slide.shapes:
                idx = self.slide.shapes.index(sh)
                if idx < len(self.slide.shapes) - 1:
                    self.slide.shapes[idx], self.slide.shapes[idx + 1] = (
                        self.slide.shapes[idx + 1],
                        self.slide.shapes[idx],
                    )
        self._sync_z_values()

    def send_backward(self) -> None:
        selected = self.selected_shape_items()
        if not selected:
            return
        for item in selected:
            sh = item.shape
            if sh in self.slide.shapes:
                idx = self.slide.shapes.index(sh)
                if idx > 0:
                    self.slide.shapes[idx], self.slide.shapes[idx - 1] = (
                        self.slide.shapes[idx - 1],
                        self.slide.shapes[idx],
                    )
        self._sync_z_values()

    def _sync_z_values(self) -> None:
        for idx, sh in enumerate(self.slide.shapes):
            item = self._items_by_id.get(sh.id)
            if item:
                item.setZValue(float(idx))
        self.update()

    # ------------------------------------------------------------------
    # Alignment and Distribution
    # ------------------------------------------------------------------
    def align_shapes(self, mode: str, align_to_slide: bool = False) -> None:
        """Align selected shapes ('L', 'C', 'R', 'T', 'M', 'B')."""
        selected = self.selected_shape_items()
        if not selected:
            return

        to_slide = align_to_slide or len(selected) == 1
        if to_slide:
            ref = QRectF(0.0, 0.0, self.slide_width, self.slide_height)
        else:
            ref = QRectF(
                selected[0].pos().x(),
                selected[0].pos().y(),
                selected[0].shape.w,
                selected[0].shape.h,
            )
            for it in selected[1:]:
                ref = ref.united(
                    QRectF(it.pos().x(), it.pos().y(), it.shape.w, it.shape.h)
                )

        for it in selected:
            rect = QRectF(it.pos().x(), it.pos().y(), it.shape.w, it.shape.h)
            dx = 0.0
            dy = 0.0
            if mode == "L":
                dx = ref.left() - rect.left()
            elif mode == "C":
                dx = ref.center().x() - rect.center().x()
            elif mode == "R":
                dx = ref.right() - rect.right()
            elif mode == "T":
                dy = ref.top() - rect.top()
            elif mode == "M":
                dy = ref.center().y() - rect.center().y()
            elif mode == "B":
                dy = ref.bottom() - rect.bottom()

            it.setPos(it.pos().x() + dx, it.pos().y() + dy)
            it.shape.x = round(it.pos().x(), 2)
            it.shape.y = round(it.pos().y(), 2)
        self.update()

    def distribute_shapes(self, axis: str = "h") -> None:
        """Distribute selected shapes evenly along 'h' (horizontal) or 'v' (vertical) axis."""
        selected = self.selected_shape_items()
        if len(selected) < 2:
            return

        if axis == "h":
            sorted_items = sorted(selected, key=lambda it: it.pos().x())
            total_w = sum(it.shape.w for it in sorted_items)
            last_x = sorted_items[-1].pos().x() + sorted_items[-1].shape.w
            span_w = last_x - sorted_items[0].pos().x()
            gap = max(0.0, (span_w - total_w) / max(1, len(sorted_items) - 1))

            cur_x = sorted_items[0].pos().x()
            for it in sorted_items:
                it.setPos(cur_x, it.pos().y())
                it.shape.x = round(cur_x, 2)
                cur_x += it.shape.w + gap
        else:
            sorted_items = sorted(selected, key=lambda it: it.pos().y())
            total_h = sum(it.shape.h for it in sorted_items)
            last_y = sorted_items[-1].pos().y() + sorted_items[-1].shape.h
            span_h = last_y - sorted_items[0].pos().y()
            gap = max(0.0, (span_h - total_h) / max(1, len(sorted_items) - 1))

            cur_y = sorted_items[0].pos().y()
            for it in sorted_items:
                it.setPos(it.pos().x(), cur_y)
                it.shape.y = round(cur_y, 2)
                cur_y += it.shape.h + gap
        self.update()

    # ------------------------------------------------------------------
    # Group / Ungroup
    # ------------------------------------------------------------------
    def group_selected(self) -> ShapeGraphicsItem | None:
        """Group multiple selected shapes into a single group shape."""
        selected = self.selected_shape_items()
        if len(selected) < 2:
            return None

        # Determine union bounds
        union_rect = selected[0].sceneBoundingRect()
        for it in selected[1:]:
            union_rect = union_rect.united(it.sceneBoundingRect())

        ordered_shapes = [it.shape for it in selected]
        group_shape = Shape(
            id=f"grp_{uuid.uuid4().hex[:8]}",
            type="group",
            name=f"Group {len(self.slide.shapes) + 1}",
            x=round(union_rect.x(), 2),
            y=round(union_rect.y(), 2),
            w=round(union_rect.width(), 2),
            h=round(union_rect.height(), 2),
            kids=ordered_shapes,
        )

        for it in selected:
            self.slide.remove_shape(it.shape.id)
        self.slide.add_shape(group_shape)

        self.load_slide(self.slide)
        new_item = self.get_shape_item(group_shape.id)
        if new_item:
            new_item.setSelected(True)
        return new_item

    def ungroup_selected(self) -> list[ShapeGraphicsItem]:
        """Ungroup any selected group shapes."""
        selected = self.selected_shape_items()
        unpacked_items: list[ShapeGraphicsItem] = []

        for it in selected:
            if it.shape.type == "group" and it.shape.kids:
                self.slide.remove_shape(it.shape.id)
                for kid in it.shape.kids:
                    self.slide.add_shape(kid)

        self.load_slide(self.slide)
        return unpacked_items

    def delete_selected(self) -> None:
        """Delete selected shapes from the slide."""
        selected = self.selected_shape_items()
        for it in selected:
            self.slide.remove_shape(it.shape.id)
        self.load_slide(self.slide)


class SlideCanvasView(QGraphicsView):
    """QGraphicsView displaying the SlideScene with zoom, context menu, and keyboard controls."""

    def __init__(
        self,
        scene: SlideScene | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = scene or SlideScene()
        self.setScene(self._scene)

        self._active_card: CommentCardWidget | None = None
        self.zoom = 1.0
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )
        self.retranslate_ui()

    def update_tool_cursor(self) -> None:
        """Update viewport cursor according to active scene drawing tool."""
        if self._scene and getattr(self._scene, "current_tool", None):
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def set_drawing_tool(self, tool: dict[str, Any] | None) -> None:
        """Forward drawing tool selection to scene and update viewport cursor."""
        if self._scene:
            self._scene.set_drawing_tool(tool)
        self.update_tool_cursor()

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale (clamped between 0.1 and 4.0)."""
        clamped = max(0.1, min(zoom, 4.0))
        self.zoom = clamped
        self.resetTransform()
        self.scale(self.zoom, self.zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom * 0.8)

    def zoom_fit(self) -> None:
        """Fit slide canvas into current viewport."""
        vw = float(self.viewport().width())
        vh = float(self.viewport().height())
        if vw > 0 and vh > 0:
            margin = 32.0
            scale_x = (vw - margin) / self._scene.slide_width
            scale_y = (vh - margin) / self._scene.slide_height
            self.set_zoom(min(scale_x, scale_y))

    def retranslate_ui(self) -> None:
        """Update internationalized tooltip and accessible descriptions."""
        self.setToolTip(safe_tr("幻灯片画布"))
        self.viewport().setAccessibleDescription(
            safe_tr("幻灯片自由交互编辑画布 (PowerPoint 2003 视图)")
        )

    def insert_comment_at(self, x: float, y: float, text: str = "") -> Comment:
        """Insert a comment at given canvas coordinates and present card."""
        cm = self._scene.add_comment_at(x, y, text=text)
        self.show_comment_card(cm)
        return cm

    def show_comment_card(self, comment: Comment) -> None:
        """Display interactive comment card overlay next to comment position."""
        if self._active_card:
            self._active_card.close()
            self._active_card = None

        pres = getattr(self._scene, "presentation", None)
        if not pres:
            from atboffice.modules.presentation.models.presentation import Presentation

            pres = Presentation()
            self._scene.presentation = pres

        card = CommentCardWidget(comment, pres, parent=self)
        self._active_card = card

        view_pos = self.mapFromScene(QPointF(comment.x, comment.y))
        card.move(int(view_pos.x() + 35), int(view_pos.y()))
        card.commentDeleted.connect(lambda c: self._scene.remove_comment(c))
        card.show()
        card.raise_()
        card.text_edit.setFocus()

    # ------------------------------------------------------------------
    # Context Menu
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event: Any) -> None:
        menu = QMenu(self)

        act_comment = menu.addAction(safe_tr("插入批注"))
        scene_pos = self.mapToScene(event.pos())
        act_comment.triggered.connect(
            lambda: self.insert_comment_at(scene_pos.x(), scene_pos.y())
        )
        menu.addSeparator()

        # Z-Order submenu
        order_menu = menu.addMenu(safe_tr("叠放次序"))
        act_front = order_menu.addAction(safe_tr("置于顶层"))
        act_back = order_menu.addAction(safe_tr("置于底层"))
        act_forward = order_menu.addAction(safe_tr("上移一层"))
        act_backward = order_menu.addAction(safe_tr("下移一层"))

        act_front.triggered.connect(self._scene.bring_to_front)
        act_back.triggered.connect(self._scene.send_to_back)
        act_forward.triggered.connect(self._scene.bring_forward)
        act_backward.triggered.connect(self._scene.send_backward)

        # Alignment submenu
        align_menu = menu.addMenu(safe_tr("对齐方式"))
        act_al = align_menu.addAction(safe_tr("左对齐"))
        act_ac = align_menu.addAction(safe_tr("水平居中"))
        act_ar = align_menu.addAction(safe_tr("右对齐"))
        align_menu.addSeparator()
        act_at = align_menu.addAction(safe_tr("顶端对齐"))
        act_am = align_menu.addAction(safe_tr("垂直居中"))
        act_ab = align_menu.addAction(safe_tr("底端对齐"))
        align_menu.addSeparator()
        act_dh = align_menu.addAction(safe_tr("横向分布"))
        act_dv = align_menu.addAction(safe_tr("纵向分布"))

        act_al.triggered.connect(lambda: self._scene.align_shapes("L"))
        act_ac.triggered.connect(lambda: self._scene.align_shapes("C"))
        act_ar.triggered.connect(lambda: self._scene.align_shapes("R"))
        act_at.triggered.connect(lambda: self._scene.align_shapes("T"))
        act_am.triggered.connect(lambda: self._scene.align_shapes("M"))
        act_ab.triggered.connect(lambda: self._scene.align_shapes("B"))
        act_dh.triggered.connect(lambda: self._scene.distribute_shapes("h"))
        act_dv.triggered.connect(lambda: self._scene.distribute_shapes("v"))

        menu.addSeparator()
        act_grp = menu.addAction(safe_tr("组合"))
        act_ungrp = menu.addAction(safe_tr("取消组合"))
        act_grp.triggered.connect(self._scene.group_selected)
        act_ungrp.triggered.connect(self._scene.ungroup_selected)

        menu.addSeparator()
        act_del = menu.addAction(safe_tr("删除"))
        act_del.triggered.connect(self._scene.delete_selected)

        menu.exec(event.globalPos())

    # ------------------------------------------------------------------
    # Keyboard & Wheel events
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._scene and getattr(self._scene, "current_tool", None):
                self._scene.set_drawing_tool(None)
                event.accept()
                return
        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._scene.delete_selected()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_G and ctrl_held:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._scene.ungroup_selected()
            else:
                self._scene.group_selected()
            event.accept()
            return
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 8.0 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1.0
            dx, dy = 0.0, 0.0
            if event.key() == Qt.Key.Key_Left:
                dx = -step
            elif event.key() == Qt.Key.Key_Right:
                dx = step
            elif event.key() == Qt.Key.Key_Up:
                dy = -step
            elif event.key() == Qt.Key.Key_Down:
                dy = step

            for it in self._scene.selected_shape_items():
                it.setPos(it.pos().x() + dx, it.pos().y() + dy)
                it.shape.x = round(it.pos().x(), 2)
                it.shape.y = round(it.pos().y(), 2)
            self._scene.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
