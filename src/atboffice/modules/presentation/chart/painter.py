"""Orchestrating ChartPainter coordinating title, legend, axes, and type renderers."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPen,
)

from atboffice.modules.presentation.chart.model import ChartData
from atboffice.modules.presentation.chart.renderers import (
    draw_areas,
    draw_bars,
    draw_columns,
    draw_legend,
    draw_lines,
    draw_pie_doughnut,
    draw_radar,
    draw_scatter_bubble,
    get_series_color,
    resolve_color,
    wrap_text,
)
from atboffice.modules.presentation.chart.renderers.three_d import (
    depth_grid_segments,
    depth_offset,
    draw_walls,
    is_3d_bar,
    shrink_for_depth,
)
from atboffice.modules.presentation.chart.scale import format_val, scale


class ChartPainter:
    """Renders 17 DrawingML chart types into any QPainter device."""

    @classmethod
    def paint_chart(
        cls,
        painter: QPainter,
        chart: ChartData,
        bounds: QRectF,
    ) -> None:
        """Main entry point to paint a DrawingML chart inside bounds."""
        if bounds.width() < 20 or bounds.height() < 20:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Background & Border
        if chart.bg:
            bg_col = resolve_color(chart.bg, "#FFFFFF")
            painter.setBrush(QBrush(bg_col))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        if chart.border and chart.border.get("t") != "none":
            border_col = resolve_color(chart.border.get("c"), "#D9D9D9")
            painter.setPen(QPen(border_col, 1.0))
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawRect(bounds)

        # 2. Inset padding
        pad = max(6.0, min(bounds.width(), bounds.height()) * 0.04)
        rem_rect = bounds.adjusted(pad, pad, -pad, -pad)

        # 3. Title
        base_fsz = max(1.0, float(chart.fsz) if chart.fsz else 10.0)
        if chart.title:
            title_font = QFont("sans-serif")
            raw_title_sz = chart.title_tx.get("sz", base_fsz * 1.2)
            try:
                title_sz = max(1.0, float(raw_title_sz))
            except (ValueError, TypeError):
                title_sz = max(1.0, base_fsz * 1.2)
            title_font.setPointSizeF(title_sz)
            title_font.setBold(bool(chart.title_tx.get("b", True)))
            painter.setFont(title_font)

            fm = QFontMetricsF(title_font)
            lines = wrap_text(str(chart.title), title_font, rem_rect.width() * 0.9)
            th = len(lines) * fm.lineSpacing()

            title_color = resolve_color(chart.title_tx.get("color"), "#333333")
            painter.setPen(QPen(title_color))

            title_rect = QRectF(rem_rect.left(), rem_rect.top(), rem_rect.width(), th)
            painter.drawText(title_rect, int(Qt.AlignmentFlag.AlignCenter), "\n".join(lines))

            rem_rect.setTop(rem_rect.top() + th + 6.0)

        # 4. Legend items
        legend_items: list[tuple[str, QColor]] = []
        cats = [str(c) if c is not None else "" for c in (chart.cats or [])]
        if chart.kind in ("pie", "doughnut"):
            # Slices are the categories
            for ci, cat in enumerate(cats):
                if chart.pie_colors and ci < len(chart.pie_colors):
                    col = resolve_color(chart.pie_colors[ci])
                else:
                    col = resolve_color(None, "#4472C4")
                legend_items.append((cat, col))
        else:
            for si, s in enumerate(chart.series):
                s_name = str(s.name) if s.name is not None else f"Series {si+1}"
                legend_items.append((s_name, get_series_color(s, si)))

        plot_area = draw_legend(
            painter,
            legend_items,
            chart.legend,
            rem_rect,
            font_size=max(8.0, base_fsz * 0.9),
        )

        # 5. Gridlines & Axes for Cartesian types
        kind = chart.kind
        cartesian_col_line = (
            "col",
            "colStacked",
            "colPct",
            "line",
            "lineMarkers",
            "area",
            "areaStacked",
            "areaPct",
        )
        dep = (0.0, 0.0)
        if kind in cartesian_col_line:
            plot_rect, dep = cls._draw_cartesian_axes_and_grid(
                painter, chart, plot_area, is_bar=False
            )
        elif kind in ("bar", "barStacked", "barPct"):
            plot_rect, dep = cls._draw_cartesian_axes_and_grid(
                painter, chart, plot_area, is_bar=True
            )
        elif kind in ("scatter", "bubble"):
            plot_rect = cls._draw_xy_axes_and_grid(painter, chart, plot_area)
        else:
            plot_rect = plot_area

        # 6. Dispatch Plot Rendering
        if kind in ("col", "colStacked", "colPct"):
            draw_columns(painter, chart, plot_rect, dep)
        elif kind in ("bar", "barStacked", "barPct"):
            draw_bars(painter, chart, plot_rect, dep)
        elif kind in ("line", "lineMarkers"):
            draw_lines(painter, chart, plot_rect)
        elif kind in ("area", "areaStacked", "areaPct"):
            draw_areas(painter, chart, plot_rect)
        elif kind in ("pie", "doughnut"):
            draw_pie_doughnut(painter, chart, plot_rect)
        elif kind in ("scatter", "bubble"):
            draw_scatter_bubble(painter, chart, plot_rect)
        elif kind in ("radar", "radarFilled"):
            draw_radar(painter, chart, plot_rect)

        painter.restore()

    @classmethod
    def _draw_cartesian_axes_and_grid(
        cls,
        painter: QPainter,
        chart: ChartData,
        area: QRectF,
        is_bar: bool = False,
    ) -> tuple[QRectF, tuple[float, float]]:
        """Draw axes, tick marks, gridlines, and labels for Column/Line/Area and Bar charts.

        Returns the front plot rectangle and the 3-D depth offset ``(dx, dy)``,
        which is ``(0, 0)`` for flat charts.
        """
        font = QFont("sans-serif")
        font.setPointSizeF(max(7.0, chart.fsz * 0.85))
        painter.setFont(font)
        fm = QFontMetricsF(font)

        # Determine value range
        series = chart.series or []
        is_pct = chart.kind in ("colPct", "barPct", "areaPct")
        if is_pct:
            lo, hi = 0.0, 100.0
        elif chart.kind in ("colStacked", "barStacked", "areaStacked"):
            n_cats = len(chart.cats or [""])
            sums = [0.0] * n_cats
            for s in series:
                for ci in range(n_cats):
                    if ci < len(s.vals):
                        sums[ci] += s.vals[ci]
            lo, hi = 0.0, max(sums) if sums else 1.0
        else:
            all_vals = [v for s in series for v in s.vals]
            lo = min(0.0, min(all_vals) if all_vals else 0.0)
            hi = max(all_vals) if all_vals else 1.0

        if is_bar:
            cats = [str(c) if c is not None else "" for c in (chart.cats or [])]
            sc = scale(lo, hi, chart.ax.get("v"), length=area.width(), label_sz=chart.fsz)
            # Left margin for category names
            max_cat_w = max([fm.horizontalAdvance(c) for c in cats] + [20.0])
            left_margin = min(max_cat_w + 8.0, area.width() * 0.35)
            bottom_margin = fm.height() + 8.0

            plot_rect = QRectF(
                area.left() + left_margin,
                area.top(),
                area.width() - left_margin,
                area.height() - bottom_margin,
            )
            plot_rect, dep = cls._fit_depth(chart, plot_rect, horizontal=True)

            # Draw value gridlines & ticks on bottom
            ticks = sc["ticks"]
            min_v, max_v = sc["min"], sc["max"]
            v_range = max_v - min_v if max_v != min_v else 1.0
            if dep != (0.0, 0.0):
                xs = [
                    plot_rect.left() + (t - min_v) / v_range * plot_rect.width() for t in ticks
                ]
                cls._draw_depth_grid(painter, chart, plot_rect, dep, xs, horizontal=True)

            for tick in ticks:
                ratio = (tick - min_v) / v_range
                x = plot_rect.left() + ratio * plot_rect.width()
                if chart.grid_y and dep == (0.0, 0.0):
                    painter.setPen(QPen(QColor("#E5E5E5"), 0.75))
                    painter.drawLine(QPointF(x, plot_rect.top()), QPointF(x, plot_rect.bottom()))

                painter.setPen(QPen(QColor("#555555")))
                tick_str = f"{tick:.0f}%" if is_pct else format_val(tick)
                painter.drawText(
                    QRectF(x - 20, plot_rect.bottom() + 2, 40, bottom_margin),
                    int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                    tick_str,
                )

            # Draw category labels on left
            slot_h = plot_rect.height() / max(1, len(cats))
            for ci, cat in enumerate(cats):
                cy = plot_rect.top() + ci * slot_h
                painter.setPen(QPen(QColor("#333333")))
                painter.drawText(
                    QRectF(area.left(), cy, left_margin - 4, slot_h),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                    cat,
                )

            # Axis lines
            painter.setPen(QPen(QColor("#868686"), 1.0))
            painter.drawLine(plot_rect.topLeft(), plot_rect.bottomLeft())
            painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
            return plot_rect, dep
        else:
            sc = scale(lo, hi, chart.ax.get("v"), length=area.height(), label_sz=chart.fsz)
            ticks = sc["ticks"]
            # Measure left value label width
            max_lbl_w = max([fm.horizontalAdvance(format_val(t)) for t in ticks] + [24.0])
            left_margin = max_lbl_w + 6.0
            bottom_margin = fm.height() + 8.0

            plot_rect = QRectF(
                area.left() + left_margin,
                area.top(),
                area.width() - left_margin,
                area.height() - bottom_margin,
            )
            plot_rect, dep = cls._fit_depth(chart, plot_rect, horizontal=False)

            # Draw horizontal gridlines & value labels
            min_v, max_v = sc["min"], sc["max"]
            v_range = max_v - min_v if max_v != min_v else 1.0
            if dep != (0.0, 0.0):
                ys = [
                    plot_rect.bottom() - (t - min_v) / v_range * plot_rect.height()
                    for t in ticks
                ]
                cls._draw_depth_grid(painter, chart, plot_rect, dep, ys, horizontal=False)

            for tick in ticks:
                ratio = (tick - min_v) / v_range
                y = plot_rect.bottom() - ratio * plot_rect.height()
                if chart.grid_y and dep == (0.0, 0.0):
                    painter.setPen(QPen(QColor("#E5E5E5"), 0.75))
                    painter.drawLine(QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y))

                painter.setPen(QPen(QColor("#555555")))
                tick_str = f"{tick:.0f}%" if is_pct else format_val(tick)
                painter.drawText(
                    QRectF(area.left(), y - fm.height() / 2.0, left_margin - 4, fm.height()),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                    tick_str,
                )

            # Draw category labels along bottom
            n_cats = len(chart.cats or [""])
            slot_w = plot_rect.width() / max(1, n_cats)
            for ci, cat in enumerate(chart.cats):
                cx = plot_rect.left() + ci * slot_w
                painter.setPen(QPen(QColor("#333333")))
                painter.drawText(
                    QRectF(cx, plot_rect.bottom() + 3, slot_w, bottom_margin),
                    int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                    cat,
                )

            # Axis lines
            painter.setPen(QPen(QColor("#868686"), 1.0))
            painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
            painter.drawLine(plot_rect.topLeft(), plot_rect.bottomLeft())
            return plot_rect, dep

    @classmethod
    def _fit_depth(
        cls,
        chart: ChartData,
        plot_rect: QRectF,
        horizontal: bool,
    ) -> tuple[QRectF, tuple[float, float]]:
        """Shrink the plot box to leave room for the depth of a 3-D bar chart."""
        if not is_3d_bar(chart) or chart.view3d is None:
            return plot_rect, (0.0, 0.0)
        dep = depth_offset(
            chart.view3d,
            plot_rect,
            len(chart.cats or [""]),
            len(chart.series or []),
            horizontal,
        )
        return shrink_for_depth(plot_rect, *dep), dep

    @classmethod
    def _draw_depth_grid(
        cls,
        painter: QPainter,
        chart: ChartData,
        plot_rect: QRectF,
        dep: tuple[float, float],
        positions: list[float],
        horizontal: bool,
    ) -> None:
        """Walls and floor of a 3-D plot with the value gridlines on its walls."""
        draw_walls(painter, plot_rect, dep[0], dep[1], horizontal)
        if not chart.grid_y:
            return
        painter.setPen(QPen(QColor("#D9D9D9"), 0.75))
        for p1, p2 in depth_grid_segments(plot_rect, dep[0], dep[1], positions, horizontal):
            painter.drawLine(p1, p2)

    @classmethod
    def _draw_xy_axes_and_grid(
        cls,
        painter: QPainter,
        chart: ChartData,
        area: QRectF,
    ) -> QRectF:
        """Draw Cartesian grid and numeric labels for X and Y axes."""
        font = QFont("sans-serif")
        font.setPointSizeF(max(7.0, chart.fsz * 0.85))
        painter.setFont(font)
        fm = QFontMetricsF(font)

        left_margin = 32.0
        bottom_margin = fm.height() + 8.0

        plot_rect = QRectF(
            area.left() + left_margin,
            area.top(),
            area.width() - left_margin,
            area.height() - bottom_margin,
        )

        painter.setPen(QPen(QColor("#868686"), 1.0))
        painter.drawLine(plot_rect.topLeft(), plot_rect.bottomLeft())
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
        return plot_rect
