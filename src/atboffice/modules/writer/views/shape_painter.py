"""Paint Quire DrawingML / VML shapes: geometry, fill, outline and text box content.

Canvas-agnostic: the caller passes the destination rectangle (device units), the
device units per point, and callbacks that paint one laid-out text line or table
at a point offset from a device-space origin. Shapes with no fill, no outline and
no text paint nothing.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen

from atboffice.modules.presentation.views.geometry_helper import (
    create_shape_path,
    flip_transform,
)
from atboffice.modules.writer.models.document import Paragraph
from atboffice.modules.writer.models.drawing import ShapeItem

OPEN_GEOMETRIES = frozenset({"line", "straightConnector1", "arc", "bentConnector3", "curvedConnector3"})

_DASH_STYLES = {
    "solid": Qt.PenStyle.SolidLine,
    "dot": Qt.PenStyle.DotLine,
    "dash": Qt.PenStyle.DashLine,
    "dashDot": Qt.PenStyle.DashDotLine,
    "dashDotDot": Qt.PenStyle.DashDotDotLine,
}

# (painter, origin in device units, line or table layout, x_pt, y_pt) -> None
LinePainter = Callable[[QPainter, QPointF, Any, float, float], None]
# (painter, shape, device rect) -> None, for picture members of groups
ImagePainter = Callable[[QPainter, ShapeItem, QRectF], None]


@dataclass
class TextBlock:
    """One laid-out text box block positioned in the shape's text area (points)."""

    kind: str  # "line" or "table"
    layout: Any
    x: float
    y: float


def _color(hex_color: str, alpha: float = 1.0) -> QColor:
    col = QColor(hex_color or "#000000")
    if not col.isValid():
        col = QColor("#000000")
    col.setAlphaF(max(0.0, min(1.0, alpha)))
    return col


def fill_brush(fill: Any, rect: QRectF) -> QBrush:
    """Brush for a ``DmlFill`` inside ``rect``; ``NoBrush`` for no fill."""
    kind = getattr(fill, "kind", "none") if fill is not None else "none"
    if kind == "none":
        return QBrush(Qt.BrushStyle.NoBrush)
    if kind == "gradient" and getattr(fill, "stops", None):
        rad = math.radians(float(fill.angle))
        dx, dy = math.cos(rad), math.sin(rad)
        half = (abs(rect.width() * dx) + abs(rect.height() * dy)) / 2.0
        c = rect.center()
        grad = QLinearGradient(
            QPointF(c.x() - dx * half, c.y() - dy * half),
            QPointF(c.x() + dx * half, c.y() + dy * half),
        )
        for pos, col, alpha in fill.stops:
            grad.setColorAt(max(0.0, min(1.0, pos)), _color(col, alpha))
        return QBrush(grad)
    return QBrush(_color(fill.color, getattr(fill, "alpha", 1.0)))


def outline_pen(line: Any, scale: float) -> QPen:
    """Pen for a ``DmlLine``; ``NoPen`` when the outline is hidden."""
    if line is None or not getattr(line, "visible", False):
        return QPen(Qt.PenStyle.NoPen)
    pen = QPen(_color(line.color, line.alpha), max(0.5, float(line.width)) * scale)
    pen.setStyle(_DASH_STYLES.get(getattr(line, "dash", "solid"), Qt.PenStyle.SolidLine))
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return pen


