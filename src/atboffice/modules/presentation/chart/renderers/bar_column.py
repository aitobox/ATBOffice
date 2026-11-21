"""Renderer for Column and Bar charts (Clustered, Stacked, 100% Stacked)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers.common import get_series_color
from atboffice.modules.presentation.chart.renderers.three_d import draw_box, is_deep
from atboffice.modules.presentation.chart.scale import format_val, scale


def _paint_bar(
    painter: QPainter,
    rect: QRectF,
    col: QColor,
    dep: tuple[float, float],
) -> None:
    """A flat bar, or a box when the chart is seen in 3-D."""
    if dep == (0.0, 0.0):
        painter.setPen(QPen(col.darker(110), 0.5))
        painter.setBrush(QBrush(col))
        painter.drawRect(rect)
    else:
        draw_box(painter, rect, col, dep[0], dep[1])


def _draw_order(n_cats: int, n_series: int, deep: bool) -> list[tuple[int, int]]:
    """(category, series) pairs in paint order; depth rows are painted from the back."""
    if deep:
        return [(ci, si) for si in reversed(range(n_series)) for ci in range(n_cats)]
    return [(ci, si) for ci in range(n_cats) for si in range(n_series)]


def draw_columns(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
    dep: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Render Clustered, Stacked, and 100% Stacked Column charts.

    ``dep`` is the 3-D depth offset; ``(0, 0)`` draws flat columns.
    """
    cats = chart.cats or [""]
    series = chart.series or []
    n_cats = len(cats)
    n_series = len(series)
    if n_cats == 0 or n_series == 0:
        return

    kind = chart.kind
    is_pct = kind == "colPct"
    is_stacked = kind in ("colStacked", "colPct")

    # Determine value bounds
    if is_pct:
        lo, hi = 0.0, 100.0
    elif is_stacked:
        pos_sums = [0.0] * n_cats
        neg_sums = [0.0] * n_cats
        for s in series:
            for ci in range(n_cats):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                if v >= 0:
                    pos_sums[ci] += v
                else:
                    neg_sums[ci] += v
        lo = min(0.0, min(neg_sums) if neg_sums else 0.0)
        hi = max(0.0, max(pos_sums) if pos_sums else 1.0)
    else:
        all_vals = [v for s in series for v in s.vals]
        lo = min(0.0, min(all_vals) if all_vals else 0.0)
        hi = max(0.0, max(all_vals) if all_vals else 1.0)

    sc = scale(lo, hi, chart.ax.get("v"), length=plot_rect.height(), label_sz=chart.fsz)
    min_v, max_v = sc["min"], sc["max"]
    val_range = max_v - min_v if max_v != min_v else 1.0

    def val_to_y(v: float) -> float:
        ratio = (v - min_v) / val_range
        return plot_rect.bottom() - ratio * plot_rect.height()

    y_zero = val_to_y(0.0)
    slot_w = plot_rect.width() / n_cats
    cat_pad = slot_w * 0.2
    avail_w = slot_w - cat_pad * 2

    if is_stacked:
        for ci in range(n_cats):
            cat_left = plot_rect.left() + ci * slot_w + cat_pad

            total = 0.0
            if is_pct:
                for s in series:
                    v = s.vals[ci] if ci < len(s.vals) else 0.0
                    total += abs(v)
                if total == 0.0:
                    total = 1.0

            cur_pos_y = y_zero
            cur_neg_y = y_zero

            for si, s in enumerate(series):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                col = get_series_color(s, si)

                if is_pct:
                    pct = (v / total) * 100.0 if total > 0 else 0.0
                    h_px = (abs(pct) / val_range) * plot_rect.height()
                    if v >= 0:
                        bar_rect = QRectF(cat_left, cur_pos_y - h_px, avail_w, h_px)
                        cur_pos_y -= h_px
                    else:
                        bar_rect = QRectF(cat_left, cur_neg_y, avail_w, h_px)
                        cur_neg_y += h_px
                else:
                    h_px = (abs(v) / val_range) * plot_rect.height()
                    if v >= 0:
                        bar_rect = QRectF(cat_left, cur_pos_y - h_px, avail_w, h_px)
                        cur_pos_y -= h_px
                    else:
                        bar_rect = QRectF(cat_left, cur_neg_y, avail_w, h_px)
                        cur_neg_y += h_px

                _paint_bar(painter, bar_rect, col, dep)
                if chart.labels and bar_rect.height() > 12:
                    lbl_text = f"{v:.1f}%" if is_pct else format_val(v)
                    painter.setPen(QPen(QColor("#FFFFFF")))
                    painter.drawText(bar_rect, int(Qt.AlignmentFlag.AlignCenter), lbl_text)
        return

    # Clustered: side by side, or one depth row per series for standard 3-D
    deep = dep != (0.0, 0.0) and is_deep(chart)
    bar_w = avail_w if deep else avail_w / n_series
    for ci, si in _draw_order(n_cats, n_series, deep):
        s = series[si]
        cat_left = plot_rect.left() + ci * slot_w + cat_pad
        v = s.vals[ci] if ci < len(s.vals) else 0.0
        col = get_series_color(s, si)

        bx = cat_left + (0.0 if deep else si * bar_w)
        y_val = val_to_y(v)
        by = min(y_val, y_zero)
        bh = abs(y_val - y_zero)
        bar_rect = QRectF(bx, by, bar_w, bh)
        if deep:
            row = si / n_series
            bar_rect.translate(dep[0] * row, dep[1] * row)
            depth = 0.75 / n_series
            _paint_bar(painter, bar_rect, col, (dep[0] * depth, dep[1] * depth))
        else:
            _paint_bar(painter, bar_rect, col, dep)

        if chart.labels:
            painter.setPen(QPen(QColor("#333333")))
            lbl_y = bar_rect.top() - 12 if v >= 0 else bar_rect.bottom() + 2
            painter.drawText(
                QRectF(bar_rect.left() - 10, lbl_y, bar_w + 20, 12),
                int(Qt.AlignmentFlag.AlignCenter),
                format_val(v),
            )


