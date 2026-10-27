"""Base geometric helpers and shape builder primitives for SmartArt layouts."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem


def lines_of(it: SmartArtItem, with_kids: bool = False) -> list[dict[str, Any]]:
    """Return text lines representation of an outline item."""
    res = [{"t": it.text or "", "lvl": 0}]
    if with_kids and it.kids:
        res.extend([{"t": k.text or "", "lvl": 1} for k in it.kids])
    return res


def kid_lines(it: SmartArtItem) -> list[dict[str, Any]]:
    """Return text lines representation of item's kids."""
    return [{"t": k.text or "", "lvl": 1} for k in (it.kids or [])]


def tb(x: float, y: float, w: float, h: float) -> dict[str, float]:
    """Helper to return a text bounding box dict."""
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}


def node_shape(
    it: SmartArtItem,
    i: int,
    n: int,
    geom: str,
    x: float,
    y: float,
    w: float,
    h: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a primary node shape dictionary."""
    base: dict[str, Any] = {
        "role": "node",
        "geom": geom,
        "x": float(x),
        "y": float(y),
        "w": float(w),
        "h": float(h),
        "rot": 0.0,
        "itemId": it.id,
        "level": 0,
        "styleLbl": "node1",
        "colorIdx": i,
        "colorCnt": n,
        "text": {
            "lines": lines_of(it, False),
            "box": tb(x, y, w, h),
            "anchor": "ctr",
            "align": "ctr",
        },
    }
    if extra:
        base.update(extra)
    return base


def row_unit(box: dict[str, float], n: int, a: float, g: float) -> float:
    """The largest width for items of aspect a (h = a * w) in a row of n with gaps g * w."""
    denom = n + (n - 1) * g
    w_fit = box["w"] / denom if denom > 0 else box["w"]
    h_fit = box["h"] / a if a > 0 else box["h"]
    return min(w_fit, h_fit)


def deg(r: float) -> float:
    """Convert radians to degrees."""
    return r * 180.0 / math.pi


def poly_box(pts: list[list[float]]) -> dict[str, Any]:
    """Compute bounding box for polygon points."""
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "geom": "poly",
        "poly": pts,
        "x": float(min_x),
        "y": float(min_y),
        "w": float(max(0.01, max_x - min_x)),
        "h": float(max(0.01, max_y - min_y)),
    }
