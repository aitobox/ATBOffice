"""Interactive ink drawing annotations and laser pointer overlay layer for Lectern presentations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Fill, Line, Shape

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Safe translation for SlideAnnotationOverlay."""
    app = QApplication.instance()
    if app:
        translated = app.translate("SlideAnnotationOverlay", text)
        if translated and translated != text:
            return translated
    return text


@dataclass
class AnnotationStroke:
    """Freehand vector ink annotation stroke drawn during a presentation."""

    points: list[tuple[float, float]] = field(default_factory=list)
    color: str = "#FF0000"
    width: float = 3.0
    alpha: float = 1.0
    is_highlighter: bool = False


class SlideAnnotationOverlay(QWidget):
    """Transparent overlay viewport capturing and rendering real-time vector ink and laser."""

    strokeAdded = Signal(int, object)  # (slide_index, AnnotationStroke)
    strokeErased = Signal(int, int)  # (slide_index, stroke_index)
    laserMoved = Signal(object)  # (x, y) or None
    modeChanged = Signal(str, str)  # (tool_name, color_hex)

    def __init__(
        self,
        slide_w: float = 960.0,
        slide_h: float = 540.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide_w: float = max(1.0, slide_w)
        self.slide_h: float = max(1.0, slide_h)
        self.slide_index: int = 0

        self.mode: str = "arrow"  # "arrow", "pen", "highlighter", "laser", "eraser"
        self.pen_color: str = "#FF0000"
        self.pen_width: float = 3.0
        self.highlighter_color: str = "#FFFF00"
        self.highlighter_width: float = 16.0
        self.highlighter_alpha: float = 0.4

        self.strokes_map: dict[int, list[AnnotationStroke]] = {}
        self.current_stroke: AnnotationStroke | None = None
        self.laser_pos: tuple[float, float] | None = None
        self.blank_color: QColor | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_slide_index(self, idx: int) -> None:
        """Switch current active slide index."""
        self.slide_index = idx
        self.current_stroke = None
        self.update()

    def set_mode(
        self,
        mode: str,
        color: str | None = None,
        width: float | None = None,
    ) -> None:
        """Set pointer/drawing tool mode."""
        self.mode = mode
        if color:
            self.pen_color = color
        if width:
            self.pen_width = width

        if mode != "laser":
            self.laser_pos = None

        if mode == "arrow":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode in ("pen", "highlighter"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "laser":
            self.setCursor(Qt.CursorShape.BlankCursor)
        elif mode == "eraser":
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.modeChanged.emit(self.mode, self.pen_color)
        self.update()

    def get_strokes(self, slide_index: int) -> list[AnnotationStroke]:
        """Return ink strokes for given slide."""
        return self.strokes_map.get(slide_index, [])

    def set_strokes(self, slide_index: int, strokes: list[AnnotationStroke]) -> None:
        """Set ink strokes for given slide."""
        self.strokes_map[slide_index] = list(strokes)
        self.update()

    def clear_slide_ink(self, slide_index: int) -> None:
        """Clear all ink strokes for given slide."""
        self.strokes_map[slide_index] = []
        self.current_stroke = None
        self.update()

    def clear_all_ink(self) -> None:
        """Clear ink strokes across all slides."""
        self.strokes_map.clear()
        self.current_stroke = None
        self.update()

    def has_ink(self) -> bool:
        """Check if any slide contains ink annotations."""
        return any(len(strokes) > 0 for strokes in self.strokes_map.values())

    def export_strokes_as_shapes(self, slide_index: int) -> list[Shape]:
        """Convert strokes on given slide into DrawingML freeform Shape objects."""
        shapes: list[Shape] = []
        strokes = self.get_strokes(slide_index)
        for i, s in enumerate(strokes):
            if not s.points:
                continue
            poly_pts = [list(pt) for pt in s.points]
            line_style = Line(
                color=s.color,
                width=s.width,
            )
            ink_shape = Shape(
                id=f"ink_{slide_index}_{i}",
                type="shape",
                name=f"Ink Annotation {i + 1}",
                geom="freeform",
                poly=poly_pts,
                line=line_style,
                fill=Fill.none(),
            )
            shapes.append(ink_shape)
        return shapes

    def _get_stage_geometry(self) -> tuple[float, float, float, float, float]:
        """Calculate letterboxed stage offset and scaling: (ox, oy, sw, sh, scale)."""
        vw, vh = float(self.width()), float(self.height())
        pw = max(1.0, self.slide_w)
        ph = max(1.0, self.slide_h)
        scale = min(vw / pw, vh / ph)
        if scale <= 0:
            scale = 1.0
        sw = pw * scale
        sh = ph * scale
        ox = (vw - sw) / 2.0
        oy = (vh - sh) / 2.0
        return ox, oy, sw, sh, scale

    def to_slide_pt(self, pos: QPointF | tuple[float, float]) -> tuple[float, float]:
        """Convert viewport pixel coordinates to slide canvas coordinates."""
        px = pos.x() if isinstance(pos, QPointF) else pos[0]
        py = pos.y() if isinstance(pos, QPointF) else pos[1]
        ox, oy, sw, sh, scale = self._get_stage_geometry()
        scale_x = sw / max(1.0, self.slide_w)
        scale_y = sh / max(1.0, self.slide_h)
        if scale_x <= 0 or scale_y <= 0:
            return px, py
        sx = (px - ox) / scale_x
        sy = (py - oy) / scale_y
        return sx, sy

    def to_widget_pt(self, sx: float, sy: float) -> QPointF:
        """Convert slide canvas coordinates to viewport pixel coordinates."""
        ox, oy, sw, sh, scale = self._get_stage_geometry()
        scale_x = sw / max(1.0, self.slide_w)
        scale_y = sh / max(1.0, self.slide_h)
        wx = ox + sx * scale_x
        wy = oy + sy * scale_y
        return QPointF(wx, wy)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            sp = self.to_slide_pt(event.position())
            if self.mode == "pen":
                stroke = AnnotationStroke(
                    points=[sp],
                    color=self.pen_color,
                    width=self.pen_width,
                    alpha=1.0,
                    is_highlighter=False,
                )
                self.current_stroke = stroke
                if self.slide_index not in self.strokes_map:
                    self.strokes_map[self.slide_index] = []
                self.strokes_map[self.slide_index].append(stroke)
                self.update()
                event.accept()
                return
            elif self.mode == "highlighter":
                stroke = AnnotationStroke(
                    points=[sp],
                    color=self.highlighter_color,
                    width=self.highlighter_width,
                    alpha=self.highlighter_alpha,
                    is_highlighter=True,
                )
                self.current_stroke = stroke
                if self.slide_index not in self.strokes_map:
                    self.strokes_map[self.slide_index] = []
                self.strokes_map[self.slide_index].append(stroke)
                self.update()
                event.accept()
                return
            elif self.mode == "laser":
                self.laser_pos = sp
                self.laserMoved.emit(self.laser_pos)
                self.update()
                event.accept()
                return
            elif self.mode == "eraser":
                self._erase_at(sp)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        sp = self.to_slide_pt(event.position())
        if self.mode in ("pen", "highlighter") and self.current_stroke is not None:
            self.current_stroke.points.append(sp)
            self.update()
            event.accept()
            return
        elif self.mode == "laser":
            self.laser_pos = sp
            self.laserMoved.emit(self.laser_pos)
            self.update()
            event.accept()
            return
        elif self.mode == "eraser":
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._erase_at(sp)
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_stroke is not None:
                self.strokeAdded.emit(self.slide_index, self.current_stroke)
                self.current_stroke = None
                self.update()
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def _erase_at(self, pt: tuple[float, float], threshold: float = 24.0) -> None:
        """Hit test and remove strokes near given slide point."""
        strokes = self.strokes_map.get(self.slide_index, [])
        px, py = pt
        for idx in range(len(strokes) - 1, -1, -1):
            stroke = strokes[idx]
            hit = False
            for sx, sy in stroke.points:
                if math.hypot(sx - px, sy - py) <= threshold:
                    hit = True
                    break
            if hit:
                strokes.pop(idx)
                self.strokeErased.emit(self.slide_index, idx)
                self.update()
                break

    def render_overlay(self, painter: QPainter, stage_rect: QRectF, scale: float) -> None:
        """Render annotations and laser pointer on an external painter."""
        ox = stage_rect.left()
        oy = stage_rect.top()
        sw = stage_rect.width()
        sh = stage_rect.height()
        scale_x = sw / max(1.0, self.slide_w)
        scale_y = sh / max(1.0, self.slide_h)

        # Draw strokes
        strokes = self.get_strokes(self.slide_index)
        for stroke in strokes:
            pts = stroke.points
            if len(pts) < 2:
                continue
            qc = QColor(stroke.color)
            qc.setAlphaF(min(1.0, max(0.0, stroke.alpha)))
            width = max(1.0, stroke.width * scale)
            pen = QPen(qc, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            path = QPainterPath()
            first = True
            for px, py in pts:
                wx = ox + px * scale_x
                wy = oy + py * scale_y
                if first:
                    path.moveTo(wx, wy)
                    first = False
                else:
                    path.lineTo(wx, wy)
            painter.drawPath(path)

        # Draw laser pointer
        if self.laser_pos is not None:
            lx, ly = self.laser_pos
            wx = ox + lx * scale_x
            wy = oy + ly * scale_y

            halo_rad = 18.0 * scale
            gradient = QRadialGradient(wx, wy, halo_rad)
            gradient.setColorAt(0.0, QColor(255, 30, 30, 230))
            gradient.setColorAt(0.35, QColor(255, 60, 60, 150))
            gradient.setColorAt(1.0, QColor(255, 60, 60, 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(wx, wy), halo_rad, halo_rad)

            core_rad = 4.5 * scale
            painter.setBrush(QColor(255, 255, 255, 255))
            painter.drawEllipse(QPointF(wx, wy), core_rad, core_rad)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            ox, oy, sw, sh, scale = self._get_stage_geometry()
            stage_rect = QRectF(ox, oy, sw, sh)
            self.render_overlay(painter, stage_rect, scale)
        finally:
            painter.end()

    def retranslate_ui(self) -> None:
        """Support dynamic language switching."""
        self.update()
