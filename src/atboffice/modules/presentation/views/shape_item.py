"""ShapeGraphicsItem and TransformHandleItem for interactive Lectern slide editing."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    get_adjustment_handles,
)

if TYPE_CHECKING:
    pass


HANDLE_SIZE = 8.0
ROT_HANDLE_OFFSET = 24.0


class HandleType:
    NW = "nw"
    N = "n"
    NE = "ne"
    E = "e"
    SE = "se"
    S = "s"
    SW = "sw"
    W = "w"
    ROTATE = "rot"
    ADJUST = "adj"


class TransformHandleItem(QGraphicsItem):
    """Interactive sizing, rotation, or adjustment handle attached to a ShapeGraphicsItem."""

    def __init__(
        self,
        handle_type: str,
        parent: ShapeGraphicsItem,
        adjust_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.handle_type = handle_type
        self.adjust_index = adjust_index
        self._parent_shape = parent
        self.setAcceptHoverEvents(True)
        self.setZValue(100.0)

        # Cursors
        self._update_cursor()

    def _update_cursor(self) -> None:
        ht = self.handle_type
        if ht == HandleType.ROTATE:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif ht == HandleType.ADJUST:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif ht in (HandleType.NW, HandleType.SE):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif ht in (HandleType.NE, HandleType.SW):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif ht in (HandleType.N, HandleType.S):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif ht in (HandleType.E, HandleType.W):
            self.setCursor(Qt.CursorShape.SizeHorCursor)

    def boundingRect(self) -> QRectF:
        s = HANDLE_SIZE
        if self.handle_type == HandleType.ROTATE:
            # Include connecting line to top of shape
            return QRectF(-s / 2.0, -s / 2.0, s, s + ROT_HANDLE_OFFSET)
        return QRectF(-s / 2.0, -s / 2.0, s, s)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        s = HANDLE_SIZE
        r = QRectF(-s / 2.0, -s / 2.0, s, s)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.handle_type == HandleType.ROTATE:
            # Draw connecting stem line down to top-center
            stem_pen = QPen(QColor(80, 80, 80), 1.0, Qt.PenStyle.SolidLine)
            painter.setPen(stem_pen)
            painter.drawLine(QPointF(0.0, s / 2.0), QPointF(0.0, ROT_HANDLE_OFFSET))

            # Draw green rotation circle
            painter.setPen(QPen(QColor(0, 100, 0), 1.0))
            painter.setBrush(QBrush(QColor(50, 205, 50)))
            painter.drawEllipse(r)

        elif self.handle_type == HandleType.ADJUST:
            # Draw yellow diamond adjustment handle
            painter.setPen(QPen(QColor(120, 100, 0), 1.0))
            painter.setBrush(QBrush(QColor(255, 215, 0)))
            path = QPainterPath()
            path.moveTo(0.0, -s / 2.0)
            path.lineTo(s / 2.0, 0.0)
            path.lineTo(0.0, s / 2.0)
            path.lineTo(-s / 2.0, 0.0)
            path.closeSubpath()
            painter.drawPath(path)

        else:
            # Standard sizing square handle
            painter.setPen(QPen(QColor(40, 40, 40), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawRect(r)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self._parent_shape.begin_handle_drag(self, event.scenePos())
        else:
            super("mousePressEvent", event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            event.accept()
            self._parent_shape.update_handle_drag(
                self, event.scenePos(), event.modifiers()
            )
        else:
            super("mouseMoveEvent", event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self._parent_shape.end_handle_drag(self)
        else:
            super("mouseReleaseEvent", event)


class ShapeGraphicsItem(QGraphicsObject):
    """Interactive canvas item representing a presentation Shape."""

    geometryChanged = Signal()

    def __init__(self, shape: Shape, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.shape = shape

        # Initial positioning from model
        self.setPos(shape.x, shape.y)
        self.setRotation(shape.rot)
        self.setTransformOriginPoint(shape.w / 2.0, shape.h / 2.0)

        # Graphics item flags
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        # Handles
        self._handles: list[TransformHandleItem] = []
        self._drag_start_scene_pos = QPointF()
        self._drag_initial_rect = QRectF(shape.x, shape.y, shape.w, shape.h)
        self._drag_initial_rot = shape.rot
        self._drag_initial_adj = dict(shape.adj or {})
        self._create_handles()
        self._update_handles_visibility()

    def _create_handles(self) -> None:
        for h in self._handles:
            h.setParentItem(None)
        self._handles.clear()

        # 8 sizing handles
        for ht in [
            HandleType.NW,
            HandleType.N,
            HandleType.NE,
            HandleType.E,
            HandleType.SE,
            HandleType.S,
            HandleType.SW,
            HandleType.W,
        ]:
            self._handles.append(TransformHandleItem(ht, self))

        # 1 rotation handle
        self._handles.append(TransformHandleItem(HandleType.ROTATE, self))

        # Adjustment handles if available for geometry
        adj_defs = get_adjustment_handles(self.shape.geom)
        for i in range(len(adj_defs)):
            self._handles.append(
                TransformHandleItem(HandleType.ADJUST, self, adjust_index=i)
            )

        self._position_handles()

    def _position_handles(self) -> None:
        w = max(1.0, self.shape.w)
        h = max(1.0, self.shape.h)
        adj = self.shape.adj or {}

        for hd in self._handles:
            ht = hd.handle_type
            if ht == HandleType.NW:
                hd.setPos(0.0, 0.0)
            elif ht == HandleType.N:
                hd.setPos(w / 2.0, 0.0)
            elif ht == HandleType.NE:
                hd.setPos(w, 0.0)
            elif ht == HandleType.E:
                hd.setPos(w, h / 2.0)
            elif ht == HandleType.SE:
                hd.setPos(w, h)
            elif ht == HandleType.S:
                hd.setPos(w / 2.0, h)
            elif ht == HandleType.SW:
                hd.setPos(0.0, h)
            elif ht == HandleType.W:
                hd.setPos(0.0, h / 2.0)
            elif ht == HandleType.ROTATE:
                hd.setPos(w / 2.0, -ROT_HANDLE_OFFSET)
            elif ht == HandleType.ADJUST:
                defs = get_adjustment_handles(self.shape.geom)
                if hd.adjust_index < len(defs):
                    ax, ay = defs[hd.adjust_index].get_pos(w, h, adj)
                    hd.setPos(ax, ay)

    def _update_handles_visibility(self, selected: bool | None = None) -> None:
        visible = self.isSelected() if selected is None else bool(selected)
        for hd in self._handles:
            hd.setVisible(visible)

    def boundingRect(self) -> QRectF:
        pad = HANDLE_SIZE + 2.0
        extra_top = ROT_HANDLE_OFFSET + pad if self.isSelected() else pad
        return QRectF(
            -pad,
            -extra_top,
            self.shape.w + pad * 2.0,
            self.shape.h + extra_top + pad,
        )

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(0.0, 0.0, max(1.0, self.shape.w), max(1.0, self.shape.h))
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1.0, self.shape.w)
        h = max(1.0, self.shape.h)

        # 1. Shadow effect
        if self.shape.shadow:
            sh_path = create_shape_path(self.shape.geom, w, h, self.shape.adj)
            painter.save()
            sh_dist = self.shape.shadow.dist
            sh_ang = math.radians(self.shape.shadow.angle)
            dx = math.cos(sh_ang) * sh_dist
            dy = math.sin(sh_ang) * sh_dist
            painter.translate(dx, dy)
            sh_col = QColor(self.shape.shadow.color)
            sh_col.setAlphaF(self.shape.shadow.alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(sh_col))
            painter.drawPath(sh_path)
            painter.restore()

        # 2. Main shape path
        path = create_shape_path(self.shape.geom, w, h, self.shape.adj)

        # Fill
        fill_brush = QBrush(Qt.BrushStyle.NoBrush)
        if self.shape.fill.type == "solid":
            color_str = self.shape.fill.color
            c = self._resolve_color(color_str)
            c.setAlphaF(self.shape.fill.alpha)
            fill_brush = QBrush(c)
        elif self.shape.fill.type == "none":
            fill_brush = QBrush(Qt.BrushStyle.NoBrush)
        else:
            fill_brush = QBrush(self._resolve_color("accent1"))

        # Outline Pen
        if self.shape.line.type == "none":
            line_pen = QPen(Qt.PenStyle.NoPen)
        else:
            lc = self._resolve_color(self.shape.line.color)
            dash = Qt.PenStyle.SolidLine
            if self.shape.line.dash == "dash":
                dash = Qt.PenStyle.DashLine
            elif self.shape.line.dash == "dot":
                dash = Qt.PenStyle.DotLine
            line_pen = QPen(lc, max(1.0, self.shape.line.width), dash)

        painter.setPen(line_pen)
        painter.setBrush(fill_brush)
        painter.drawPath(path)

        # 3. Draw inner text if present
        if self.shape.text and self.shape.text.plain_text.strip():
            self._paint_text(painter, w, h)

        # 4. Selection bounding ring
        if self.isSelected():
            sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(0.0, 0.0, w, h))

    def _resolve_color(self, color_name: str) -> QColor:
        """Resolve color names or hex strings to QColor."""
        if color_name.startswith("#") or color_name.startswith("rgb"):
            return QColor(color_name)
        # Standard palette mappings
        preset_map = {
            "accent1": "#2B579A",
            "accent2": "#D24726",
            "accent3": "#008A00",
            "accent4": "#825A2C",
            "accent5": "#002050",
            "accent6": "#E2B200",
            "tx1": "#000000",
            "tx2": "#595959",
            "bg1": "#FFFFFF",
            "bg2": "#EBEBEB",
            "white": "#FFFFFF",
            "black": "#000000",
        }
        hex_val = preset_map.get(color_name.lower(), "#2B579A")
        return QColor(hex_val)

    def _paint_text(self, painter: QPainter, w: float, h: float) -> None:
        """Draw multiline text within shape boundaries."""
        text_body = self.shape.text
        if not text_body:
            return

        text = text_body.plain_text
        insets = text_body.insets  # (top, right, bottom, left)
        text_rect = QRectF(
            insets[3],
            insets[0],
            max(10.0, w - insets[1] - insets[3]),
            max(10.0, h - insets[0] - insets[2]),
        )

        font = QFont("Tahoma", 14)
        if text_body.paragraphs and text_body.paragraphs[0].runs:
            first_run = text_body.paragraphs[0].runs[0]
            if first_run.font:
                font.setFamily(first_run.font)
            if first_run.size:
                font.setPointSizeF(first_run.size)
            if first_run.bold:
                font.setBold(True)
            if first_run.italic:
                font.setItalic(True)

        painter.setFont(font)
        painter.setPen(QPen(self._resolve_color("tx1")))

        align_flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        painter.drawText(text_rect, align_flags, text)

    def itemChange(
        self, change: QGraphicsItem.GraphicsItemChange, value: Any
    ) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.prepareGeometryChange()
            self._update_handles_visibility(bool(value))
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_handles_visibility(self.isSelected())
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos: QPointF = value
            # Update shape model coordinates
            self.shape.x = round(new_pos.x(), 2)
            self.shape.y = round(new_pos.y(), 2)
            self.geometryChanged.emit()
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Handle Drag Operations
    # ------------------------------------------------------------------
    def begin_handle_drag(
        self, handle: TransformHandleItem, scene_pos: QPointF
    ) -> None:
        self._drag_start_scene_pos = scene_pos
        self._drag_initial_rect = QRectF(
            self.shape.x, self.shape.y, self.shape.w, self.shape.h
        )
        self._drag_initial_rot = self.shape.rot
        self._drag_initial_adj = dict(self.shape.adj or {})

    def update_handle_drag(
        self,
        handle: TransformHandleItem,
        scene_pos: QPointF,
        modifiers: Qt.KeyboardModifiers,
    ) -> None:
        ht = handle.handle_type
        if ht == HandleType.ROTATE:
            self._do_rotate(scene_pos, modifiers)
        elif ht == HandleType.ADJUST:
            self._do_adjust(handle.adjust_index, scene_pos)
        else:
            self._do_resize(ht, scene_pos, modifiers)

    def end_handle_drag(self, handle: TransformHandleItem) -> None:
        self._position_handles()
        self.update()
        self.geometryChanged.emit()

    def _do_rotate(
        self, scene_pos: QPointF, modifiers: Qt.KeyboardModifiers
    ) -> None:
        # Calculate center point in scene coords
        center_local = QPointF(self.shape.w / 2.0, self.shape.h / 2.0)
        center_scene = self.mapToScene(center_local)

        dx = scene_pos.x() - center_scene.x()
        dy = scene_pos.y() - center_scene.y()
        # Angle in degrees relative to vertical (up = 0)
        angle = math.degrees(math.atan2(dy, dx)) + 90.0
        angle = (angle % 360.0 + 360.0) % 360.0

        # Shift snap to 15 degrees
        if bool(modifiers & Qt.KeyboardModifier.ShiftModifier):
            angle = round(angle / 15.0) * 15.0
            angle = (angle % 360.0 + 360.0) % 360.0

        self.shape.rot = round(angle, 1)
        self.setRotation(self.shape.rot)
        self.geometryChanged.emit()

    def _do_adjust(self, adjust_index: int, scene_pos: QPointF) -> None:
        local_pos = self.mapFromItem(self, self.mapFromScene(scene_pos))
        defs = get_adjustment_handles(self.shape.geom)
        if adjust_index < len(defs):
            new_adj = defs[adjust_index].calculate_adj(
                local_pos.x(),
                local_pos.y(),
                self.shape.w,
                self.shape.h,
                self._drag_initial_adj,
            )
            self.shape.adj = new_adj
            self._position_handles()
            self.prepareGeometryChange()
            self.update()
            self.geometryChanged.emit()

    def _do_resize(
        self,
        handle_type: str,
        scene_pos: QPointF,
        modifiers: Qt.KeyboardModifiers,
    ) -> None:
        # Convert scene pos delta into local coordinate space
        p0_local = self.mapFromScene(self._drag_start_scene_pos)
        p_local = self.mapFromScene(scene_pos)
        dx = p_local.x() - p0_local.x()
        dy = p_local.y() - p0_local.y()

        init_r = self._drag_initial_rect
        left, top, right, bottom = 0.0, 0.0, init_r.width(), init_r.height()

        if "w" in handle_type:
            left += dx
        if "e" in handle_type:
            right += dx
        if "n" in handle_type:
            top += dy
        if "s" in handle_type:
            bottom += dy

        # Alt modifier: center resize
        is_center = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        if is_center:
            if "w" in handle_type:
                right -= dx
            elif "e" in handle_type:
                left -= dx
            if "n" in handle_type:
                bottom -= dy
            elif "s" in handle_type:
                top -= dy

        new_w = right - left
        new_h = bottom - top

        # Shift modifier: maintain aspect ratio
        is_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if is_shift and init_r.height() > 0:
            scale_w = abs(new_w) / init_r.width()
            scale_h = abs(new_h) / init_r.height()
            scale = max(scale_w, scale_h)
            nw = init_r.width() * scale
            nh = init_r.height() * scale

            if "w" in handle_type:
                left = right - nw
            else:
                right = left + nw

            if "n" in handle_type:
                top = bottom - nh
            else:
                bottom = top + nh

            if is_center:
                left = -nw / 2.0
                right = nw / 2.0
                top = -nh / 2.0
                bottom = nh / 2.0

            new_w = right - left
            new_h = bottom - top

        # Prevent inversion below min size
        new_w = max(10.0, new_w)
        new_h = max(10.0, new_h)

        # Map top-left back to scene coordinates
        new_top_left_scene = self.mapToScene(QPointF(left, top))

        self.prepareGeometryChange()
        self.shape.w = round(new_w, 2)
        self.shape.h = round(new_h, 2)
        self.setTransformOriginPoint(self.shape.w / 2.0, self.shape.h / 2.0)
        self.setPos(new_top_left_scene)
        self.shape.x = round(new_top_left_scene.x(), 2)
        self.shape.y = round(new_top_left_scene.y(), 2)

        self._position_handles()
        self.update()
        self.geometryChanged.emit()

    def update_from_model(self) -> None:
        """Refresh graphics item state from underlying Shape model."""
        self.prepareGeometryChange()
        self.setPos(self.shape.x, self.shape.y)
        self.setRotation(self.shape.rot)
        self.setTransformOriginPoint(self.shape.w / 2.0, self.shape.h / 2.0)
        self._position_handles()
        self.update()
