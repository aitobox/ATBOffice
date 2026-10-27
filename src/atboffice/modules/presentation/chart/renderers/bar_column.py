"""Renderer for Column and Bar charts (Clustered, Stacked, 100% Stacked)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers.common import get_series_color
from atboffice.modules.presentation.chart.scale import format_val, scale


def draw_columns(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Clustered, Stacked, and 100% Stacked Column charts."""
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
        lo = min(all_vals) if all_vals else 0.0
        hi = max(all_vals) if all_vals else 1.0

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

    for ci in range(n_cats):
        cat_left = plot_rect.left() + ci * slot_w + cat_pad

        if is_stacked:
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
                painter.setPen(QPen(col.darker(110), 0.5))
                painter.setBrush(QBrush(col))

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

                painter.drawRect(bar_rect)
                if chart.labels and bar_rect.height() > 12:
                    lbl_text = f"{v:.1f}%" if is_pct else format_val(v)
                    painter.setPen(QPen(QColor("#FFFFFF")))
                    painter.drawText(bar_rect, int(Qt.AlignmentFlag.AlignCenter), lbl_text)
        else:
            bar_w = avail_w / n_series
            for si, s in enumerate(series):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                col = get_series_color(s, si)
                painter.setPen(QPen(col.darker(110), 0.5))
                painter.setBrush(QBrush(col))

                bx = cat_left + si * bar_w
                y_val = val_to_y(v)
                by = min(y_val, y_zero)
                bh = abs(y_val - y_zero)
                bar_rect = QRectF(bx, by, bar_w, bh)
                painter.drawRect(bar_rect)

                if chart.labels:
                    painter.setPen(QPen(QColor("#333333")))
                    lbl_y = by - 12 if v >= 0 else by + bh + 2
                    painter.drawText(
                        QRectF(bx - 10, lbl_y, bar_w + 20, 12),
                        int(Qt.AlignmentFlag.AlignCenter),
                        format_val(v),
                    )


def draw_bars(
    painter: QPainter,
    chart: ChartData,
    plot_rect: QRectF,
) -> None:
    """Render Clustered, Stacked, and 100% Stacked Bar (Horizontal) charts."""
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
        lo = min(all_vals) if all_vals else 0.0
        hi = max(all_vals) if all_vals else 1.0

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

    for ci in range(n_cats):
        cat_top = plot_rect.top() + ci * slot_h + cat_pad

        if is_stacked:
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
                painter.setPen(QPen(col.darker(110), 0.5))
                painter.setBrush(QBrush(col))

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

                painter.drawRect(bar_rect)
        else:
            bar_h = avail_h / n_series
            for si, s in enumerate(series):
                v = s.vals[ci] if ci < len(s.vals) else 0.0
                col = get_series_color(s, si)
                painter.setPen(QPen(col.darker(110), 0.5))
                painter.setBrush(QBrush(col))

                by = cat_top + si * bar_h
                x_val = val_to_x(v)
                bx = min(x_val, x_zero)
                bw = abs(x_val - x_zero)
                bar_rect = QRectF(bx, by, bw, bar_h)
                painter.drawRect(bar_rect)
