"""Geometry path and adjustment handle helpers for Lectern AutoShapes."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QPainterPath, QTransform


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
    geom: str,
    w: float,
    h: float,
    adj: dict[str, Any] | None = None,
    custom_path: dict[str, Any] | None = None,
) -> QPainterPath:
    """Generate a vector QPainterPath for the given geometry preset or custom path."""
    path = QPainterPath()
    w = max(1.0, float(w))
    h = max(1.0, float(h))
    adj = adj or {}

    if adj and "route" in adj and adj["route"]:
        pts = adj["route"]
        if len(pts) >= 2:
            path.moveTo(float(pts[0][0]), float(pts[0][1]))
            for pt in pts[1:]:
                path.lineTo(float(pt[0]), float(pt[1]))
            return path

    if (geom == "custom" or custom_path) and custom_path and "paths" in custom_path:
        for p_info in custom_path["paths"]:
            pw = float(p_info.get("w", w)) or w
            ph = float(p_info.get("h", h)) or h
            sx = w / pw if pw > 0 else 1.0
            sy = h / ph if ph > 0 else 1.0
            for cmd in p_info.get("cmds", []):
                op = cmd[0]
                if op == "M" and len(cmd) >= 3:
                    path.moveTo(float(cmd[1]) * sx, float(cmd[2]) * sy)
                elif op == "L" and len(cmd) >= 3:
                    path.lineTo(float(cmd[1]) * sx, float(cmd[2]) * sy)
                elif op == "C" and len(cmd) >= 7:
                    path.cubicTo(
                        float(cmd[1]) * sx, float(cmd[2]) * sy,
                        float(cmd[3]) * sx, float(cmd[4]) * sy,
                        float(cmd[5]) * sx, float(cmd[6]) * sy,
                    )
                elif op == "Q" and len(cmd) >= 5:
                    path.quadTo(
                        float(cmd[1]) * sx, float(cmd[2]) * sy,
                        float(cmd[3]) * sx, float(cmd[4]) * sy,
                    )
                elif op == "A" and len(cmd) >= 5:
                    # DrawingML arcTo starts at the current point, which lies on the
                    # ellipse at stAng (degrees, clockwise in y-down space); the
                    # ellipse centre is derived from it. Qt angles run
                    # counter-clockwise, hence the sign flips.
                    wr = abs(float(cmd[1]) * sx)
                    hr = abs(float(cmd[2]) * sy)
                    st_ang = float(cmd[3])
                    sw_ang = float(cmd[4])
                    cur = path.currentPosition()
                    st_rad = math.radians(st_ang)
                    cx = cur.x() - wr * math.cos(st_rad)
                    cy = cur.y() - hr * math.sin(st_rad)
                    if wr <= 0.0 or hr <= 0.0:
                        end_rad = math.radians(st_ang + sw_ang)
                        path.lineTo(cx + wr * math.cos(end_rad), cy + hr * math.sin(end_rad))
                    else:
                        path.arcTo(cx - wr, cy - hr, wr * 2, hr * 2, -st_ang, -sw_ang)
                elif op == "Z":
                    path.closeSubpath()
        return path

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

    elif geom in ("line", "straightConnector1"):
        path.moveTo(0.0, 0.0)
        path.lineTo(w, h)

    elif geom == "bentConnector2":
        path.moveTo(0.0, 0.0)
        path.lineTo(w, 0.0)
        path.lineTo(w, h)

    elif geom in ("bentConnector3", "bentConnector4", "bentConnector5"):
        mid_x = w / 2.0
        path.moveTo(0.0, 0.0)
        path.lineTo(mid_x, 0.0)
        path.lineTo(mid_x, h)
        path.lineTo(w, h)

    elif geom in ("curvedConnector2", "curvedConnector3"):
        path.moveTo(0.0, 0.0)
        path.cubicTo(w / 2.0, 0.0, w / 2.0, h, w, h)

    else:
        # Default rectangle
        path.addRect(0.0, 0.0, w, h)

    return path


def flip_transform(w: float, h: float, flip_h: bool, flip_v: bool) -> QTransform:
    """Mirror transform for a shape's local box (applied before rotation).

    flipH reflects across the vertical centre line and flipV across the horizontal
    one, so the box (0, 0, w, h) maps onto itself.
    """
    return QTransform(
        -1.0 if flip_h else 1.0,
        0.0,
        0.0,
        -1.0 if flip_v else 1.0,
        float(w) if flip_h else 0.0,
        float(h) if flip_v else 0.0,
    )


def connector_local_endpoints(
    w: float, h: float, flip_h: bool = False, flip_v: bool = False
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Local start/end points of an unrouted connector honoring its flips.

    An unflipped connector runs from the top-left to the bottom-right corner of its
    box; each flip mirrors both ends along that axis.
    """
    sx, ex = (w, 0.0) if flip_h else (0.0, w)
    sy, ey = (h, 0.0) if flip_v else (0.0, h)
    return (sx, sy), (ex, ey)


