"""Renderer for XY (Scatter) and Bubble charts."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers.common import (
    draw_marker,
    get_series_color,
)
from atboffice.modules.presentation.chart.scale import scale


def draw_scatter_bubble(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Scatter and Bubble charts."""
    series = chart.series or []
    if not series:
        return

    is_bubble = chart.kind == "bubble"

    # Compute X bounds
    all_xs: list[float] = []
    all_ys: list[float] = []
    all_sizes: list[float] = []

    for s in series:
        xs = s.xs or [float(i + 1) for i in range(len(s.vals))]
        all_xs.extend(xs)
        all_ys.extend(s.vals)
        if is_bubble and s.sizes:
            all_sizes.extend(s.sizes)

    if not all_xs or not all_ys:
        return

    sc_x = scale(
        min(all_xs),
        max(all_xs),
        chart.ax.get("c"),
        length=plot_rect.width(),
        label_sz=chart.fsz,
    )
    sc_y = scale(
        min(all_ys),
        max(all_ys),
        chart.ax.get("v"),
        length=plot_rect.height(),
        label_sz=chart.fsz,
    )

    min_x, max_x = sc_x["min"], sc_x["max"]
    min_y, max_y = sc_y["min"], sc_y["max"]
    span_x = max_x - min_x if max_x != min_x else 1.0
    span_y = max_y - min_y if max_y != min_y else 1.0

    max_size = max(all_sizes) if all_sizes else 1.0
    if max_size <= 0:
        max_size = 1.0

    def pt_to_canvas(x: float, y: float) -> QPointF:
        cx = plot_rect.left() + ((x - min_x) / span_x) * plot_rect.width()
        cy = plot_rect.bottom() - ((y - min_y) / span_y) * plot_rect.height()
        return QPointF(cx, cy)

    for si, s in enumerate(series):
        col = get_series_color(s, si)
        xs = s.xs or [float(i + 1) for i in range(len(s.vals))]

        pts = [pt_to_canvas(x, y) for x, y in zip(xs, s.vals, strict=False)]

        if is_bubble:
            bubble_col = QColor(col)
            bubble_col.setAlphaF(0.6)
            painter.setPen(QPen(col, 1.0))
            painter.setBrush(QBrush(bubble_col))

            for pi, pt in enumerate(pts):
                raw_sz = s.sizes[pi] if s.sizes and pi < len(s.sizes) else 1.0
                r = max(3.0, (raw_sz / max_size) * 24.0)
                painter.drawEllipse(pt, r, r)
        else:
            # Connect line if configured
            if s.line and s.line.get("type") != "none":
                painter.setPen(QPen(col, 1.5))
                for pi in range(len(pts) - 1):
                    painter.drawLine(pts[pi], pts[pi + 1])

            sym = (s.marker.get("sym") if s.marker else None) or "circle"
            for pt in pts:
                draw_marker(painter, sym, pt.x(), pt.y(), 7.0, col, stroke_col=QColor("#FFFFFF"))
