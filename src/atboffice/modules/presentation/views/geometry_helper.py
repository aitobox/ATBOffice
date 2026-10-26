"""Geometry path and adjustment handle helpers for Lectern AutoShapes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QPainterPath


def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


class AdjustmentHandleDef:
    """Definition of an interactive adjustment handle on an AutoShape."""

    def __init__(
        self,
        pos_fn: Callable[[float, float, dict[str, Any]], tuple[float, float]],
        set_fn: Callable[[float, float, float, float, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.pos_fn = pos_fn
        self.set_fn = set_fn

    def get_pos(self, w: float, h: float, adj: dict[str, Any]) -> tuple[float, float]:
        return self.pos_fn(w, h, adj)

    def calculate_adj(
        self, x: float, y: float, w: float, h: float, current_adj: dict[str, Any]
    ) -> dict[str, Any]:
        return self.set_fn(x, y, w, h, current_adj)


# Preset adjustment definitions
HANDLE_DEFS: dict[str, list[AdjustmentHandleDef]] = {
    "roundRect": [
        AdjustmentHandleDef(
            pos_fn=lambda w, h, a: (
                (min(w, h) * float(a.get("adj", 16667))) / 100000.0,
                0.0,
            ),
            set_fn=lambda x, y, w, h, a: {
                "adj": clamp((x / max(1.0, min(w, h))) * 100000.0, 0.0, 50000.0)
            },
        )
    ],
    "triangle": [
        AdjustmentHandleDef(
            pos_fn=lambda w, h, a: (
                (w * float(a.get("adj", 50000))) / 100000.0,
                0.0,
            ),
            set_fn=lambda x, y, w, h, a: {
                "adj": clamp((x / max(1.0, w)) * 100000.0, 0.0, 100000.0)
            },
        )
    ],
    "parallelogram": [
        AdjustmentHandleDef(
            pos_fn=lambda w, h, a: (
                (min(w, h) * float(a.get("adj", 25000))) / 100000.0,
                0.0,
            ),
            set_fn=lambda x, y, w, h, a: {
                "adj": clamp(
                    (x / max(1.0, min(w, h))) * 100000.0,
                    0.0,
                    (w / max(1.0, min(w, h))) * 100000.0,
                )
            },
        )
    ],
    "trapezoid": [
        AdjustmentHandleDef(
            pos_fn=lambda w, h, a: (
                (min(w, h) * float(a.get("adj", 25000))) / 100000.0,
                0.0,
            ),
            set_fn=lambda x, y, w, h, a: {
                "adj": clamp(
                    (x / max(1.0, min(w, h))) * 100000.0,
                    0.0,
                    (w / 2.0 / max(1.0, min(w, h))) * 100000.0,
                )
            },
        )
    ],
    "rightArrow": [
        AdjustmentHandleDef(
            pos_fn=lambda w, h, a: (
                w - (min(w, h) * float(a.get("adj1", 50000))) / 100000.0,
                (h - (h * float(a.get("adj2", 50000))) / 100000.0) / 2.0,
            ),
            set_fn=lambda x, y, w, h, a: {
                "adj1": clamp(((w - x) / max(1.0, min(w, h))) * 100000.0, 0.0, 100000.0),
                "adj2": clamp((1.0 - (2.0 * y) / max(1.0, h)) * 100000.0, 10000.0, 90000.0),
            },
        )
    ],
}


def get_adjustment_handles(geom: str) -> list[AdjustmentHandleDef]:
    """Return adjustment handle definitions for the given geometry type."""
    return HANDLE_DEFS.get(geom, [])


def create_shape_path(
    geom: str, w: float, h: float, adj: dict[str, Any] | None = None
) -> QPainterPath:
    """Generate a closed vector QPainterPath for the given geometry preset."""
    path = QPainterPath()
    w = max(1.0, float(w))
    h = max(1.0, float(h))
    adj = adj or {}

    if geom == "roundRect":
        a_val = float(adj.get("adj", 16667))
        r = (min(w, h) * a_val) / 100000.0
        path.addRoundedRect(0.0, 0.0, w, h, r, r)

    elif geom in ("ellipse", "oval"):
        path.addEllipse(0.0, 0.0, w, h)

    elif geom == "triangle":
        apex_x = (w * float(adj.get("adj", 50000))) / 100000.0
        path.moveTo(apex_x, 0.0)
        path.lineTo(w, h)
        path.lineTo(0.0, h)
        path.closeSubpath()

    elif geom == "rtTriangle":
        path.moveTo(0.0, 0.0)
        path.lineTo(w, h)
        path.lineTo(0.0, h)
        path.closeSubpath()

    elif geom == "diamond":
        path.moveTo(w / 2.0, 0.0)
        path.lineTo(w, h / 2.0)
        path.lineTo(w / 2.0, h)
        path.lineTo(0.0, h / 2.0)
        path.closeSubpath()

    elif geom == "parallelogram":
        x = (min(w, h) * float(adj.get("adj", 25000))) / 100000.0
        path.moveTo(x, 0.0)
        path.lineTo(w, 0.0)
        path.lineTo(w - x, h)
        path.lineTo(0.0, h)
        path.closeSubpath()

    elif geom == "trapezoid":
        x = (min(w, h) * float(adj.get("adj", 25000))) / 100000.0
        path.moveTo(x, 0.0)
        path.lineTo(w - x, 0.0)
        path.lineTo(w, h)
        path.lineTo(0.0, h)
        path.closeSubpath()

    elif geom == "hexagon":
        x = (min(w, h) * float(adj.get("adj", 25000))) / 100000.0
        path.moveTo(x, 0.0)
        path.lineTo(w - x, 0.0)
        path.lineTo(w, h / 2.0)
        path.lineTo(w - x, h)
        path.lineTo(x, h)
        path.lineTo(0.0, h / 2.0)
        path.closeSubpath()

    elif geom == "octagon":
        x = (min(w, h) * float(adj.get("adj", 29289))) / 100000.0
        path.moveTo(x, 0.0)
        path.lineTo(w - x, 0.0)
        path.lineTo(w, x)
        path.lineTo(w, h - x)
        path.lineTo(w - x, h)
        path.lineTo(x, h)
        path.lineTo(0.0, h - x)
        path.lineTo(0.0, x)
        path.closeSubpath()

    elif geom == "rightArrow":
        adj1 = float(adj.get("adj1", 50000))
        adj2 = float(adj.get("adj2", 50000))
        head_w = (min(w, h) * adj1) / 100000.0
        shaft_h = (h * adj2) / 100000.0
        shaft_top = (h - shaft_h) / 2.0
        shaft_bot = shaft_top + shaft_h
        shaft_w = max(0.0, w - head_w)

        path.moveTo(0.0, shaft_top)
        path.lineTo(shaft_w, shaft_top)
        path.lineTo(shaft_w, 0.0)
        path.lineTo(w, h / 2.0)
        path.lineTo(shaft_w, h)
        path.lineTo(shaft_w, shaft_bot)
        path.lineTo(0.0, shaft_bot)
        path.closeSubpath()

    elif geom == "line":
        path.moveTo(0.0, 0.0)
        path.lineTo(w, h)

    else:
        # Default rectangle
        path.addRect(0.0, 0.0, w, h)

    return path
