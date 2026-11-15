"""Painting helpers for imported DrawingML floating objects on the worksheet.

Covers preset/custom geometry, gradient and pattern fills, line ends, group
children and aspect-locked pictures. Objects created in Ledger without a
``geometry`` keep using the simple painter in ``object_layer``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    flip_transform,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.views.object_layer import FloatingObject

OPEN_GEOMETRIES = frozenset(
    {
        "line",
        "straightConnector1",
        "bentConnector2",
        "bentConnector3",
        "bentConnector4",
        "bentConnector5",
        "curvedConnector2",
        "curvedConnector3",
        "arc",
    }
)

_PATTERN_STYLES: dict[str, Qt.BrushStyle] = {
    "pct5": Qt.BrushStyle.Dense7Pattern,
    "pct10": Qt.BrushStyle.Dense7Pattern,
    "pct20": Qt.BrushStyle.Dense6Pattern,
    "pct25": Qt.BrushStyle.Dense6Pattern,
    "pct30": Qt.BrushStyle.Dense5Pattern,
    "pct40": Qt.BrushStyle.Dense5Pattern,
    "pct50": Qt.BrushStyle.Dense4Pattern,
    "pct60": Qt.BrushStyle.Dense3Pattern,
    "pct70": Qt.BrushStyle.Dense3Pattern,
    "pct75": Qt.BrushStyle.Dense2Pattern,
    "pct80": Qt.BrushStyle.Dense2Pattern,
    "pct90": Qt.BrushStyle.Dense1Pattern,
    "horz": Qt.BrushStyle.HorPattern,
    "ltHorz": Qt.BrushStyle.HorPattern,
    "dkHorz": Qt.BrushStyle.HorPattern,
    "vert": Qt.BrushStyle.VerPattern,
    "ltVert": Qt.BrushStyle.VerPattern,
    "dkVert": Qt.BrushStyle.VerPattern,
    "cross": Qt.BrushStyle.CrossPattern,
    "smGrid": Qt.BrushStyle.CrossPattern,
    "lgGrid": Qt.BrushStyle.CrossPattern,
    "upDiag": Qt.BrushStyle.BDiagPattern,
    "ltUpDiag": Qt.BrushStyle.BDiagPattern,
    "dkUpDiag": Qt.BrushStyle.BDiagPattern,
    "wdUpDiag": Qt.BrushStyle.BDiagPattern,
    "dnDiag": Qt.BrushStyle.FDiagPattern,
    "ltDnDiag": Qt.BrushStyle.FDiagPattern,
    "dkDnDiag": Qt.BrushStyle.FDiagPattern,
    "wdDnDiag": Qt.BrushStyle.FDiagPattern,
    "diagCross": Qt.BrushStyle.DiagCrossPattern,
    "openDmnd": Qt.BrushStyle.DiagCrossPattern,
}


def child_rect(parent: QRect, frac: tuple[float, float, float, float] | None) -> QRect:
    """Map a group child's fractional frame into its parent's rectangle."""
    if frac is None:
        return QRect(parent)
    fx, fy, fw, fh = frac
    return QRect(
        round(parent.x() + fx * parent.width()),
        round(parent.y() + fy * parent.height()),
        max(1, round(fw * parent.width())),
        max(1, round(fh * parent.height())),
    )


def fit_aspect_rect(rect: QRect, src_w: int, src_h: int) -> QRect:
    """Largest rectangle with the source aspect ratio, centred inside ``rect``."""
    if src_w <= 0 or src_h <= 0 or rect.width() <= 0 or rect.height() <= 0:
        return QRect(rect)
    scale = min(rect.width() / src_w, rect.height() / src_h)
    w = max(1, round(src_w * scale))
    h = max(1, round(src_h * scale))
    return QRect(
        rect.x() + (rect.width() - w) // 2, rect.y() + (rect.height() - h) // 2, w, h
    )


def _color(hex_color: str, alpha: float) -> QColor:
    col = QColor(hex_color)
    if not col.isValid():
        col = QColor("#000000")
    col.setAlphaF(max(0.0, min(1.0, alpha)))
    return col


def fill_brush(obj: FloatingObject, rect: QRectF) -> QBrush:
    """Build the brush for an object's fill inside ``rect``."""
    if obj.fill_type == "none":
        return QBrush(Qt.BrushStyle.NoBrush)
    if obj.fill_type == "gradient" and obj.gradient_stops:
        # DrawingML a:lin ang: clockwise from +x in y-down space; the gradient
        # line spans the rect's projection on that direction.
        rad = math.radians(obj.gradient_angle)
        dx, dy = math.cos(rad), math.sin(rad)
        half = (abs(rect.width() * dx) + abs(rect.height() * dy)) / 2.0
        c = rect.center()
        grad = QLinearGradient(
            QPointF(c.x() - dx * half, c.y() - dy * half),
            QPointF(c.x() + dx * half, c.y() + dy * half),
        )
        for pos, col, alpha in obj.gradient_stops:
            grad.setColorAt(max(0.0, min(1.0, pos)), _color(col, alpha))
        return QBrush(grad)
    if obj.fill_type == "pattern":
        style = _PATTERN_STYLES.get(obj.pattern, Qt.BrushStyle.Dense4Pattern)
        return QBrush(_color(obj.fill_color, obj.fill_alpha), style)
    return QBrush(_color(obj.fill_color, obj.fill_alpha))


