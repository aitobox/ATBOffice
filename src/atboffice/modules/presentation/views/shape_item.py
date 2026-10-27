"""ShapeGraphicsItem and TransformHandleItem for interactive Lectern slide editing."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
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


def safe_tr(text: str) -> str:
    """Translate UI text with fallback to Chinese native text for ATBOffice."""
    app = QApplication.instance()
    if app:
        translated = app.translate("ShapeGraphicsItem", text)
        if translated and translated != text:
            return translated
    return text


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

        # In-place text editor state
        self.is_editing_text: bool = False
        self._text_editor: Any = None

        # Multimedia preview state
        self._is_preview_playing: bool = False
        self.retranslate_ui()

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

        # 0. Chart rendering if shape is a chart
        if self.shape.is_chart:
            from atboffice.modules.presentation.chart.model import ChartData
            from atboffice.modules.presentation.chart.painter import ChartPainter

            c_data = (
                self.shape.chart
                if isinstance(self.shape.chart, ChartData)
                else ChartData.from_dict(self.shape.chart)
            )
            ChartPainter.paint_chart(painter, c_data, QRectF(0.0, 0.0, w, h))
            return

        # 0.1 Multimedia / Picture rendering
        if self.shape.media_item or self.shape.type == "image":
            self._paint_media_or_image(painter, w, h)
            if self.isSelected():
                sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(0.0, 0.0, w, h))
            return

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

        # 3. Draw inner text if present and not currently being edited
        if not self.is_editing_text and self.shape.text and self.shape.text.plain_text.strip():
            self._paint_text(painter, w, h)

        # 4. Selection bounding ring
        if self.isSelected():
            sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(0.0, 0.0, w, h))

    def _resolve_color(self, color_name: str | None) -> QColor:
        """Resolve color names or hex strings to QColor."""
        if not color_name:
            return QColor("#000000")
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
        if not text_body or text_body.is_empty():
            return

        insets = text_body.insets
        ins_l, ins_t, ins_r, ins_b = insets
        avail_w = max(10.0, w - ins_l - ins_r)
        avail_h = max(10.0, h - ins_t - ins_b)
        text_rect = QRectF(ins_l, ins_t, avail_w, avail_h)

        from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem
        ShapeTextEditorItem.render_static_text(
            painter, text_body, text_rect, self._resolve_color
        )

    def retranslate_ui(self) -> None:
        """Update tooltips and labels on locale switch."""
        if self.shape.media_item:
            media_lbl = safe_tr("视频") if self.shape.media_item.is_video else safe_tr("音频")
            preview_hint = safe_tr("单击中央徽标预览播放")
            tip = f"{media_lbl}{safe_tr('多媒体')}: {self.shape.name} ({preview_hint})"
            self.setToolTip(tip)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle media preview toggle or propagate standard selection/move."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.shape.media_item
            and not self.is_editing_text
        ):
            pos = event.pos()
            w = max(1.0, self.shape.w)
            h = max(1.0, self.shape.h)
            badge_d = min(50.0, min(w, h) * 0.38)
            cx = w / 2.0
            cy = h / 2.0 - (8.0 if h >= 70.0 else 0.0)
            badge_r = QRectF(cx - badge_d / 2.0, cy - badge_d / 2.0, badge_d, badge_d)
            bar_h = 24.0
            bar_r = QRectF(0.0, h - bar_h, w, bar_h) if h >= 60.0 else QRectF()
            if badge_r.contains(pos) or (bar_r.isValid() and bar_r.contains(pos)):
                self._is_preview_playing = not self._is_preview_playing
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def _paint_media_or_image(self, painter: QPainter, w: float, h: float) -> None:
        """Paint image poster frame or multimedia playback preview overlay."""
        m_item = self.shape.media_item

        # 1. Background / Poster frame
        drawn_image = False
        poster_bytes = None
        if m_item and m_item.poster_bytes:
            poster_bytes = m_item.poster_bytes

        if poster_bytes:
            qimg = QImage.fromData(poster_bytes)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                painter.drawPixmap(QRectF(0.0, 0.0, w, h).toRect(), pix)
                drawn_image = True

        if not drawn_image:
            # Fallback procedural background
            if m_item and m_item.is_audio:
                bg_rect = QRectF(0.0, 0.0, w, h)
                painter.setPen(QPen(QColor(180, 195, 210), 1.0))
                painter.setBrush(QBrush(QColor(240, 244, 248)))
                painter.drawRoundedRect(bg_rect, 4.0, 4.0)
                self._draw_speaker_icon(painter, w, h)
            elif m_item and m_item.is_video:
                bg_rect = QRectF(0.0, 0.0, w, h)
                painter.setPen(QPen(QColor(50, 50, 55), 1.0))
                painter.setBrush(QBrush(QColor(25, 27, 32)))
                painter.drawRoundedRect(bg_rect, 4.0, 4.0)
            else:
                bg_rect = QRectF(0.0, 0.0, w, h)
                painter.setPen(QPen(QColor(200, 200, 200), 1.0, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(245, 245, 245)))
                painter.drawRect(bg_rect)

        # 2. Multimedia Playback Controls Overlay
        if m_item:
            self._paint_playback_controls(painter, w, h)

    def _draw_speaker_icon(self, painter: QPainter, w: float, h: float) -> None:
        """Draw classic audio speaker symbol with sound waves."""
        cx = w / 2.0
        cy = h / 2.0 - (10.0 if h >= 60.0 else 0.0)
        s = min(28.0, min(w, h) * 0.35)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(70, 90, 120), 1.5))
        painter.setBrush(QBrush(QColor(100, 130, 170)))

        # Speaker body: rectangle + flared polygon
        path = QPainterPath()
        path.moveTo(cx - s * 0.5, cy - s * 0.3)
        path.lineTo(cx - s * 0.2, cy - s * 0.3)
        path.lineTo(cx + s * 0.2, cy - s * 0.7)
        path.lineTo(cx + s * 0.2, cy + s * 0.7)
        path.lineTo(cx - s * 0.2, cy + s * 0.3)
        path.lineTo(cx - s * 0.5, cy + s * 0.3)
        path.closeSubpath()
        painter.drawPath(path)

        # Sound arcs
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(cx + s * 0.1, cy - s * 0.4, s * 0.5, s * 0.8), -60 * 16, 120 * 16)
        painter.drawArc(QRectF(cx + s * 0.25, cy - s * 0.65, s * 0.7, s * 1.3), -60 * 16, 120 * 16)

        # Filename label
        if h >= 80.0 and self.shape.name:
            font = QFont("Helvetica", 8)
            painter.setFont(font)
            painter.setPen(QPen(QColor(60, 75, 95)))
            lbl_rect = QRectF(4.0, cy + s * 0.8, w - 8.0, 18.0)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, self.shape.name)

        painter.restore()

    def _paint_playback_controls(self, painter: QPainter, w: float, h: float) -> None:
        """Draw interactive center play badge and bottom playback control bar."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Central Play Badge
        badge_d = min(50.0, min(w, h) * 0.38)
        if badge_d >= 16.0:
            cx = w / 2.0
            cy = h / 2.0 - (8.0 if h >= 70.0 else 0.0)
            badge_r = QRectF(cx - badge_d / 2.0, cy - badge_d / 2.0, badge_d, badge_d)

            # Circular semi-transparent background
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1.5))
            badge_bg = QColor(20, 24, 30, 200 if not self._is_preview_playing else 230)
            painter.setBrush(QBrush(badge_bg))
            painter.drawEllipse(badge_r)

            # Draw Play triangle or Pause bars
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
            if not self._is_preview_playing:
                tri_path = QPainterPath()
                tw = badge_d * 0.35
                th = badge_d * 0.4
                tri_path.moveTo(cx - tw * 0.4, cy - th * 0.5)
                tri_path.lineTo(cx + tw * 0.6, cy)
                tri_path.lineTo(cx - tw * 0.4, cy + th * 0.5)
                tri_path.closeSubpath()
                painter.drawPath(tri_path)
            else:
                pw = badge_d * 0.12
                ph = badge_d * 0.36
                painter.drawRect(QRectF(cx - pw * 1.5, cy - ph / 2.0, pw, ph))
                painter.drawRect(QRectF(cx + pw * 0.5, cy - ph / 2.0, pw, ph))

        # 2. Bottom Playback Control Bar (only when height allows)
        bar_h = 24.0
        if h >= 60.0 and w >= 100.0:
            bar_rect = QRectF(0.0, h - bar_h, w, bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(15, 18, 22, 215)))
            painter.drawRect(bar_rect)

            # Play/Pause micro glyph on left
            painter.setBrush(QBrush(QColor(220, 225, 230)))
            btn_x = 10.0
            btn_y = h - bar_h / 2.0
            if not self._is_preview_playing:
                p_tri = QPainterPath()
                p_tri.moveTo(btn_x, btn_y - 4.5)
                p_tri.lineTo(btn_x + 7.0, btn_y)
                p_tri.lineTo(btn_x, btn_y + 4.5)
                p_tri.closeSubpath()
                painter.drawPath(p_tri)
            else:
                painter.drawRect(QRectF(btn_x, btn_y - 4.0, 2.5, 8.0))
                painter.drawRect(QRectF(btn_x + 4.0, btn_y - 4.0, 2.5, 8.0))

            # Timeline track
            track_left = btn_x + 16.0
            track_right = w - 60.0
            track_y = btn_y
            if track_right > track_left:
                painter.setPen(
                    QPen(
                        QColor(80, 85, 95),
                        2.5,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                    )
                )
                painter.drawLine(QPointF(track_left, track_y), QPointF(track_right, track_y))
                # Active progress
                prog_w = (track_right - track_left) * (0.35 if self._is_preview_playing else 0.0)
                if prog_w > 0:
                    painter.setPen(
                        QPen(
                            QColor(0, 120, 215),
                            2.5,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap,
                        )
                    )
                    painter.drawLine(
                        QPointF(track_left, track_y),
                        QPointF(track_left + prog_w, track_y),
                    )
                    painter.setBrush(QBrush(QColor(255, 255, 255)))
                    painter.setPen(QPen(QColor(0, 120, 215), 1.0))
                    painter.drawEllipse(QPointF(track_left + prog_w, track_y), 3.5, 3.5)

            # Time code label
            painter.setFont(QFont("Monospace", 7))
            painter.setPen(QPen(QColor(180, 185, 195)))
            time_text = "00:15" if self._is_preview_playing else "00:00"
            painter.drawText(
                QRectF(w - 55.0, h - bar_h, 50.0, bar_h),
                Qt.AlignmentFlag.AlignCenter,
                time_text,
            )

        painter.restore()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Activate in-place rich text editing or datasheet dialog on left double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.shape.is_chart:
                event.accept()
                from PySide6.QtWidgets import QDialog

                from atboffice.modules.presentation.chart.model import ChartData
                from atboffice.modules.presentation.dialogs.datasheet_dialog import (
                    DatasheetDialog,
                )

                c_data = (
                    self.shape.chart
                    if isinstance(self.shape.chart, ChartData)
                    else ChartData.from_dict(self.shape.chart)
                )
                parent_view = (
                    self.scene().views()[0]
                    if self.scene() and self.scene().views()
                    else None
                )
                dlg = DatasheetDialog(chart=c_data, parent=parent_view)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.shape.chart = dlg.get_chart_data().to_dict()
                    self.update()
                    self.geometryChanged.emit()
                return

            event.accept()
            self.start_text_editing()
        else:
            super().mouseDoubleClickEvent(event)

    def start_text_editing(self) -> Any:
        """Activate in-place rich text editor."""
        from atboffice.modules.presentation.models.text import TextBody
        from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem

        if self.is_editing_text and self._text_editor:
            return self._text_editor

        if not self.shape.text:
            self.shape.text = TextBody.create_empty()

        self.is_editing_text = True
        self._update_handles_visibility(False)

        self._text_editor = ShapeTextEditorItem(self)
        self._text_editor.setFocus()
        self.update()
        return self._text_editor

    def finish_text_editing(self) -> None:
        """Finish in-place rich text editing and cleanup editor item."""
        if not self.is_editing_text:
            return

        self.is_editing_text = False
        if self._text_editor:
            sc = self._text_editor.scene()
            if sc:
                sc.removeItem(self._text_editor)
            self._text_editor.setParentItem(None)
            self._text_editor = None

        self._update_handles_visibility(self.isSelected())
        self.update()
        self.geometryChanged.emit()

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
