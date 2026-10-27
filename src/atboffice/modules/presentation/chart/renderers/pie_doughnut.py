"""Renderer for Pie and Doughnut charts."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from atboffice.modules.presentation.chart.model import CH_PALETTE, ChartData
from atboffice.modules.presentation.chart.renderers.common import resolve_color


def draw_pie_doughnut(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Pie or Doughnut chart."""
    series = chart.series or []
    if not series:
        return

    s0 = series[0]
    vals = s0.vals
    if not vals:
        return

    total = sum(max(0.0, v) for v in vals)
    if total <= 0:
        total = 1.0

    is_doughnut = chart.kind == "doughnut"
    hole_ratio = 0.5 if is_doughnut else 0.0

    center = plot_rect.center()
    radius = min(plot_rect.width(), plot_rect.height()) / 2.0 * 0.85
    inner_radius = radius * hole_ratio

    start_angle = 90.0  # 12 o'clock

    for i, v in enumerate(vals):
        val = max(0.0, v)
        span_angle = (val / total) * 360.0
        if span_angle <= 0:
            continue

        if chart.pie_colors and i < len(chart.pie_colors):
            col = resolve_color(chart.pie_colors[i])
        else:
            col = QColor(CH_PALETTE[i % len(CH_PALETTE)])

        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.setBrush(QBrush(col))

        path = QPainterPath()
        outer_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)

        if is_doughnut and inner_radius > 0:
            inner_rect = QRectF(
                center.x() - inner_radius,
                center.y() - inner_radius,
                inner_radius * 2,
                inner_radius * 2,
            )
            # Outer arc
            path.arcMoveTo(outer_rect, start_angle)
            path.arcTo(outer_rect, start_angle, -span_angle)
            # Inner arc back
            path.arcTo(inner_rect, start_angle - span_angle, span_angle)
            path.closeSubpath()
        else:
            path.moveTo(center)
            path.arcTo(outer_rect, start_angle, -span_angle)
            path.closeSubpath()

        painter.drawPath(path)

        # Labels (percentages)
        if chart.labels and span_angle > 15.0:
            mid_angle = math.radians(start_angle - span_angle / 2.0)
            label_r = (radius + inner_radius) / 2.0
            lx = center.x() + label_r * math.cos(mid_angle)
            ly = center.y() - label_r * math.sin(mid_angle)

            pct_str = f"{(val / total) * 100:.0f}%"
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(
                QRectF(lx - 25, ly - 8, 50, 16),
                int(Qt.AlignmentFlag.AlignCenter),
                pct_str,
            )

        start_angle -= span_angle