def shape_path(obj: FloatingObject, rect: QRect) -> QPainterPath:
    """Return the object's outline path in widget coordinates."""
    w, h = float(max(1, rect.width())), float(max(1, rect.height()))
    path = create_shape_path(obj.geometry, w, h, obj.geometry_adj, obj.custom_path)
    if obj.flip_h or obj.flip_v:
        path = flip_transform(w, h, obj.flip_h, obj.flip_v).map(path)
    return path.translated(float(rect.x()), float(rect.y()))


def _arrow_head(painter: QPainter, tip: QPointF, origin: QPointF, size: float) -> None:
    ang = math.atan2(tip.y() - origin.y(), tip.x() - origin.x())
    spread = math.radians(25)
    p1 = QPointF(tip.x() - size * math.cos(ang - spread), tip.y() - size * math.sin(ang - spread))
    p2 = QPointF(tip.x() - size * math.cos(ang + spread), tip.y() - size * math.sin(ang + spread))
    painter.save()
    painter.setBrush(QBrush(painter.pen().color()))
    painter.drawPolygon(QPolygonF([tip, p1, p2]))
    painter.restore()


def _path_end_segment(path: QPainterPath, at_start: bool) -> tuple[QPointF, QPointF] | None:
    n = path.elementCount()
    if n < 2:
        return None
    if at_start:
        a, b = path.elementAt(0), path.elementAt(1)
    else:
        a, b = path.elementAt(n - 2), path.elementAt(n - 1)
        a, b = b, a
    return QPointF(a.x, a.y), QPointF(b.x, b.y)


def paint_geometry(painter: QPainter, obj: FloatingObject, rect: QRect) -> None:
    """Paint a preset or custom geometry shape with its fill, outline and line ends."""
    path = shape_path(obj, rect)
    is_open = obj.geometry in OPEN_GEOMETRIES or obj.kind == "line"
    painter.save()
    if obj.fill_type == "pattern" and not is_open:
        painter.fillPath(path, QBrush(_color(obj.pattern_bg, obj.fill_alpha)))
    no_brush = QBrush(Qt.BrushStyle.NoBrush)
    painter.setBrush(no_brush if is_open else fill_brush(obj, path.boundingRect()))
    if obj.line_visible:
        painter.setPen(QPen(QColor(obj.line_color), max(0.5, obj.line_width)))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)
    if obj.line_visible:
        size = max(6.0, obj.line_width * 3.0)
        for end_type, at_start in ((obj.head_end, True), (obj.tail_end, False)):
            if not end_type:
                continue
            seg = _path_end_segment(path, at_start)
            if seg is not None:
                _arrow_head(painter, seg[0], seg[1], size)
    painter.restore()


def paint_image(painter: QPainter, obj: FloatingObject, rect: QRect) -> None:
    """Paint a picture; aspect-locked pictures are fitted, undecodable ones get a placeholder."""
    pix = QPixmap()
    if obj.image_data and pix.loadFromData(obj.image_data):
        target = fit_aspect_rect(rect, pix.width(), pix.height()) if obj.lock_aspect else rect
        painter.drawPixmap(target, pix)
        return
    # Unsupported format (e.g. WMF/EMF): neutral frame instead of a shape-colored box.
    painter.save()
    painter.setBrush(QBrush(QColor(242, 242, 242)))
    painter.setPen(QPen(QColor(166, 166, 166), 1, Qt.PenStyle.DashLine))
    painter.drawRect(rect)
    painter.restore()
