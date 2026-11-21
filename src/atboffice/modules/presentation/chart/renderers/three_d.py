"""Oblique 3-D geometry for column and bar charts (``c:bar3DChart``).

The chart is seen obliquely: depth is a 2-D offset ``(dx, dy)`` derived from
the ``c:view3D`` rotation angles, the way the reference renderer draws it.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF

from atboffice.modules.presentation.chart.model import ChartData

BAR_KINDS = ("col", "colStacked", "colPct", "bar", "barStacked", "barPct")
WALL_LINE = "#BFBFBF"

Offset = tuple[float, float]


def is_3d_bar(chart: ChartData) -> bool:
    """True when the chart is a column/bar chart seen at a non-zero 3-D angle."""
    v3 = chart.view3d
    if not v3 or chart.kind not in BAR_KINDS:
        return False
    return bool(float(v3.get("rotX", 0) or 0) or float(v3.get("rotY", 0) or 0))


def is_deep(chart: ChartData) -> bool:
    """Series sit in separate depth rows (``grouping="standard"``), never when stacked."""
    return bool(
        chart.view3d
        and chart.view3d.get("deep")
        and chart.kind in ("col", "bar")
    )


def depth_offset(
    view3d: dict[str, Any],
    rect: QRectF,
    n_cats: int,
    n_series: int,
    horizontal: bool,
) -> Offset:
    """Screen offset of the back of the plot relative to its front."""
    rot_x = float(view3d.get("rotX", 0) or 0)
    rot_y = float(view3d.get("rotY", 0) or 0)
    if not rot_x and not rot_y:
        return (0.0, 0.0)
    deep = bool(view3d.get("deep"))
    n_deep = max(1, n_series) if deep else 1
    share = 0.32 if deep else 0.18
    band = (rect.height() if horizontal else rect.width()) / max(n_cats, 1)
    depth = min(band * 0.45 * n_deep, rect.height() * share, rect.width() * share)
    depth *= max(0.2, min(2.0, float(view3d.get("depth", 100) or 100) / 100.0))
    vx = math.sin(math.radians(rot_y))
    vy = math.sin(math.radians(rot_x))
    norm = math.hypot(vx, vy) or 1.0
    return (depth * vx / norm, -depth * vy / norm)


def shrink_for_depth(rect: QRectF, dx: float, dy: float) -> QRectF:
    """Front plot box that leaves room for the depth inside ``rect``."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    if dx > 0:
        w -= dx
    else:
        x -= dx
        w += dx
    if dy < 0:
        y -= dy
        h += dy
    else:
        h -= dy
    return QRectF(x, y, max(4.0, w), max(4.0, h))


def depth_grid_segments(
    rect: QRectF,
    dx: float,
    dy: float,
    positions: list[float],
    horizontal: bool,
) -> list[tuple[QPointF, QPointF]]:
    """Value gridlines on the back wall plus their run across the side wall/floor."""
    segs: list[tuple[QPointF, QPointF]] = []
    if horizontal:
        for x in positions:
            segs.append((QPointF(x + dx, rect.top() + dy), QPointF(x + dx, rect.bottom() + dy)))
            segs.append((QPointF(x, rect.bottom()), QPointF(x + dx, rect.bottom() + dy)))
    else:
        side_x = rect.left() if dx >= 0 else rect.right()
        for y in positions:
            segs.append((QPointF(rect.left() + dx, y + dy), QPointF(rect.right() + dx, y + dy)))
            segs.append((QPointF(side_x, y), QPointF(side_x + dx, y + dy)))
    return segs


def draw_walls(
    painter: QPainter,
    rect: QRectF,
    dx: float,
    dy: float,
    horizontal: bool,
) -> None:
    """Outline the back wall, side wall and floor of the 3-D plot."""
    x0, y0, x1, y1 = rect.left(), rect.top(), rect.right(), rect.bottom()
    back = [(x0 + dx, y0 + dy), (x1 + dx, y0 + dy), (x1 + dx, y1 + dy), (x0 + dx, y1 + dy)]
    floor = [(x0, y1), (x1, y1), (x1 + dx, y1 + dy), (x0 + dx, y1 + dy)]
    side_x = x0 if (horizontal or dx >= 0) else x1
    side = [(side_x, y0), (side_x + dx, y0 + dy), (side_x + dx, y1 + dy), (side_x, y1)]
    painter.setPen(QPen(QColor(WALL_LINE), 0.75))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for pts in (back, side, floor):
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))


def shade(color: QColor, amount: float) -> QColor:
    """Mix toward white (``amount > 0``) or black (``amount < 0``)."""
    r, g, b = color.red(), color.green(), color.blue()
    if amount >= 0:
        mix = lambda c: round(c + (255 - c) * amount)  # noqa: E731
    else:
        mix = lambda c: round(c * (1 + amount))  # noqa: E731
    return QColor(mix(r), mix(g), mix(b), color.alpha())


def draw_box(
    painter: QPainter,
    front: QRectF,
    color: QColor,
    dx: float,
    dy: float,
) -> None:
    """A box: the front face, then a lighter top and a darker side."""
    edge = QPen(color.darker(110), 0.5)
    painter.setPen(edge)
    painter.setBrush(QBrush(color))
    painter.drawRect(front)
    bx, by, bw, bh = front.x(), front.y(), front.width(), front.height()
    top = [(bx, by), (bx + bw, by), (bx + bw + dx, by + dy), (bx + dx, by + dy)]
    sx = bx + bw if dx >= 0 else bx
    side = [(sx, by), (sx + dx, by + dy), (sx + dx, by + bh + dy), (sx, by + bh)]
    for pts, col in ((top, shade(color, 0.25)), (side, shade(color, -0.25))):
        painter.setBrush(QBrush(col))
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in pts]))
