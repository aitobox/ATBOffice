"""Renderer for Line and Area charts (Standard, Markers, Stacked, 100% Stacked)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers.common import (
    draw_marker,
    get_series_color,
)
from atboffice.modules.presentation.chart.scale import format_val, scale


def draw_lines(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Line and Line with Markers charts."""
    cats = chart.cats or [""]
    series = chart.series or []
    n_cats = len(cats)
    if n_cats == 0 or not series:
        return

    all_vals = [v for s in series for v in s.vals]
    lo = min(all_vals) if all_vals else 0.0
    hi = max(all_vals) if all_vals else 1.0

    sc = scale(lo, hi, chart.ax.get("v"), length=plot_rect.height(), label_sz=chart.fsz)
    min_v, max_v = sc["min"], sc["max"]
    val_range = max_v - min_v if max_v != min_v else 1.0

    slot_w = plot_rect.width() / max(1, n_cats - 1 if n_cats > 1 else 1)

    def cat_x(ci: int) -> float:
        if n_cats <= 1:
            return plot_rect.center().x()
        return plot_rect.left() + ci * slot_w

    def val_y(v: float) -> float:
        ratio = (v - min_v) / val_range
        return plot_rect.bottom() - ratio * plot_rect.height()

    for si, s in enumerate(series):
        col = get_series_color(s, si)
        pen = QPen(col, 2.0)
        painter.setPen(pen)

        pts: list[QPointF] = []
        for ci in range(n_cats):
            if ci < len(s.vals):
                pts.append(QPointF(cat_x(ci), val_y(s.vals[ci])))

        if not pts:
            continue

        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        painter.drawPath(path)

        # Draw markers if lineMarkers or custom marker
        show_marker = chart.kind == "lineMarkers" or (s.marker and s.marker.get("sym") != "none")
        sym = (s.marker.get("sym") if s.marker else None) or ("circle" if show_marker else "none")

        if show_marker:
            for pt in pts:
                draw_marker(painter, sym, pt.x(), pt.y(), 6.0, col, stroke_col=QColor("#FFFFFF"))

        if chart.labels:
            painter.setPen(QPen(QColor("#333333")))
            for ci, pt in enumerate(pts):
                val_str = format_val(s.vals[ci])
                painter.drawText(
                    QRectF(pt.x() - 25, pt.y() - 16, 50, 14),
                    int(Qt.AlignmentFlag.AlignCenter),
                    val_str,
                )


def draw_areas(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Standard, Stacked, and 100% Stacked Area charts."""
    cats = chart.cats or [""]
    series = chart.series or []
    n_cats = len(cats)
    if n_cats == 0 or not series:
        return

    is_pct = chart.kind == "areaPct"
    is_stacked = chart.kind in ("areaStacked", "areaPct")

    if is_pct:
        lo, hi = 0.0, 100.0
    elif is_stacked:
        pos_sums = [0.0] * n_cats
        for s in series:
            for ci in range(n_cats):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                if v > 0:
                    pos_sums[ci] += v
        lo, hi = 0.0, max(pos_sums) if pos_sums else 1.0
    else:
        all_vals = [v for s in series for v in s.vals]
        lo = min(0.0, min(all_vals) if all_vals else 0.0)
        hi = max(all_vals) if all_vals else 1.0

    sc = scale(lo, hi, chart.ax.get("v"), length=plot_rect.height(), label_sz=chart.fsz)
    min_v, max_v = sc["min"], sc["max"]
    val_range = max_v - min_v if max_v != min_v else 1.0

    slot_w = plot_rect.width() / max(1, n_cats - 1 if n_cats > 1 else 1)

    def cat_x(ci: int) -> float:
        if n_cats <= 1:
            return plot_rect.center().x()
        return plot_rect.left() + ci * slot_w

    def val_y(v: float) -> float:
        ratio = (v - min_v) / val_range
        return plot_rect.bottom() - ratio * plot_rect.height()

    baseline_y = val_y(0.0)

    if is_stacked:
        totals = [0.0] * n_cats
        if is_pct:
            for s in series:
                for ci in range(n_cats):
                    totals[ci] += abs(s.vals[ci] if ci < len(s.vals) else 0.0)
            totals = [t if t > 0 else 1.0 for t in totals]

        accum_y = [baseline_y] * n_cats
        for si, s in enumerate(series):
            col = get_series_color(s, si)
            fill_col = QColor(col)
            fill_col.setAlphaF(0.75)

            new_y: list[float] = []
            for ci in range(n_cats):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                val_norm = (v / totals[ci]) * 100.0 if is_pct else v
                h_px = (val_norm / val_range) * plot_rect.height()
                new_y.append(accum_y[ci] - h_px)

            # Build polygon between accum_y and new_y
            path = QPainterPath()
            path.moveTo(cat_x(0), accum_y[0])
            for ci in range(n_cats):
                path.lineTo(cat_x(ci), new_y[ci])
            for ci in reversed(range(n_cats)):
                path.lineTo(cat_x(ci), accum_y[ci])
            path.closeSubpath()

            painter.setPen(QPen(col, 1.0))
            painter.setBrush(QBrush(fill_col))
            painter.drawPath(path)

            accum_y = new_y
    else:
        for si, s in enumerate(series):
            col = get_series_color(s, si)
            fill_col = QColor(col)
            fill_col.setAlphaF(0.6)

            pts: list[QPointF] = []
            for ci in range(n_cats):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                pts.append(QPointF(cat_x(ci), val_y(v)))

            path = QPainterPath()
            path.moveTo(cat_x(0), baseline_y)
            for pt in pts:
                path.lineTo(pt)
            path.lineTo(cat_x(n_cats - 1), baseline_y)
            path.closeSubpath()

            painter.setPen(QPen(col, 1.5))
            painter.setBrush(QBrush(fill_col))
            painter.drawPath(path)
