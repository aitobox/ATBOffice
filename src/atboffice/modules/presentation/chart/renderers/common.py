"""Common rendering helpers, markers, legends, and color resolution for DrawingML charts."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)

from atboffice.modules.presentation.chart.model import CH_PALETTE, SeriesData

THEME_COLOR_MAP = {
    "accent1": "#4472C4",
    "accent2": "#ED7D31",
    "accent3": "#A5A5A5",
    "accent4": "#FFC000",
    "accent5": "#5B9BD5",
    "accent6": "#70AD47",
    "tx1": "#000000",
    "tx2": "#595959",
    "bg1": "#FFFFFF",
    "bg2": "#F2F2F2",
    "white": "#FFFFFF",
    "black": "#000000",
}


def resolve_color(color_spec: Any, default: str = "#4472C4") -> QColor:
    """Resolve a theme color name, dict, or hex string into a QColor."""
    if not color_spec:
        return QColor(default)
    if isinstance(color_spec, dict):
        c = color_spec.get("c") or default
        alpha = float(color_spec.get("a", 1.0))
        col = resolve_color(c, default)
        col.setAlphaF(max(0.0, min(1.0, alpha)))
        return col

    s = str(color_spec).strip()
    if s.lower() in THEME_COLOR_MAP:
        return QColor(THEME_COLOR_MAP[s.lower()])
    if s.startswith("#") or s.startswith("rgb"):
        return QColor(s)
    return QColor(default)


def get_series_color(series: SeriesData, index: int) -> QColor:
    """Get color for series, falling back to CH_PALETTE."""
    if series.color:
        return resolve_color(series.color)
    if series.fill and series.fill.get("c"):
        return resolve_color(series.fill["c"])
    return QColor(CH_PALETTE[index % len(CH_PALETTE)])


def draw_marker(
    painter: QPainter,
    sym: str,
    x: float,
    y: float,
    size: float,
    fill_col: QColor,
    stroke_col: QColor | None = None,
) -> None:
    """Render DrawingML series marker symbol."""
    if sym == "none" or size <= 0:
        return
    r = size / 2.0
    pen = QPen(stroke_col or fill_col.darker(120), 1.0)
    brush = QBrush(fill_col)
    painter.setPen(pen)
    painter.setBrush(brush)

    if sym == "circle":
        painter.drawEllipse(QPointF(x, y), r, r)
    elif sym == "diamond":
        path = QPainterPath()
        path.moveTo(x, y - r)
        path.lineTo(x + r, y)
        path.lineTo(x, y + r)
        path.lineTo(x - r, y)
        path.closeSubpath()
        painter.drawPath(path)
    elif sym == "triangle":
        path = QPainterPath()
        path.moveTo(x, y - r)
        path.lineTo(x + r, y + r)
        path.lineTo(x - r, y + r)
        path.closeSubpath()
        painter.drawPath(path)
    elif sym == "x":
        painter.drawLine(QPointF(x - r, y - r), QPointF(x + r, y + r))
        painter.drawLine(QPointF(x + r, y - r), QPointF(x - r, y + r))
    elif sym == "plus":
        painter.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        painter.drawLine(QPointF(x, y - r), QPointF(x, y + r))
    elif sym == "star":
        painter.drawLine(QPointF(x - r, y - r), QPointF(x + r, y + r))
        painter.drawLine(QPointF(x + r, y - r), QPointF(x - r, y + r))
        painter.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        painter.drawLine(QPointF(x, y - r), QPointF(x, y + r))
    else:  # "square" default
        painter.drawRect(QRectF(x - r, y - r, size, size))


def wrap_text(text: str, font: QFont, max_width: float) -> list[str]:
    """Wrap multiline string to fit within max_width."""
    if not text:
        return []
    try:
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            char_w = (font.pointSizeF() * 0.6) if font else 7.0
            max_chars = max(1, int(max_width / char_w))
            fallback_lines: list[str] = []
            for p in text.split("\n"):
                while len(p) > max_chars:
                    fallback_lines.append(p[:max_chars])
                    p = p[max_chars:]
                fallback_lines.append(p)
            return fallback_lines

        fm = QFontMetricsF(font)
        lines: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            cur_line = ""
            for word in words:
                candidate = f"{cur_line} {word}".strip() if cur_line else word
                if fm.horizontalAdvance(candidate) <= max_width or not cur_line:
                    cur_line = candidate
                else:
                    lines.append(cur_line)
                    cur_line = word
            if cur_line:
                lines.append(cur_line)
        return lines
    except Exception:
        return text.split("\n")


def draw_legend(
    painter: QPainter,
    items: list[tuple[str, QColor]],
    legend_pos: str,
    chart_rect: QRectF,
    font_size: float = 9.0,
) -> QRectF:
    """Draw chart legend and return the remaining area for the plot.

    legend_pos: 'r' (Right), 'b' (Bottom), 't' (Top), 'l' (Left), 'none'.
    """
    if legend_pos == "none" or not items:
        return chart_rect

    font = QFont("sans-serif")
    font.setPointSizeF(font_size)
    painter.setFont(font)
    fm = QFontMetricsF(font)

    pad = 8.0
    sw_size = 10.0
    gap = 4.0
    item_spacing = 12.0

    rem_rect = QRectF(chart_rect)

    if legend_pos in ("r", "l"):
        max_item_w = 0.0
        for name, _ in items:
            max_item_w = max(max_item_w, sw_size + gap + fm.horizontalAdvance(name))
        leg_w = min(max_item_w + pad * 2, chart_rect.width() * 0.35)

        if legend_pos == "r":
            leg_rect = QRectF(
                chart_rect.right() - leg_w,
                chart_rect.top(),
                leg_w,
                chart_rect.height(),
            )
            rem_rect.setRight(chart_rect.right() - leg_w - pad)
        else:
            leg_rect = QRectF(
                chart_rect.left(),
                chart_rect.top(),
                leg_w,
                chart_rect.height(),
            )
            rem_rect.setLeft(chart_rect.left() + leg_w + pad)

        # Draw vertical items centered vertically
        total_h = len(items) * (sw_size + gap) + (len(items) - 1) * gap
        cur_y = max(leg_rect.top() + pad, leg_rect.center().y() - total_h / 2.0)
        x0 = leg_rect.left() + pad

        for name, col in items:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawRect(QRectF(x0, cur_y, sw_size, sw_size))

            painter.setPen(QPen(QColor("#333333")))
            text_rect = QRectF(
                x0 + sw_size + gap,
                cur_y - 1,
                leg_rect.width() - pad * 2 - sw_size - gap,
                sw_size + 4,
            )
            align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            painter.drawText(text_rect, align, name)
            cur_y += sw_size + gap * 2

    elif legend_pos in ("b", "t"):
        line_h = sw_size + gap
        leg_h = line_h + pad * 2

        if legend_pos == "b":
            leg_rect = QRectF(
                chart_rect.left(),
                chart_rect.bottom() - leg_h,
                chart_rect.width(),
                leg_h,
            )
            rem_rect.setBottom(chart_rect.bottom() - leg_h - pad)
        else:
            leg_rect = QRectF(chart_rect.left(), chart_rect.top(), chart_rect.width(), leg_h)
            rem_rect.setTop(chart_rect.top() + leg_h + pad)

        # Measure horizontal layout
        item_widths = [sw_size + gap + fm.horizontalAdvance(name) for name, _ in items]
        total_w = sum(item_widths) + max(0, len(items) - 1) * item_spacing
        cur_x = max(leg_rect.left() + pad, leg_rect.center().x() - total_w / 2.0)
        cur_y = leg_rect.center().y() - sw_size / 2.0

        for (name, col), iw in zip(items, item_widths, strict=False):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawRect(QRectF(cur_x, cur_y, sw_size, sw_size))

            painter.setPen(QPen(QColor("#333333")))
            text_rect = QRectF(
                cur_x + sw_size + gap,
                cur_y - 2,
                iw - sw_size - gap,
                sw_size + 4,
            )
            align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            painter.drawText(text_rect, align, name)
            cur_x += iw + item_spacing

    return rem_rect
