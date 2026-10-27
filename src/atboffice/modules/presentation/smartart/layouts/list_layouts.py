"""List category layouts for SmartArt (blockList, verticalBullet, stackedList, hBullet, linedList, vBox)."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import (
    kid_lines,
    lines_of,
    node_shape,
    tb,
)


def make_block_list(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Block List."""
    n = max(1, len(items))
    a = 0.6
    g = 0.1
    best_c = 1
    best_r = n
    best_w = 0.0

    for c in range(1, n + 1):
        r = math.ceil(n / c)
        w_cand = min(
            box["w"] / (c + (c - 1) * g),
            box["h"] / (r * a + (r - 1) * g * a),
        )
        if w_cand > best_w + 0.01:
            best_c = c
            best_r = r
            best_w = w_cand

    c, r, w = best_c, best_r, best_w
    h = a * w
    gx = g * w
    gy = g * h
    top = box["y"] + (box["h"] - (r * h + (r - 1) * gy)) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        row = i // c
        in_row = n - row * c if row == r - 1 else c
        left = box["x"] + (box["w"] - (in_row * w + (in_row - 1) * gx)) / 2.0
        x = left + (i - row * c) * (w + gx)
        y = top + row * (h + gy)
        out.append(
            node_shape(
                it,
                i,
                n,
                "rect",
                x,
                y,
                w,
                h,
                {"text": {"lines": lines_of(it, True), "box": tb(x, y, w, h), "anchor": "ctr", "align": "ctr"}},
            )
        )
    return out


