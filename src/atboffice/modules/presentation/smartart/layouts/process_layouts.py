"""Process category layouts for SmartArt.

Includes: process, chevron, stepUp, continuousArrow, vProcess, timeline.
"""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import (
    lines_of,
    node_shape,
    row_unit,
    tb,
)


def make_process(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Process."""
    n = max(1, len(items))
    a = 0.6
    g = 0.4
    w = row_unit(box, n, a, g)
    h = a * w
    left = box["x"] + (box["w"] - (n * w + (n - 1) * g * w)) / 2.0
    y = box["y"] + (box["h"] - h) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        x = left + i * w * (1.0 + g)
        out.append(node_shape(it, i, n, "roundRect", x, y, w, h, {"adj": [10000]}))
        if i < n - 1:
            aw = w * 0.22
            ah = w * 0.26
            out.append(
                {
                    "role": "arrow",
                    "geom": "rightArrow",
                    "adj": [60000, 50000],
                    "x": x + w + (g * w - aw) / 2.0,
                    "y": y + (h - ah) / 2.0,
                    "w": aw,
                    "h": ah,
                    "rot": 0.0,
                    "itemId": it.id,
                    "level": 0,
                    "styleLbl": "sibTrans2D1",
                    "colorIdx": i,
                    "colorCnt": n - 1,
                }
            )
    return out


def make_chevron(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Chevron Process."""
    n = max(1, len(items))
    a = 0.4
    step = 0.84
    w = min(box["w"] / (1.0 + (n - 1) * step), box["h"] / a)
    h = a * w
    left = box["x"] + (box["w"] - (w + (n - 1) * step * w)) / 2.0
    y = box["y"] + (box["h"] - h) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        x = left + i * step * w
        out.append(
            node_shape(
                it,
                i,
                n,
                "chevron",
                x,
                y,
                w,
                h,
                {
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(x + h * 0.5, y, max(0.01, w - h), h),
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        )
    return out


def make_step_up(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Step Up Process."""
    n = max(1, len(items))
    g = 0.1
    w = box["w"] / (n + (n - 1) * g)
    rise = 0.55
    h = min(box["h"] / (1.0 + (n - 1) * rise), w * 0.9)
    y0 = box["y"] + (box["h"] - h * (1.0 + (n - 1) * rise)) / 2.0 + h * (n - 1) * rise

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        out.append(
            node_shape(
                it,
                i,
                n,
                "roundRect",
                box["x"] + i * w * (1.0 + g),
                y0 - i * h * rise,
                w,
                h,
                {"adj": [10000]},
            )
        )
    return out


def make_continuous_arrow(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Continuous Arrow Process."""
    n = max(1, len(items))
    ah = min(box["h"], box["w"] * 0.32)
    ay = box["y"] + (box["h"] - ah) / 2.0

    out: list[dict[str, Any]] = [
        {
            "role": "arrow",
            "big": True,
            "geom": "rightArrow",
            "adj": [70000, 50000],
            "x": box["x"],
            "y": ay,
            "w": box["w"],
            "h": ah,
            "rot": 0.0,
            "itemId": items[0].id if items else None,
            "level": 0,
            "styleLbl": "sibTrans2D1",
            "colorIdx": 0,
            "colorCnt": 1,
        }
    ]

    span = box["w"] - ah * 0.6
    g = 0.12
    w = span / (n + (n - 1) * g)
    h = ah * 0.5

    for i, it in enumerate(items):
        out.append(
            node_shape(
                it,
                i,
                n,
                "roundRect",
                box["x"] + i * w * (1.0 + g),
                ay + (ah - h) / 2.0,
                w,
                h,
                {"adj": [16667]},
            )
        )
    return out


def make_v_process(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Vertical Process."""
    n = max(1, len(items))
    g = 0.5
    h = box["h"] / (n + (n - 1) * g)
    w = min(box["w"], h * 7.0)
    x = box["x"] + (box["w"] - w) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        y = box["y"] + i * h * (1.0 + g)
        out.append(node_shape(it, i, n, "roundRect", x, y, w, h, {"adj": [10000]}))
        if i < n - 1:
            arrow_len = g * h * 0.8
            arrow_thick = min(h * 0.45, arrow_len * 1.2)
            out.append(
                {
                    "role": "arrow",
                    "geom": "rightArrow",
                    "adj": [60000, 50000],
                    "x": box["x"] + box["w"] / 2.0 - arrow_len / 2.0,
                    "y": y + h + (g * h) / 2.0 - arrow_thick / 2.0,
                    "w": arrow_len,
                    "h": arrow_thick,
                    "rot": 90.0,
                    "itemId": it.id,
                    "level": 0,
                    "styleLbl": "sibTrans2D1",
                    "colorIdx": i,
                    "colorCnt": n - 1,
                }
            )
    return out


def make_timeline(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Timeline."""
    n = max(1, len(items))
    cy = box["y"] + box["h"] / 2.0
    line_h = min(box["h"] * 0.12, 24.0)

    out: list[dict[str, Any]] = [
        {
            "role": "arrow",
            "big": True,
            "geom": "rightArrow",
            "adj": [50000, 60000],
            "x": box["x"],
            "y": cy - line_h / 2.0,
            "w": box["w"],
            "h": line_h,
            "rot": 0.0,
            "itemId": items[0].id if items else None,
            "level": 0,
            "styleLbl": "sibTrans2D1",
            "colorIdx": 0,
            "colorCnt": 1,
        }
    ]

    step = (box["w"] - line_h * 1.5) / n
    d = min(line_h * 1.1, step * 0.4)
    lh = box["h"] / 2.0 - d

    for i, it in enumerate(items):
        mx = box["x"] + step * (i + 0.5)
        out.append(
            {
                "role": "marker",
                "geom": "ellipse",
                "x": mx - d / 2.0,
                "y": cy - d / 2.0,
                "w": d,
                "h": d,
                "rot": 0.0,
                "itemId": it.id,
                "level": 0,
                "styleLbl": "node1",
                "colorIdx": i,
                "colorCnt": n,
            }
        )
        up = i % 2 == 0
        y = box["y"] if up else cy + d / 2.0
        lw = min(step * 1.2, box["w"])
        lx = max(box["x"], min(mx - lw / 2.0, box["x"] + box["w"] - lw))
        out.append(
            node_shape(
                it,
                i,
                n,
                "rect",
                lx,
                y,
                lw,
                lh,
                {
                    "noFill": True,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(lx, y, lw, lh),
                        "anchor": "b" if up else "t",
                        "align": "ctr",
                    },
                },
            )
        )
    return out