def get_shape_connection_sites(
    geom: str,
    w: float,
    h: float,
    adj: dict[str, Any] | None = None,
) -> list[tuple[float, float]]:
    """Return local coordinates of standard connection sites on shape perimeter.

    Standard indexing follows Office DrawingML conventions:
      Index 0: Top-center
      Index 1: Right-center
      Index 2: Bottom-center
      Index 3: Left-center
    """
    w = max(1.0, float(w))
    h = max(1.0, float(h))
    adj = adj or {}

    if geom == "triangle":
        apex_x = (w * float(adj.get("adj", 50000))) / 100000.0
        return [
            (apex_x, 0.0),
            ((w + apex_x) / 2.0, h / 2.0),
            (w / 2.0, h),
            (apex_x / 2.0, h / 2.0),
        ]
    elif geom == "diamond":
        return [
            (w / 2.0, 0.0),
            (w, h / 2.0),
            (w / 2.0, h),
            (0.0, h / 2.0),
        ]
    elif geom in ("ellipse", "oval"):
        return [
            (w / 2.0, 0.0),
            (w, h / 2.0),
            (w / 2.0, h),
            (0.0, h / 2.0),
        ]
    else:
        # Default bounding box cardinal connection sites
        return [
            (w / 2.0, 0.0),      # 0: Top
            (w, h / 2.0),        # 1: Right
            (w / 2.0, h),        # 2: Bottom
            (0.0, h / 2.0),      # 3: Left
        ]


def calculate_connector_route(
    p1: tuple[float, float],
    p2: tuple[float, float],
    geom: str = "straightConnector1",
    site1_idx: int | None = None,
    site2_idx: int | None = None,
) -> list[tuple[float, float]]:
    """Calculate waypoints for connector routes between two points in scene coordinates.

    Returns a list of (x, y) coordinates forming the route segments.
    """
    x1, y1 = p1
    x2, y2 = p2

    if geom in ("line", "straightConnector1"):
        return [(x1, y1), (x2, y2)]

    if geom == "bentConnector2":
        # 1 bend: horizontal then vertical, or vertical then horizontal
        if site1_idx in (0, 2):  # exits top or bottom
            return [(x1, y1), (x1, y2), (x2, y2)]
        else:  # exits left or right
            return [(x1, y1), (x2, y1), (x2, y2)]

    if geom in ("bentConnector3", "bentConnector4", "bentConnector5"):
        # Elbow connector with 2 orthogonal bends
        if site1_idx in (0, 2) and site2_idx in (0, 2):
            # Both exit vertically
            mid_y = (y1 + y2) / 2.0
            return [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]
        elif site1_idx in (1, 3) and site2_idx in (1, 3):
            # Both exit horizontally
            mid_x = (x1 + x2) / 2.0
            return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
        elif site1_idx in (0, 2):
            # Exits vertically, enters horizontally
            return [(x1, y1), (x1, y2), (x2, y2)]
        elif site1_idx in (1, 3):
            # Exits horizontally, enters vertically
            return [(x1, y1), (x2, y1), (x2, y2)]
        else:
            # Fallback based on dominant axis
            if abs(x2 - x1) >= abs(y2 - y1):
                mid_x = (x1 + x2) / 2.0
                return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
            else:
                mid_y = (y1 + y2) / 2.0
                return [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]

    # Default fallback
    return [(x1, y1), (x2, y2)]