def make_vertical_bullet(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Vertical Bullet List."""
    n = max(1, len(items))
    kid_h = 0.5
    g = 0.12
    weight = sum(1.0 + (kid_h * len(it.kids) + 0.1 if it.kids else 0.0) for it in items) + (n - 1) * g
    u = min(box["h"] / weight if weight > 0 else box["h"], box["w"] * 0.3)
    y = box["y"] + (box["h"] - u * weight) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        out.append(
            node_shape(
                it,
                i,
                n,
                "roundRect",
                box["x"],
                y,
                box["w"],
                u,
                {
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(box["x"] + u * 0.15, y, box["w"] - u * 0.3, u),
                        "anchor": "ctr",
                        "align": "l",
                    }
                },
            )
        )
        y += u
        if it.kids:
            h = kid_h * u * len(it.kids) + 0.1 * u
            out.append(
                {
                    "role": "child",
                    "geom": "rect",
                    "noFill": True,
                    "x": box["x"],
                    "y": y,
                    "w": box["w"],
                    "h": h,
                    "rot": 0.0,
                    "itemId": it.id,
                    "level": 1,
                    "styleLbl": "revTx",
                    "colorIdx": i,
                    "colorCnt": n,
                    "text": {
                        "lines": kid_lines(it),
                        "box": tb(box["x"] + u * 0.4, y, box["w"] - u * 0.5, h),
                        "anchor": "t",
                        "align": "l",
                    },
                }
            )
            y += h
        y += g * u
    return out


def make_stacked_list(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Stacked List."""
    n = max(1, len(items))
    g = 0.15
    denom = n + (n - 1) * g
    rh = min(box["h"] / denom if denom > 0 else box["h"], box["w"] * 0.3)
    y = box["y"] + (box["h"] - (n * rh + (n - 1) * g * rh)) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        d = rh
        cx = box["x"]
        # Child card to the right
        out.append(
            {
                "role": "child",
                "geom": "rect",
                "tint": True,
                "x": cx + d * 0.5,
                "y": y + rh * 0.12,
                "w": max(0.01, box["w"] - d * 0.5),
                "h": rh * 0.76,
                "rot": 0.0,
                "itemId": it.id,
                "level": 1,
                "styleLbl": "alignAcc1",
                "colorIdx": i,
                "colorCnt": n,
                "text": {
                    "lines": kid_lines(it),
                    "box": tb(cx + d * 1.1, y + rh * 0.12, max(0.01, box["w"] - d * 1.2), rh * 0.76),
                    "anchor": "t",
                    "align": "l",
                },
            }
        )
        # Primary circle node
        out.append(
            node_shape(
                it,
                i,
                n,
                "ellipse",
                cx,
                y,
                d,
                d,
                {
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(cx + d * 0.146, y + d * 0.146, d * 0.708, d * 0.708),
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        )
        y += rh * (1.0 + g)
    return out


def make_h_bullet(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Horizontal Bullet List."""
    n = max(1, len(items))
    g = 0.06
    denom = n + (n - 1) * g
    cw = box["w"] / denom if denom > 0 else box["w"]
    hh = min(box["h"] * 0.3, cw * 0.6)

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        x = box["x"] + i * cw * (1.0 + g)
        out.append(
            {
                "role": "child",
                "geom": "rect",
                "tint": True,
                "x": x,
                "y": box["y"] + hh,
                "w": cw,
                "h": max(0.01, box["h"] - hh),
                "rot": 0.0,
                "itemId": it.id,
                "level": 1,
                "styleLbl": "alignAcc1",
                "colorIdx": i,
                "colorCnt": n,
                "text": {
                    "lines": kid_lines(it),
                    "box": tb(x + cw * 0.08, box["y"] + hh + cw * 0.04, max(0.01, cw * 0.86), max(0.01, box["h"] - hh - cw * 0.04)),
                    "anchor": "t",
                    "align": "l",
                },
            }
        )
        out.append(node_shape(it, i, n, "rect", x, box["y"], cw, hh))
    return out


def make_lined_list(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Lined List."""
    n = max(1, len(items))
    rh = box["h"] / n
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        y = box["y"] + i * rh
        out.append(
            {
                "role": "conn",
                "geom": "path",
                "path": [[box["x"], y], [box["x"] + box["w"], y]],
                "x": box["x"],
                "y": y,
                "w": box["w"],
                "h": 0.0,
                "rot": 0.0,
                "itemId": it.id,
                "level": 0,
                "styleLbl": "parChTrans1D2",
                "colorIdx": i,
                "colorCnt": n,
            }
        )
        out.append(
            node_shape(
                it,
                i,
                n,
                "rect",
                box["x"],
                y,
                box["w"] * 0.3,
                rh,
                {
                    "noFill": True,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(box["x"], y, box["w"] * 0.3, rh),
                        "anchor": "t",
                        "align": "l",
                    },
                },
            )
        )
        if it.kids:
            out.append(
                {
                    "role": "child",
                    "geom": "rect",
                    "tint": False,
                    "noFill": True,
                    "x": box["x"] + box["w"] * 0.32,
                    "y": y,
                    "w": box["w"] * 0.68,
                    "h": rh,
                    "rot": 0.0,
                    "itemId": it.id,
                    "level": 1,
                    "styleLbl": "alignAcc1",
                    "colorIdx": i,
                    "colorCnt": n,
                    "text": {
                        "lines": kid_lines(it),
                        "box": tb(box["x"] + box["w"] * 0.32, y, box["w"] * 0.68, rh),
                        "anchor": "t",
                        "align": "l",
                    },
                }
            )
    return out


def make_v_box(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Vertical Box List."""
    n = max(1, len(items))
    tab_h = 0.38
    g = 0.1
    denom = n * (1.0 + tab_h * 0.5) + (n - 1) * g
    u = box["h"] / denom if denom > 0 else box["h"]
    y = box["y"] + (box["h"] - u * denom) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        th = u * tab_h
        by = y + th * 0.5
        out.append(
            {
                "role": "child",
                "geom": "rect",
                "tint": True,
                "line": True,
                "x": box["x"],
                "y": by,
                "w": box["w"],
                "h": u,
                "rot": 0.0,
                "itemId": it.id,
                "level": 1,
                "styleLbl": "alignAcc1",
                "colorIdx": i,
                "colorCnt": n,
                "text": {
                    "lines": kid_lines(it),
                    "box": tb(box["x"] + box["w"] * 0.05, by + th * 0.55, box["w"] * 0.9, max(0.01, u - th * 0.55)),
                    "anchor": "t",
                    "align": "l",
                },
            }
        )
        out.append(
            node_shape(
                it,
                i,
                n,
                "roundRect",
                box["x"] + box["w"] * 0.04,
                y,
                box["w"] * 0.62,
                th,
                {
                    "adj": [16667],
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(box["x"] + box["w"] * 0.06, y, box["w"] * 0.58, th),
                        "anchor": "ctr",
                        "align": "l",
                    },
                },
            )
        )
        y += u * (1.0 + tab_h * 0.5 + g)
    return out