def layout_shape_text(shape: ShapeItem, doc: Any = None) -> list[TextBlock]:
    """Lay out the text box story inside the shape insets, honoring the vertical anchor.

    The result is cached on the shape and recomputed when its size changes.
    """
    if shape.story is None or not shape.story.blocks:
        return []
    key = (round(shape.width, 2), round(shape.height, 2), tuple(shape.insets), shape.v_anchor)
    cached = getattr(shape, "_text_layout_cache", None)
    if cached is not None and cached[0] == key:
        return cached[1]

    from atboffice.modules.writer.layout.portions import layout_paragraph
    from atboffice.modules.writer.layout.table_layout import layout_table

    left, top, right, bottom = shape.insets
    avail_w = max(1.0, shape.width - left - right)
    blocks: list[TextBlock] = []
    y = 0.0
    prev: Paragraph | None = None
    for i, block in enumerate(shape.story.blocks):
        try:
            if isinstance(block, Paragraph):
                pl = layout_paragraph(
                    p=block,
                    container_width=avail_w,
                    doc=doc,
                    prev_paragraph=prev,
                    is_page_top=i == 0,
                )
                y += pl.effective_space_before if i else 0.0
                for line in pl.lines:
                    blocks.append(TextBlock("line", line, left + line.indent_left, y + line.top))
                y += pl.height + pl.space_after
                prev = block
            elif getattr(block, "rows", None) is not None:
                tl = layout_table(block, container_width=avail_w, doc=doc)
                blocks.append(TextBlock("table", tl, left + getattr(tl, "x", 0.0), y))
                y += getattr(tl, "height", 0.0)
                prev = None
        except Exception:
            continue

    avail_h = shape.height - top - bottom
    if shape.v_anchor == "ctr":
        dy = top + max(0.0, (avail_h - y) / 2.0)
    elif shape.v_anchor == "b":
        dy = top + max(0.0, avail_h - y)
    else:
        dy = top
    for tb in blocks:
        tb.y += dy
        if tb.kind == "line" and shape.text_color:
            # automatic text color follows the shape style's fontRef (e.g. lt1 on accent fills)
            for po in tb.layout.portions:
                if getattr(po, "color", None) in (None, "", "auto"):
                    po.color = shape.text_color
    shape._text_layout_cache = (key, blocks)  # type: ignore[attr-defined]
    return blocks


def paint_shape(
    painter: QPainter,
    shape: ShapeItem,
    rect: QRectF,
    scale: float,
    paint_line: LinePainter | None = None,
    paint_table: LinePainter | None = None,
    paint_image: ImagePainter | None = None,
    doc: Any = None,
) -> None:
    """Paint ``shape`` into ``rect`` (device units, ``scale`` device units per point)."""
    if rect.width() <= 0 or rect.height() <= 0 or shape.is_invisible:
        return
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rot = float(shape.rotation or 0.0)
        if rot:
            c = rect.center()
            painter.translate(c)
            painter.rotate(rot)
            painter.translate(-c)

        if shape.children:
            sx = rect.width() / shape.width if shape.width > 0 else scale
            sy = rect.height() / shape.height if shape.height > 0 else scale
            if shape.fill is not None and shape.fill.kind != "none":
                painter.fillRect(rect, fill_brush(shape.fill, rect))
            for ch in shape.children:
                child_rect = QRectF(
                    rect.left() + ch.x * sx,
                    rect.top() + ch.y * sy,
                    ch.item.width * sx,
                    ch.item.height * sy,
                )
                if shape.flip_h:
                    child_rect.moveLeft(2 * rect.left() + rect.width() - child_rect.right())
                if shape.flip_v:
                    child_rect.moveTop(2 * rect.top() + rect.height() - child_rect.bottom())
                if ch.item.image_part and not ch.item.children:
                    if paint_image is not None:
                        paint_image(painter, ch.item, child_rect)
                    continue
                paint_shape(
                    painter, ch.item, child_rect, scale, paint_line, paint_table, paint_image, doc
                )
            return

        _paint_geometry(painter, shape, rect, scale)
        if paint_line is None:
            return
        origin = rect.topLeft()
        for tb in layout_shape_text(shape, doc):
            if tb.kind == "line":
                paint_line(painter, origin, tb.layout, tb.x, tb.y)
            elif paint_table is not None:
                paint_table(painter, origin, tb.layout, tb.x, tb.y)
    finally:
        painter.restore()


def _paint_geometry(painter: QPainter, shape: ShapeItem, rect: QRectF, scale: float) -> None:
    w, h = max(1.0, rect.width()), max(1.0, rect.height())
    adj = shape.adjustments or None
    path = create_shape_path(shape.geometry, w, h, adj, shape.custom_path)
    if shape.flip_h or shape.flip_v:
        path = flip_transform(w, h, shape.flip_h, shape.flip_v).map(path)
    path.translate(rect.left(), rect.top())
    if shape.geometry not in OPEN_GEOMETRIES:
        brush = fill_brush(shape.fill, rect)
        if brush.style() != Qt.BrushStyle.NoBrush:
            painter.fillPath(path, brush)
    pen = outline_pen(shape.line, scale)
    if pen.style() != Qt.PenStyle.NoPen:
        painter.strokePath(path, pen)
