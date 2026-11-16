"""Conditional-formatting icon-set catalogue and QPainter drawing.

Ported from ``ledger/js/render.js`` (icon sets section). Each icon set maps
to a list of ``(kind, arg, color)`` entries, ordered from the lowest band
(index 0) to the highest band.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF

_RED, _AMBER, _GREEN, _GREY = "#C00000", "#E6B200", "#00A050", "#808080"
_BLUE, _DARK, _LIGHT = "#1F5DA8", "#404040", "#C9C9C9"

ICON_SETS: dict[str, list[tuple[str, Any, str]]] = {
    "3Arrows": [("arrow", "down", _RED), ("arrow", "side", _AMBER), ("arrow", "up", _GREEN)],
    "3ArrowsGray": [("arrow", "down", _GREY), ("arrow", "side", _GREY), ("arrow", "up", _GREY)],
    "3Flags": [("flag", 0, _RED), ("flag", 0, _AMBER), ("flag", 0, _GREEN)],
    "3TrafficLights1": [("dot", 0, _RED), ("dot", 0, _AMBER), ("dot", 0, _GREEN)],
    "3TrafficLights2": [("light", 0, _RED), ("light", 0, _AMBER), ("light", 0, _GREEN)],
    "3Signs": [("diamond", 0, _RED), ("tri", 0, _AMBER), ("dot", 0, _GREEN)],
    "3Symbols": [("xmark", 0, _RED), ("excl", 0, _AMBER), ("check", 0, _GREEN)],
    "3Symbols2": [("xmark", 1, _RED), ("excl", 1, _AMBER), ("check", 1, _GREEN)],
    "3Stars": [("star", 0, _LIGHT), ("star", 0.5, _AMBER), ("star", 1, _AMBER)],
    "3Triangles": [("tri", "down", _RED), ("dash", 0, _AMBER), ("tri", "up", _GREEN)],
    "4Arrows": [
        ("arrow", "down", _RED),
        ("arrow", "downside", _AMBER),
        ("arrow", "upside", _AMBER),
        ("arrow", "up", _GREEN),
    ],
    "4ArrowsGray": [
        ("arrow", "down", _GREY),
        ("arrow", "downside", _GREY),
        ("arrow", "upside", _GREY),
        ("arrow", "up", _GREY),
    ],
    "4RedToBlack": [("dot", 0, _DARK), ("dot", 0, _GREY), ("dot", 0, "#E08080"), ("dot", 0, _RED)],
    "4Rating": [("bars", 1, _BLUE), ("bars", 2, _BLUE), ("bars", 3, _BLUE), ("bars", 4, _BLUE)],
    "4TrafficLights": [("dot", 0, _DARK), ("dot", 0, _RED), ("dot", 0, _AMBER), ("dot", 0, _GREEN)],
    "5Arrows": [
        ("arrow", "down", _RED),
        ("arrow", "downside", _AMBER),
        ("arrow", "side", _AMBER),
        ("arrow", "upside", _AMBER),
        ("arrow", "up", _GREEN),
    ],
    "5ArrowsGray": [
        ("arrow", "down", _GREY),
        ("arrow", "downside", _GREY),
        ("arrow", "side", _GREY),
        ("arrow", "upside", _GREY),
        ("arrow", "up", _GREY),
    ],
    "5Rating": [("bars", k, _BLUE) for k in range(5)],
    "5Quarters": [("quarter", k, _DARK) for k in range(5)],
    "3Smilies": [("face", -1, _RED), ("face", 0, _AMBER), ("face", 1, _GREEN)],
    "5Boxes": [("boxes", k, _BLUE) for k in range(5)],
}

_ARROW_ANGLE = {"up": -90.0, "upside": -45.0, "side": 0.0, "downside": 45.0, "down": 90.0}


def icon_spec(set_name: str, index: int) -> tuple[str, Any, str] | None:
    """Return ``(kind, arg, color)`` for an icon, or None for ``NoIcons``."""
    if set_name == "NoIcons":
        return None
    icons = ICON_SETS.get(set_name) or ICON_SETS["3TrafficLights1"]
    if 0 <= index < len(icons):
        return icons[index]
    return ("dot", 0, _GREY)


def icon_size(row_h: int, zoom: float = 1.0) -> int:
    """Icon edge length for a cell of height ``row_h`` (render.js: min(16*z, h-2))."""
    return max(0, min(round(16 * zoom), row_h - 2))


def draw_icon(painter: QPainter, set_name: str, index: int, x: float, y: float, s: float) -> None:
    """Draw icon ``index`` of ``set_name`` into the square (x, y, s, s)."""
    spec = icon_spec(set_name, index)
    if spec is None or s <= 2:
        return
    kind, arg, col_hex = spec
    col = QColor(col_hex)
    cx, cy, r = x + s / 2.0, y + s / 2.0, s / 2.0 - 1.0
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(col))

    def circle(rad: float = r) -> None:
        painter.drawEllipse(QPointF(cx, cy), rad, rad)

    def poly(points: list[tuple[float, float]]) -> None:
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in points]))

    if kind == "arrow":
        painter.translate(cx, cy)
        painter.rotate(_ARROW_ANGLE.get(str(arg), 0.0))
        poly(
            [
                (r, 0),
                (0, -r),
                (0, -r * 0.4),
                (-r, -r * 0.4),
                (-r, r * 0.4),
                (0, r * 0.4),
                (0, r),
            ]
        )
    elif kind in ("dot", "light"):
        if kind == "light":
            painter.setPen(QPen(QColor("#333333"), 1))
        circle()
    elif kind == "diamond":
        poly([(cx, y + 1), (x + s - 1, cy), (cx, y + s - 1), (x + 1, cy)])
    elif kind == "tri":
        if arg == "down":
            poly([(x + 1, y + 3), (x + s - 1, y + 3), (cx, y + s - 2)])
        else:
            poly([(cx, y + 2), (x + s - 1, y + s - 3), (x + 1, y + s - 3)])
    elif kind == "dash":
        painter.drawRect(QRectF(x + 2, cy - s / 8, s - 4, s / 4))
    elif kind == "flag":
        painter.drawRect(QRectF(x + 2, y + 1, 1.5, s - 2))
        poly([(x + 3.5, y + 1), (x + s - 1, y + s / 4 + 1), (x + 3.5, y + s / 2 + 1)])
    elif kind in ("xmark", "excl", "check"):
        stroke_col = col
        if not arg:
            circle()
            stroke_col = QColor("#FFFFFF")
        pen = QPen(stroke_col, max(1.5, s / 7))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        if kind == "xmark":
            path.moveTo(cx - r / 2, cy - r / 2)
            path.lineTo(cx + r / 2, cy + r / 2)
            path.moveTo(cx + r / 2, cy - r / 2)
            path.lineTo(cx - r / 2, cy + r / 2)
        elif kind == "excl":
            path.moveTo(cx, cy - r / 2)
            path.lineTo(cx, cy + r / 6)
            path.moveTo(cx, cy + r / 2.2)
            path.lineTo(cx, cy + r / 1.8)
        else:
            path.moveTo(cx - r / 2, cy)
            path.lineTo(cx - r / 8, cy + r / 2.5)
            path.lineTo(cx + r / 2, cy - r / 2.5)
        painter.drawPath(path)
    elif kind == "star":
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r * 0.45 if k % 2 else r
            pts.append(QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a)))
        star = QPolygonF(pts)
        painter.setPen(QPen(QColor("#B08A00"), 1))
        if arg == 1:
            painter.drawPolygon(star)
        else:
            if arg == 0.5:
                clip = QPainterPath()
                clip.addPolygon(star)
                painter.save()
                painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
                painter.fillRect(QRectF(x, y, s / 2, s), col)
                painter.restore()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(star)
    elif kind == "bars":
        for k in range(4):
            hh = (s - 2) * (k + 1) / 4
            painter.setBrush(QBrush(col if k < arg else QColor(_LIGHT)))
            painter.drawRect(QRectF(x + 1 + k * (s / 4), y + s - 1 - hh, s / 4 - 1, hh))
    elif kind == "boxes":
        for k in range(4):
            painter.setBrush(QBrush(col if k < arg else QColor(_LIGHT)))
            painter.drawRect(
                QRectF(x + 1 + (k % 2) * (s / 2), y + 1 + (k // 2) * (s / 2), s / 2 - 2, s / 2 - 2)
            )
    elif kind == "quarter":
        painter.setPen(QPen(col, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        circle()
        if arg:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            # Qt angles: 1/16 degree, counter-clockwise from 3 o'clock.
            painter.drawPie(QRectF(cx - r, cy - r, 2 * r, 2 * r), 90 * 16, -int(90 * arg) * 16)
    elif kind == "face":
        circle()
        painter.setBrush(QBrush(QColor("#000000")))
        painter.drawRect(QRectF(cx - r / 2.5, cy - r / 3, 1.5, 1.5))
        painter.drawRect(QRectF(cx + r / 3.5, cy - r / 3, 1.5, 1.5))
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if arg > 0:
            painter.drawArc(QRectF(cx - r / 2, cy - r / 2, r, r), -36 * 16, -108 * 16)
        elif arg < 0:
            painter.drawArc(QRectF(cx - r / 2, cy + r / 1.4 - r / 2, r, r), 36 * 16, 108 * 16)
        else:
            painter.drawLine(QPointF(cx - r / 2.5, cy + r / 3), QPointF(cx + r / 2.5, cy + r / 3))
    else:
        circle()
    painter.restore()
