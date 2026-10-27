"""Cycle category layouts for SmartArt (cycle, radial, continuousCycle)."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import (
    deg,
    lines_of,
    node_shape,
    tb,
)


def make_cycle(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Cycle."""
    n = max(1, len(items))
    s_dim = min(box["w"], box["h"])
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0

    if n == 1:
        d = s_dim
        return [
            node_shape(
                items[0],
                0,
                1,
                "ellipse",
                cx - d / 2.0,
                cy - d / 2.0,
                d,
                d,
                {
                    "text": {
                        "lines": lines_of(items[0], False),
                        "box": tb(cx - d * 0.35, cy - d * 0.35, d * 0.7, d * 0.7),
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        ]

    k = min(1.05, 1.55 * math.sin(math.pi / n))
    r = s_dim / (2.0 + k)
    d = k * r
    out: list[dict[str, Any]] = []

    def at_angle(idx: int) -> float:
        return -math.pi / 2.0 + (2.0 * math.pi * idx) / n

    for i, it in enumerate(items):
        t = at_angle(i)
        x = cx + r * math.cos(t) - d / 2.0
        y = cy + r * math.sin(t) - d / 2.0
        out.append(
            node_shape(
                it,
                i,
                n,
                "ellipse",
                x,
                y,
                d,
                d,
                {
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(x + d * 0.12, y + d * 0.15, d * 0.76, d * 0.7),
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        )

    for i, it in enumerate(items):
        t = (at_angle(i) + at_angle(i + 1)) / 2.0
        chord = 2.0 * r * math.sin(math.pi / n)
        aw = max(d * 0.15, (chord - d) * 0.6)
        ah = d * 0.22
        mx = cx + r * math.cos(t)
        my = cy + r * math.sin(t)
        out.append(
            {
                "role": "arrow",
                "geom": "rightArrow",
                "adj": [60000, 50000],
                "x": mx - aw / 2.0,
                "y": my - ah / 2.0,
                "w": aw,
                "h": ah,
                "rot": deg(t) + 90.0,
                "itemId": it.id,
                "level": 0,
                "styleLbl": "sibTrans2D1",
                "colorIdx": i,
                "colorCnt": n,
            }
        )

    return out


def make_radial(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Radial."""
    if not items:
        return []

    centre = items[0]
    around = centre.kids if centre.kids else items[1:]
    n = len(around)
    s_dim = min(box["w"], box["h"])
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0

    if n == 0:
        d = s_dim * 0.5
        return [
            node_shape(
                centre,
                0,
                1,
                "ellipse",
                cx - d / 2.0,
                cy - d / 2.0,
                d,
                d,
                {
                    "text": {
                        "lines": lines_of(centre, False),
                        "box": tb(cx - d * 0.35, cy - d * 0.35, d * 0.7, d * 0.7),
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        ]

    big_d = s_dim / 2.9
    small_d = 0.8 * big_d
    r = big_d / 2.0 + 0.2 * big_d + small_d / 2.0
    room = 2.0 * r * math.sin(math.pi / max(n, 2)) * 0.85
    if small_d > room:
        small_d = room
        r = big_d / 2.0 + 0.2 * big_d + small_d / 2.0

    scale = s_dim / (2.0 * r + small_d) if (2.0 * r + small_d) > 0 else 1.0
    big_d *= scale
    small_d *= scale
    r *= scale

    out: list[dict[str, Any]] = [
        node_shape(
            centre,
            0,
            n + 1,
            "ellipse",
            cx - big_d / 2.0,
            cy - big_d / 2.0,
            big_d,
            big_d,
            {
                "text": {
                    "lines": lines_of(centre, False),
                    "box": tb(cx - big_d * 0.35, cy - big_d * 0.35, big_d * 0.7, big_d * 0.7),
                    "anchor": "ctr",
                    "align": "ctr",
                }
            },
        )
    ]

    for i, it in enumerate(around):
        t = -math.pi / 2.0 + (2.0 * math.pi * i) / n
        sx = cx + r * math.cos(t)
        sy = cy + r * math.sin(t)
        nx = sx - small_d / 2.0
        ny = sy - small_d / 2.0

        p1 = [cx + (big_d / 2.0) * math.cos(t), cy + (big_d / 2.0) * math.sin(t)]
        p2 = [sx - (small_d / 2.0) * math.cos(t), sy - (small_d / 2.0) * math.sin(t)]
        xs = [p1[0], p2[0]]
        ys = [p1[1], p2[1]]

        out.append(
            {
                "role": "conn",
                "geom": "path",
                "path": [p1, p2],
                "x": min(xs),
                "y": min(ys),
                "w": max(0.01, max(xs) - min(xs)),
                "h": max(0.01, max(ys) - min(ys)),
                "rot": 0.0,
                "itemId": it.id,
                "level": 1,
                "styleLbl": "parChTrans1D2",
                "colorIdx": i,
                "colorCnt": n,
            }
        )
        out.append(
            node_shape(
                it,
                i + 1,
                n + 1,
                "ellipse",
                nx,
                ny,
                small_d,
                small_d,
                {
                    "level": 1,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(sx - small_d * 0.35, sy - small_d * 0.35, small_d * 0.7, small_d * 0.7),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )

    stretch_k = min(2.0, box["w"] / (2.0 * r + small_d)) if (2.0 * r + small_d) > 0 else 1.0
    if stretch_k > 1.0:
        for sh in out:
            sh["x"] = cx + (sh["x"] - cx) * stretch_k
            sh["w"] *= stretch_k
            if "path" in sh and sh["path"]:
                sh["path"] = [[cx + (pt[0] - cx) * stretch_k, pt[1]] for pt in sh["path"]]
            if sh.get("text") and "box" in sh["text"]:
                t_box = sh["text"]["box"]
                t_box["x"] = cx + (t_box["x"] - cx) * stretch_k
                t_box["w"] *= stretch_k

    return out


def make_continuous_cycle(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Continuous Cycle."""
    n = max(1, len(items))
    s_dim = min(box["w"], box["h"])
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0

    k = min(0.9, 1.6 * math.sin(math.pi / max(n, 2)))
    nw = (s_dim / (2.0 + k * 0.6)) * k
    nh = nw * 0.6
    r = (s_dim - nh) / 2.0

    ring = [
        [cx + r * math.cos((2.0 * math.pi * j) / 72.0), cy + r * math.sin((2.0 * math.pi * j) / 72.0)]
        for j in range(73)
    ]
    out: list[dict[str, Any]] = [
        {
            "role": "ring",
            "geom": "path",
            "path": ring,
            "x": cx - r,
            "y": cy - r,
            "w": 2.0 * r,
            "h": 2.0 * r,
            "rot": 0.0,
            "itemId": items[0].id if items else None,
            "level": 0,
            "styleLbl": "sibTrans2D1",
            "colorIdx": 0,
            "colorCnt": 1,
        }
    ]

    for i, it in enumerate(items):
        t = -math.pi / 2.0 + (2.0 * math.pi * i) / n
        x = cx + r * math.cos(t) - nw / 2.0
        y = cy + r * math.sin(t) - nh / 2.0
        clamped_x = max(box["x"], min(x, box["x"] + box["w"] - nw))
        out.append(node_shape(it, i, n, "roundRect", clamped_x, y, nw, nh, {"adj": [16667]}))

    return out