def draw_bars(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
    dep: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Render Clustered, Stacked, and 100% Stacked Bar (Horizontal) charts.

    ``dep`` is the 3-D depth offset; ``(0, 0)`` draws flat bars.
    """
    cats = chart.cats or [""]
    series = chart.series or []
    n_cats = len(cats)
    n_series = len(series)
    if n_cats == 0 or n_series == 0:
        return

    kind = chart.kind
    is_pct = kind == "barPct"
    is_stacked = kind in ("barStacked", "barPct")

    if is_pct:
        lo, hi = 0.0, 100.0
    elif is_stacked:
        pos_sums = [0.0] * n_cats
        neg_sums = [0.0] * n_cats
        for s in series:
            for ci in range(n_cats):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                if v >= 0:
                    pos_sums[ci] += v
                else:
                    neg_sums[ci] += v
        lo = min(0.0, min(neg_sums) if neg_sums else 0.0)
        hi = max(0.0, max(pos_sums) if pos_sums else 1.0)
    else:
        all_vals = [v for s in series for v in s.vals]
        lo = min(0.0, min(all_vals) if all_vals else 0.0)
        hi = max(0.0, max(all_vals) if all_vals else 1.0)

    sc = scale(lo, hi, chart.ax.get("v"), length=plot_rect.width(), label_sz=chart.fsz)
    min_v, max_v = sc["min"], sc["max"]
    val_range = max_v - min_v if max_v != min_v else 1.0

    def val_to_x(v: float) -> float:
        ratio = (v - min_v) / val_range
        return plot_rect.left() + ratio * plot_rect.width()

    x_zero = val_to_x(0.0)
    slot_h = plot_rect.height() / n_cats
    cat_pad = slot_h * 0.2
    avail_h = slot_h - cat_pad * 2

    # Bottom categories first: in 3-D a lower bar's top face sits behind the bar above it
    if is_stacked:
        for ci in reversed(range(n_cats)):
            cat_top = plot_rect.top() + ci * slot_h + cat_pad

            total = 0.0
            if is_pct:
                for s in series:
                    v = s.vals[ci] if ci < len(s.vals) else 0.0
                    total += abs(v)
                if total == 0.0:
                    total = 1.0

            cur_pos_x = x_zero
            cur_neg_x = x_zero

            for si, s in enumerate(series):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                col = get_series_color(s, si)

                if is_pct:
                    pct = (v / total) * 100.0 if total > 0 else 0.0
                    w_px = (abs(pct) / val_range) * plot_rect.width()
                    if v >= 0:
                        bar_rect = QRectF(cur_pos_x, cat_top, w_px, avail_h)
                        cur_pos_x += w_px
                    else:
                        bar_rect = QRectF(cur_neg_x - w_px, cat_top, w_px, avail_h)
                        cur_neg_x -= w_px
                else:
                    w_px = (abs(v) / val_range) * plot_rect.width()
                    if v >= 0:
                        bar_rect = QRectF(cur_pos_x, cat_top, w_px, avail_h)
                        cur_pos_x += w_px
                    else:
                        bar_rect = QRectF(cur_neg_x - w_px, cat_top, w_px, avail_h)
                        cur_neg_x -= w_px

                _paint_bar(painter, bar_rect, col, dep)
        return

    deep = dep != (0.0, 0.0) and is_deep(chart)
    bar_h = avail_h if deep else avail_h / n_series
    for ci, si in _draw_order(n_cats, n_series, deep):
        ci = n_cats - 1 - ci
        s = series[si]
        cat_top = plot_rect.top() + ci * slot_h + cat_pad
        v = s.vals[ci] if ci < len(s.vals) else 0.0
        col = get_series_color(s, si)

        by = cat_top + (0.0 if deep else si * bar_h)
        x_val = val_to_x(v)
        bx = min(x_val, x_zero)
        bw = abs(x_val - x_zero)
        bar_rect = QRectF(bx, by, bw, bar_h)
        if deep:
            row = si / n_series
            bar_rect.translate(dep[0] * row, dep[1] * row)
            depth = 0.75 / n_series
            _paint_bar(painter, bar_rect, col, (dep[0] * depth, dep[1] * depth))
        else:
            _paint_bar(painter, bar_rect, col, dep)
