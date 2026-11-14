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
from atboffice.modules.presentation.models.text import TextBody
from atboffice.modules.presentation.views.geometry_helper import (
    calculate_connector_route,
    connector_local_endpoints,
    create_shape_path,
    flip_transform,
    get_adjustment_handles,
    get_shape_connection_sites,
)

if TYPE_CHECKING:
    pass


HANDLE_SIZE = 8.0
ROT_HANDLE_OFFSET = 24.0

DASH_PATTERNS: dict[str, list[float] | None] = {
    "solid": None,
    "dot": [1.0, 2.0],
    "dash": [4.0, 3.0],
    "lgDash": [8.0, 3.0],
    "dashDot": [4.0, 3.0, 1.0, 3.0],
    "lgDashDot": [8.0, 3.0, 1.0, 3.0],
    "lgDashDotDot": [8.0, 3.0, 1.0, 3.0, 1.0, 3.0],
    "sysDash": [3.0, 1.0],
    "sysDot": [1.0, 1.0],
    "sysDashDot": [3.0, 1.0, 1.0, 1.0],
    "sysDashDotDot": [3.0, 1.0, 1.0, 1.0, 1.0, 1.0],
}


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
    START = "start"
    END = "end"


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
        elif ht in (HandleType.ADJUST, HandleType.START, HandleType.END):
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

        elif self.handle_type in (HandleType.START, HandleType.END):
            # Draw circular connector endpoint handle
            painter.setPen(QPen(QColor(0, 102, 204), 1.5))
            painter.setBrush(QBrush(QColor(51, 153, 255)))
            painter.drawEllipse(r)

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
        self.model = shape

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

    @property
    def shape_data(self) -> Shape:
        """Convenience alias for the underlying Shape data model."""
        return self.model

    def _create_handles(self) -> None:
        for h in self._handles:
            h.setParentItem(None)
        self._handles.clear()

        # Connector endpoints
        if self.model.is_connector:
            self._handles.append(TransformHandleItem(HandleType.START, self))
            self._handles.append(TransformHandleItem(HandleType.END, self))
            self._position_handles()
            return

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
        adj_defs = get_adjustment_handles(self.model.geom)
        for i in range(len(adj_defs)):
            self._handles.append(
                TransformHandleItem(HandleType.ADJUST, self, adjust_index=i)
            )

        self._position_handles()

    def _position_handles(self) -> None:
        w = max(1.0, self.model.w)
        h = max(1.0, self.model.h)
        adj = self.model.adj or {}

        if self.model.is_connector:
            p1 = adj.get("p1")
            p2 = adj.get("p2")
            if p1 and p2:
                sx = float(p1[0]) - self.model.x
                sy = float(p1[1]) - self.model.y
                ex = float(p2[0]) - self.model.x
                ey = float(p2[1]) - self.model.y
            else:
                (sx, sy), (ex, ey) = connector_local_endpoints(
                    w, h, self.model.flip_h, self.model.flip_v
                )

            for hd in self._handles:
                if hd.handle_type == HandleType.START:
                    hd.setPos(sx, sy)
                elif hd.handle_type == HandleType.END:
                    hd.setPos(ex, ey)
            return

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
                defs = get_adjustment_handles(self.model.geom)
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
            self.model.w + pad * 2.0,
            self.model.h + extra_top + pad,
        )

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(0.0, 0.0, max(1.0, self.model.w), max(1.0, self.model.h))
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1.0, self.model.w)
        h = max(1.0, self.model.h)

        # 0. Chart rendering if shape is a chart
        if self.model.is_chart:
            from atboffice.modules.presentation.chart.model import ChartData
            from atboffice.modules.presentation.chart.painter import ChartPainter

            c_data = (
                self.model.chart
                if isinstance(self.model.chart, ChartData)
                else ChartData.from_dict(self.model.chart)
            )
            ChartPainter.paint_chart(painter, c_data, QRectF(0.0, 0.0, w, h))
            return

        # 0.1 Multimedia / Picture rendering
        if self.model.media_item or self.model.type == "image":
            self._paint_media_or_image(painter, w, h)
            if self.isSelected():
                sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(0.0, 0.0, w, h))
            return

        # 0.2 Table rendering if shape is a table
        if self.model.type == "table" or bool(self.model.tbl):
            self._paint_table(painter, w, h)
            if self.isSelected():
                sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(0.0, 0.0, w, h))
            return

        # 0.3 SmartArt Diagram rendering
        if self.model.is_diagram or bool(self.model.sa):
            self._paint_diagram(painter, w, h)
            if self.isSelected():
                sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(0.0, 0.0, w, h))
            return

        # 0.4 Group rendering
        if self.model.type == "group" and self.model.kids:
            self._paint_group(painter, w, h)
            if self.isSelected():
                sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(0.0, 0.0, w, h))
            return

        # Flips mirror the geometry (and its shadow) inside the box; text stays upright.
        flip_xf = flip_transform(w, h, self.model.flip_h, self.model.flip_v)

        # 1. Shadow effect
        if self.model.shadow:
            sh_path = flip_xf.map(
                create_shape_path(self.model.geom, w, h, self.model.adj, self.model.custom_path)
            )
            painter.save()
            sh_dist = self.model.shadow.dist
            sh_ang = math.radians(self.model.shadow.angle)
            dx = math.cos(sh_ang) * sh_dist
            dy = math.sin(sh_ang) * sh_dist
            painter.translate(dx, dy)
            sh_col = QColor(self.model.shadow.color)
            sh_col.setAlphaF(self.model.shadow.alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(sh_col))
            painter.drawPath(sh_path)
            painter.restore()

        # 2. Main shape path
        path = flip_xf.map(
            create_shape_path(self.model.geom, w, h, self.model.adj, self.model.custom_path)
        )

        # Fill
        fill_brush = QBrush(Qt.BrushStyle.NoBrush)
        if self.model.fill.type == "solid":
            color_str = self.model.fill.color
            c = self._resolve_color(color_str)
            c.setAlphaF(self.model.fill.alpha)
            fill_brush = QBrush(c)
        elif self.model.fill.type == "none":
            fill_brush = QBrush(Qt.BrushStyle.NoBrush)
        else:
            fill_brush = QBrush(self._resolve_color("accent1"))

        # Outline Pen
        if self.model.line.type == "none":
            line_pen = QPen(Qt.PenStyle.NoPen)
        else:
            lc = self._resolve_color(self.model.line.color)
            line_w = max(1.0, self.model.line.width)
            line_pen = QPen(lc, line_w, Qt.PenStyle.SolidLine)
            custom_dash = getattr(self.model.line, "custom_dash", None)
            if custom_dash:
                pattern = [float(x) for x in custom_dash]
                if len(pattern) % 2 != 0:
                    pattern.append(pattern[-1])
                line_pen.setDashPattern(pattern)
            elif self.model.line.dash in DASH_PATTERNS:
                pat = DASH_PATTERNS[self.model.line.dash]
                if pat:
                    line_pen.setDashPattern(pat)
            elif self.model.line.dash == "dash":
                line_pen.setStyle(Qt.PenStyle.DashLine)
            elif self.model.line.dash == "dot":
                line_pen.setStyle(Qt.PenStyle.DotLine)

        painter.setPen(line_pen)
        painter.setBrush(fill_brush)
        painter.drawPath(path)

        # 3. Draw inner text if present and not currently being edited
        if not self.is_editing_text and self.model.text and self.model.text.plain_text.strip():
            self._paint_text(painter, w, h)

        # 4. Selection bounding ring
        if self.isSelected() and not self.model.is_connector:
            sel_pen = QPen(QColor(0, 120, 215, 180), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(0.0, 0.0, w, h))

        # 5. Connection sites indicator during drag/hover
        if getattr(self, "_show_connection_sites", False) and not self.model.is_connector:
            highlight_idx = getattr(self, "_highlight_site_idx", None)
            sites = get_shape_connection_sites(self.model.geom, w, h, self.model.adj)
            painter.save()
            for idx, (lx, ly) in enumerate(sites):
                is_hl = idx == highlight_idx
                r = 4.5 if is_hl else 3.0
                dot_rect = QRectF(lx - r, ly - r, r * 2.0, r * 2.0)
                if is_hl:
                    painter.setPen(QPen(QColor(0, 150, 0), 1.5))
                    painter.setBrush(QBrush(QColor(0, 230, 0)))
                else:
                    painter.setPen(QPen(QColor(0, 100, 200), 1.0))
                    painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawEllipse(dot_rect)
            painter.restore()

    def _resolve_color(self, color_name: str | None) -> QColor:
        """Resolve color names or hex strings to QColor."""
        if not color_name:
            return QColor("#000000")
        if color_name.startswith("#") or color_name.startswith("rgb"):
            return QColor(color_name)

        design = None
        clr_map_ovr = None
        scene = self.scene()
        if scene:
            pres = getattr(scene, "presentation", None)
            slide = getattr(scene, "slide", None)
            if slide:
                clr_map_ovr = getattr(slide, "clr_map_ovr", None)
            if pres and hasattr(pres, "designs") and pres.designs:
                if slide and getattr(slide, "design_id", "") in pres.designs:
                    design = pres.designs[slide.design_id]
                else:
                    design = next(iter(pres.designs.values()), None)

        from atboffice.modules.presentation.models.designs import resolve_color
        hex_val = resolve_color(color_name, design=design, fallback="", clr_map_ovr=clr_map_ovr)
        if hex_val:
            return QColor(hex_val)

        # Standard palette mappings
        preset_map = {
            "accent1": "#2B579A",
            "accent2": "#D24726",
            "accent3": "#008A00",
            "accent4": "#825A2C",
            "accent5": "#002050",
            "accent6": "#E2B200",
            "hlink": "#0000FF",
            "folhlink": "#800080",
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
        text_body = self.model.text
        if not text_body or text_body.is_empty():
            return

        insets = text_body.insets
        ins_l, ins_t, ins_r, ins_b = insets
        avail_w = max(10.0, w - ins_l - ins_r)
        avail_h = max(10.0, h - ins_t - ins_b)
        text_rect = QRectF(ins_l, ins_t, avail_w, avail_h)

        scene = self.scene()
        slide_idx = 0
        pres = None
        if scene:
            pres = getattr(scene, "presentation", None)
            slide = getattr(scene, "slide", None)
            if pres and slide and hasattr(pres, "slides") and slide in pres.slides:
                try:
                    slide_idx = pres.slides.index(slide)
                except ValueError:
                    slide_idx = 0

        from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem
        ShapeTextEditorItem.render_static_text(
            painter,
            text_body,
            text_rect,
            self._resolve_color,
            slide_index=slide_idx,
            presentation=pres,
        )

    def retranslate_ui(self) -> None:
        """Update tooltips and labels on locale switch."""
        if self.model.media_item:
            is_vid = (
                getattr(self.model.media_item, "is_video", False)
                if not isinstance(self.model.media_item, dict)
                else self.model.media_item.get("is_video", False)
            )
            media_lbl = safe_tr("视频") if is_vid else safe_tr("音频")
            preview_hint = safe_tr("单击中央徽标预览播放")
            tip = f"{media_lbl}{safe_tr('多媒体')}: {self.model.name} ({preview_hint})"
            self.setToolTip(tip)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle media preview toggle or propagate standard selection/move."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.model.media_item
            and not self.is_editing_text
        ):
            pos = event.pos()
            w = max(1.0, self.model.w)
            h = max(1.0, self.model.h)
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
        m_item = self.model.media_item

        # 1. Background / Poster frame
        drawn_image = False
        poster_bytes = None
        if m_item and m_item.poster_bytes:
            poster_bytes = m_item.poster_bytes
        elif self.model.media:
            sc = self.scene()
            if sc and hasattr(sc, "presentation") and sc.presentation:
                media_map = sc.presentation.props.get("_media_map", {})
                poster_bytes = media_map.get(self.model.media)

        if poster_bytes:
            qimg = QImage.fromData(poster_bytes)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                painter.save()
                painter.setTransform(
                    flip_transform(w, h, self.model.flip_h, self.model.flip_v), True
                )
                painter.setClipRect(QRectF(0.0, 0.0, w, h), Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(self._image_target_rect(w, h), pix, QRectF(pix.rect()))
                painter.restore()
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
        if m_item and (getattr(m_item, "is_video", False) or getattr(m_item, "is_audio", False)):
            self._paint_playback_controls(painter, w, h)

    def _image_target_rect(self, w: float, h: float) -> QRectF:
        """Where the whole picture lands so its srcRect crop fills the frame.

        The visible fraction (1 - l - r, 1 - t - b) is stretched to the frame and the
        rest falls outside it (or, for negative crops, leaves padding inside it).
        """
        crop = self.model.crop if isinstance(self.model.crop, dict) else None
        if not crop:
            return QRectF(0.0, 0.0, w, h)
        cl = float(crop.get("l", 0.0) or 0.0)
        ct = float(crop.get("t", 0.0) or 0.0)
        cr = float(crop.get("r", 0.0) or 0.0)
        cb = float(crop.get("b", 0.0) or 0.0)
        vis_w = 1.0 - cl - cr
        vis_h = 1.0 - ct - cb
        if vis_w <= 0.001 or vis_h <= 0.001:
            return QRectF(0.0, 0.0, w, h)
        full_w = w / vis_w
        full_h = h / vis_h
        return QRectF(-cl * full_w, -ct * full_h, full_w, full_h)

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
        if h >= 80.0 and self.model.name:
            font = QFont("Helvetica", 8)
            painter.setFont(font)
            painter.setPen(QPen(QColor(60, 75, 95)))
            lbl_rect = QRectF(4.0, cy + s * 0.8, w - 8.0, 18.0)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, self.model.name)

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

    def _paint_table(self, painter: QPainter, w: float, h: float) -> None:
        """Render table grid cells, borders, fills, and multiline text runs with font colors."""
        tbl_data = self.model.tbl or {}
        cols = tbl_data.get("cols", [])
        rows = tbl_data.get("rows", [])
        if not rows:
            return

        if not cols:
            num_c = max(len(r.get("cells", [])) for r in rows) if rows else 1
            cols = [w / max(1, num_c)] * max(1, num_c)

        tot_cols_w = sum(cols)
        sx = (w / tot_cols_w) if tot_cols_w > 0.001 else 1.0

        from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem

        cur_y = 0.0
        for r_idx, row in enumerate(rows):
            row_h = float(row.get("h", 30.0))
            cur_x = 0.0
            cells = row.get("cells", [])
            for c_idx, cell in enumerate(cells):
                col_w = (cols[c_idx] if c_idx < len(cols) else (w / max(1, len(cells)))) * sx
                cell_rect = QRectF(cur_x, cur_y, col_w, row_h)

                # Fill
                c_fill = cell.get("fill")
                if c_fill and isinstance(c_fill, dict) and c_fill.get("t") == "solid":
                    painter.fillRect(cell_rect, self._resolve_color(c_fill.get("c")))
                elif c_fill and hasattr(c_fill, "color") and c_fill.color:
                    painter.fillRect(cell_rect, self._resolve_color(c_fill.color))

                # Border
                grid_pen = QPen(QColor(180, 180, 180), 1.0)
                painter.setPen(grid_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(cell_rect)

                # Text
                cell_tx = cell.get("tx")
                if isinstance(cell_tx, dict):
                    try:
                        cell_tx = TextBody.from_dict(cell_tx)
                    except Exception:
                        cell_tx = None
                if cell_tx and hasattr(cell_tx, "is_empty") and not cell_tx.is_empty():
                    pad_rect = cell_rect.adjusted(6.0, 3.0, -6.0, -3.0)
                    ShapeTextEditorItem.render_static_text(
                        painter, cell_tx, pad_rect, self._resolve_color
                    )
                elif cell.get("text"):
                    painter.setPen(QColor("#000000"))
                    font = QFont("Arial", 11)
                    painter.setFont(font)
                    painter.drawText(
                        cell_rect.adjusted(6.0, 3.0, -6.0, -3.0),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        str(cell["text"]),
                    )

                cur_x += col_w
            cur_y += row_h

    def _paint_diagram(self, painter: QPainter, w: float, h: float) -> None:
        """Render SmartArt diagram layout and text."""
        rect = QRectF(0.0, 0.0, w, h)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background container
        fill_col = self._resolve_color(
            self.model.fill.color
            if self.model.fill and self.model.fill.type != "none"
            else "accent1"
        )
        fill_col.setAlphaF(0.15)
        painter.setBrush(QBrush(fill_col))
        painter.setPen(QPen(self._resolve_color("accent1"), 1.5))
        painter.drawRoundedRect(rect, 8.0, 8.0)

        items = []
        if self.model.sa and isinstance(self.model.sa, dict):
            items = self.model.sa.get("items", [])

        if items:
            n = len(items)
            gap = min(16.0, w / (n * 8))
            bw = (w - 20.0 - gap * (n - 1)) / max(1, n)
            bh = min(h * 0.7, bw * 0.6)
            by = (h - bh) / 2.0
            for i, it in enumerate(items):
                bx = 10.0 + i * (bw + gap)
                box_rect = QRectF(bx, by, bw, bh)
                box_c = self._resolve_color("accent1")
                painter.setBrush(QBrush(box_c))
                painter.setPen(QPen(self._resolve_color("dk1"), 1.0))
                painter.drawRoundedRect(box_rect, 4.0, 4.0)

                it_txt = str(it.get("text", ""))
                if it_txt:
                    painter.setPen(QColor("#FFFFFF"))
                    font = QFont("Arial", max(9, int(bh * 0.22)))
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(
                        box_rect.adjusted(4.0, 4.0, -4.0, -4.0),
                        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                        it_txt,
                    )
        elif self.model.text and not self.model.text.is_empty():
            self._paint_text(painter, w, h)

        painter.restore()

    def _paint_group(self, painter: QPainter, w: float, h: float) -> None:
        """Recursively render child shapes inside a group shape."""
        painter.save()
        for kid in self.model.kids:
            local_x = kid.x - self.model.x
            local_y = kid.y - self.model.y
            painter.save()
            painter.translate(local_x, local_y)

            kw = max(1.0, kid.w)
            kh = max(1.0, kid.h)
            path = flip_transform(kw, kh, kid.flip_h, kid.flip_v).map(
                create_shape_path(kid.geom, kw, kh, kid.adj, kid.custom_path)
            )

            if kid.fill and kid.fill.type == "solid":
                fc = self._resolve_color(kid.fill.color)
                fc.setAlphaF(kid.fill.alpha)
                painter.setBrush(QBrush(fc))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if kid.line and kid.line.type != "none":
                lc = self._resolve_color(kid.line.color)
                painter.setPen(QPen(lc, max(1.0, kid.line.width)))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawPath(path)

            if kid.text and not kid.text.is_empty():
                from atboffice.modules.presentation.views.text_editor import ShapeTextEditorItem

                insets = kid.text.insets
                ins_l, ins_t, ins_r, ins_b = insets
                text_rect = QRectF(
                    ins_l,
                    ins_t,
                    max(10.0, kw - ins_l - ins_r),
                    max(10.0, kh - ins_t - ins_b),
                )
                ShapeTextEditorItem.render_static_text(
                    painter, kid.text, text_rect, self._resolve_color
                )

            painter.restore()
        painter.restore()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Activate in-place rich text editing or datasheet dialog on left double-click."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.model.is_chart:
                event.accept()
                from PySide6.QtWidgets import QDialog

                from atboffice.modules.presentation.chart.model import ChartData
                from atboffice.modules.presentation.dialogs.datasheet_dialog import (
                    DatasheetDialog,
                )

                c_data = (
                    self.model.chart
                    if isinstance(self.model.chart, ChartData)
                    else ChartData.from_dict(self.model.chart)
                )
                parent_view = (
                    self.scene().views()[0]
                    if self.scene() and self.scene().views()
                    else None
                )
                dlg = DatasheetDialog(chart=c_data, parent=parent_view)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.model.chart = dlg.get_chart_data().to_dict()
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

        if not self.model.text:
            self.model.text = TextBody.create_empty()

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
            self.model.x = round(new_pos.x(), 2)
            self.model.y = round(new_pos.y(), 2)
            sc = self.scene()
            if sc and hasattr(sc, "update_connected_connectors"):
                sc.update_connected_connectors(self.model.id)
            self.geometryChanged.emit()
        return super().itemChange(change, value)

    def get_connection_sites_scene(self) -> list[tuple[float, float]]:
        """Return scene coordinates of standard connection sites for this shape."""
        local_sites = get_shape_connection_sites(
            self.model.geom, self.model.w, self.model.h, self.model.adj
        )
        scene_sites = []
        for lx, ly in local_sites:
            sp = self.mapToScene(QPointF(lx, ly))
            scene_sites.append((sp.x(), sp.y()))
        return scene_sites

    def update_connector_endpoints(
        self,
        start_pt: tuple[float, float] | QPointF,
        end_pt: tuple[float, float] | QPointF,
        site1_idx: int | None = None,
        site2_idx: int | None = None,
    ) -> None:
        """Update connector position, bounds, and route from scene endpoints."""
        sx = start_pt.x() if isinstance(start_pt, QPointF) else start_pt[0]
        sy = start_pt.y() if isinstance(start_pt, QPointF) else start_pt[1]
        ex = end_pt.x() if isinstance(end_pt, QPointF) else end_pt[0]
        ey = end_pt.y() if isinstance(end_pt, QPointF) else end_pt[1]

        min_x = min(sx, ex)
        min_y = min(sy, ey)
        w = max(1.0, abs(ex - sx))
        h = max(1.0, abs(ey - sy))

        p1_local = (sx - min_x, sy - min_y)
        p2_local = (ex - min_x, ey - min_y)

        route = calculate_connector_route(
            p1_local,
            p2_local,
            geom=self.model.geom,
            site1_idx=site1_idx,
            site2_idx=site2_idx,
        )

        self.prepareGeometryChange()
        self.model.x = round(min_x, 2)
        self.model.y = round(min_y, 2)
        self.model.w = round(w, 2)
        self.model.h = round(h, 2)
        self.model.rot = 0.0
        # The route already runs from start to end, so a parsed flip would mirror it twice.
        self.model.flip_h = False
        self.model.flip_v = False
        self.setPos(min_x, min_y)
        self.setRotation(0.0)

        adj = dict(self.model.adj or {})
        adj["p1"] = [round(sx, 2), round(sy, 2)]
        adj["p2"] = [round(ex, 2), round(ey, 2)]
        adj["route"] = [[round(rx, 2), round(ry, 2)] for rx, ry in route]
        if site1_idx is not None:
            adj["site1"] = site1_idx
        if site2_idx is not None:
            adj["site2"] = site2_idx
        self.model.adj = adj

        self._position_handles()
        self.update()
        sc = self.scene()
        if sc and hasattr(sc, "update_connected_connectors"):
            sc.update_connected_connectors(self.model.id)
        self.geometryChanged.emit()

    def _do_drag_connector_endpoint(
        self,
        handle_type: str,
        scene_pos: QPointF,
        modifiers: Qt.KeyboardModifiers,
    ) -> None:
        """Handle interactive dragging of connector endpoints with magnetic snapping."""
        is_start = handle_type == HandleType.START
        adj = self.model.adj or {}

        # 1. Determine anchor (other endpoint in scene coords)
        p1 = adj.get("p1")
        p2 = adj.get("p2")
        if is_start:
            if p2:
                anchor_pt = QPointF(float(p2[0]), float(p2[1]))
            else:
                anchor_pt = QPointF(self.model.x + self.model.w, self.model.y + self.model.h)
        else:
            if p1:
                anchor_pt = QPointF(float(p1[0]), float(p1[1]))
            else:
                anchor_pt = QPointF(self.model.x, self.model.y)

        # 2. Magnetic snap detection against other shapes in scene
        snap_threshold = 15.0
        best_dist = snap_threshold
        snapped_pos = scene_pos
        snap_target: dict[str, Any] | None = None
        target_item: ShapeGraphicsItem | None = None

        sc = self.scene()
        if sc:
            for item in sc.items():
                if (
                    isinstance(item, ShapeGraphicsItem)
                    and item is not self
                    and not item.model.is_connector
                ):
                    sites = item.get_connection_sites_scene()
                    for idx, (sx, sy) in enumerate(sites):
                        dist = math.hypot(scene_pos.x() - sx, scene_pos.y() - sy)
                        if dist < best_dist:
                            best_dist = dist
                            snapped_pos = QPointF(sx, sy)
                            snap_target = {"id": item.model.id, "idx": idx}
                            target_item = item

        # Clear previous hover highlights on all shapes and mark current target if any
        if sc:
            for item in sc.items():
                if isinstance(item, ShapeGraphicsItem):
                    setattr(item, "_highlight_site_idx", None)
                    setattr(item, "_show_connection_sites", False)

        if target_item and snap_target:
            setattr(target_item, "_highlight_site_idx", snap_target["idx"])
            setattr(target_item, "_show_connection_sites", True)
            target_item.update()

        # Save pending connection to commit on release
        if is_start:
            self._pending_cxn_start = snap_target
            start_scene = snapped_pos
            end_scene = anchor_pt
            s_idx = snap_target["idx"] if snap_target else adj.get("site1")
            e_idx = self.model.cxn_end.get("idx") if self.model.cxn_end else adj.get("site2")
        else:
            self._pending_cxn_end = snap_target
            start_scene = anchor_pt
            end_scene = snapped_pos
            s_idx = self.model.cxn_start.get("idx") if self.model.cxn_start else adj.get("site1")
            e_idx = snap_target["idx"] if snap_target else adj.get("site2")

        self.update_connector_endpoints(
            start_scene,
            end_scene,
            site1_idx=s_idx,
            site2_idx=e_idx,
        )

    # ------------------------------------------------------------------
    # Handle Drag Operations
    # ------------------------------------------------------------------
    def begin_handle_drag(
        self, handle: TransformHandleItem, scene_pos: QPointF
    ) -> None:
        self._drag_start_scene_pos = scene_pos
        self._drag_initial_rect = QRectF(
            self.model.x, self.model.y, self.model.w, self.model.h
        )
        self._drag_initial_rot = self.model.rot
        self._drag_initial_adj = dict(self.model.adj or {})

    def update_handle_drag(
        self,
        handle: TransformHandleItem,
        scene_pos: QPointF,
        modifiers: Qt.KeyboardModifiers,
    ) -> None:
        ht = handle.handle_type
        if ht in (HandleType.START, HandleType.END):
            self._do_drag_connector_endpoint(ht, scene_pos, modifiers)
        elif ht == HandleType.ROTATE:
            self._do_rotate(scene_pos, modifiers)
        elif ht == HandleType.ADJUST:
            self._do_adjust(handle.adjust_index, scene_pos)
        else:
            self._do_resize(ht, scene_pos, modifiers)

    def end_handle_drag(self, handle: TransformHandleItem) -> None:
        ht = handle.handle_type
        if ht == HandleType.START:
            self.model.cxn_start = getattr(self, "_pending_cxn_start", None)
        elif ht == HandleType.END:
            self.model.cxn_end = getattr(self, "_pending_cxn_end", None)

        sc = self.scene()
        if sc:
            for item in sc.items():
                if isinstance(item, ShapeGraphicsItem):
                    setattr(item, "_highlight_site_idx", None)
                    setattr(item, "_show_connection_sites", False)
                    item.update()

        self._position_handles()
        self.update()
        sc = self.scene()
        if sc and hasattr(sc, "update_connected_connectors"):
            sc.update_connected_connectors(self.model.id)
        self.geometryChanged.emit()

    def _do_rotate(
        self, scene_pos: QPointF, modifiers: Qt.KeyboardModifiers
    ) -> None:
        # Calculate center point in scene coords
        center_local = QPointF(self.model.w / 2.0, self.model.h / 2.0)
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

        self.model.rot = round(angle, 1)
        self.setRotation(self.model.rot)
        self.geometryChanged.emit()

    def _do_adjust(self, adjust_index: int, scene_pos: QPointF) -> None:
        local_pos = self.mapFromItem(self, self.mapFromScene(scene_pos))
        defs = get_adjustment_handles(self.model.geom)
        if adjust_index < len(defs):
            new_adj = defs[adjust_index].calculate_adj(
                local_pos.x(),
                local_pos.y(),
                self.model.w,
                self.model.h,
                self._drag_initial_adj,
            )
            self.model.adj = new_adj
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
        self.model.w = round(new_w, 2)
        self.model.h = round(new_h, 2)
        self.setTransformOriginPoint(self.model.w / 2.0, self.model.h / 2.0)
        self.setPos(new_top_left_scene)
        self.model.x = round(new_top_left_scene.x(), 2)
        self.model.y = round(new_top_left_scene.y(), 2)

        self._position_handles()
        self.update()
        sc = self.scene()
        if sc and hasattr(sc, "update_connected_connectors"):
            sc.update_connected_connectors(self.model.id)
        self.geometryChanged.emit()

    def update_from_model(self) -> None:
        """Refresh graphics item state from underlying Shape model."""
        self.prepareGeometryChange()
        self.setPos(self.model.x, self.model.y)
        self.setRotation(self.model.rot)
        self.setTransformOriginPoint(self.model.w / 2.0, self.model.h / 2.0)
        self._position_handles()
        self.update()
