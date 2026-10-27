"""Renderer for Radar (Spider / Web) and Filled Radar charts."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers.common import (
    draw_marker,
    get_series_color,
)
from atboffice.modules.presentation.chart.scale import scale


def draw_radar(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Radar and Filled Radar charts."""
    cats = chart.cats or ["Cat 1", "Cat 2", "Cat 3"]
    series = chart.series or []
    n_cats = len(cats)
    if n_cats < 3 or not series:
        return

    is_filled = chart.kind == "radarFilled"
    center = plot_rect.center()
    max_radius = min(plot_rect.width(), plot_rect.height()) / 2.0 * 0.8

    all_vals = [v for s in series for v in s.vals]
    lo = min(0.0, min(all_vals) if all_vals else 0.0)
    hi = max(all_vals) if all_vals else 1.0

    sc = scale(lo, hi, chart.ax.get("v"), length=max_radius, label_sz=chart.fsz)
    min_v, max_v = sc["min"], sc["max"]
    val_range = max_v - min_v if max_v != min_v else 1.0

    angle_step = (2.0 * math.pi) / n_cats
    start_angle = -math.pi / 2.0  # 12 o'clock

    # Draw spider grid web
    ticks = sc.get("ticks", [0.0, max_v])
    painter.setPen(QPen(QColor("#D9D9D9"), 0.75, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    for tick in ticks:
        ratio = (tick - min_v) / val_range
        r = max(0.0, ratio * max_radius)
        if r <= 0:
            continue
        ring_path = QPainterPath()
        for ci in range(n_cats):
            ang = start_angle + ci * angle_step
            pt = QPointF(center.x() + r * math.cos(ang), center.y() + r * math.sin(ang))
            if ci == 0:
                ring_path.moveTo(pt)
            else:
                ring_path.lineTo(pt)
        ring_path.closeSubpath()
        painter.drawPath(ring_path)

    # Draw radial spokes & category labels
    painter.setPen(QPen(QColor("#CCCCCC"), 1.0))
    cat_font = QFont("sans-serif")
    cat_font.setPointSizeF(max(7.0, chart.fsz * 0.9))
    painter.setFont(cat_font)

    for ci, cat in enumerate(cats):
        ang = start_angle + ci * angle_step
        spoke_end = QPointF(
            center.x() + max_radius * math.cos(ang),
            center.y() + max_radius * math.sin(ang),
        )
        painter.drawLine(center, spoke_end)

        label_pt = QPointF(
            center.x() + (max_radius + 12.0) * math.cos(ang),
            center.y() + (max_radius + 12.0) * math.sin(ang),
        )
        painter.setPen(QPen(QColor("#555555")))
        painter.drawText(
            QRectF(label_pt.x() - 35, label_pt.y() - 8, 70, 16),
            int(Qt.AlignmentFlag.AlignCenter),
            cat,
        )

    # Draw series polygons
    for si, s in enumerate(series):
        col = get_series_color(s, si)
        pts: list[QPointF] = []

        for ci in range(n_cats):
            v = s.vals[ci] if ci < len(s.vals) else 0.0
            ratio = (v - min_v) / val_range
            r = max(0.0, ratio * max_radius)
            ang = start_angle + ci * angle_step
            pts.append(QPointF(center.x() + r * math.cos(ang), center.y() + r * math.sin(ang)))

        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            path.closeSubpath()

        if is_filled:
            fill_col = QColor(col)
            fill_col.setAlphaF(0.4)
            painter.setPen(QPen(col, 1.5))
            painter.setBrush(QBrush(fill_col))
            painter.drawPath(path)
        else:
            painter.setPen(QPen(col, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            for pt in pts:
                draw_marker(
                    painter,
                    "circle",
                    pt.x(),
                    pt.y(),
                    5.0,
                    col,
                    stroke_col=QColor("#FFFFFF"),
                )
