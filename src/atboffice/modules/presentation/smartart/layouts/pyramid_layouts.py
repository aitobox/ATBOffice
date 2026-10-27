"""Pyramid category layouts for SmartArt (pyramid, invertedPyramid, pyramidList)."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import (
    lines_of,
    node_shape,
    poly_box,
    tb,
)


def make_pyramid(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Pyramid."""
    n = max(1, len(items))
    a = 0.87
    base = min(box["w"], box["h"] / a)
    big_h = base * a
    gap = big_h * 0.015 if n > 1 else 0.0

    def wt(i: int) -> float:
        return 1.7 if (i == 0 and n > 1) else 1.0

    sum_wt = sum(wt(i) for i in range(n))
    unit = (big_h - (n - 1) * gap) / sum_wt if sum_wt > 0 else big_h
    x0 = box["x"] + (box["w"] - base) / 2.0
    y0 = box["y"] + (box["h"] - big_h) / 2.0

    y_at = y0
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        lh = unit * wt(i)
        y_top = y_at
        w_top = base * (y_top - y0) / big_h if big_h > 0 else 0.0
        w_bot = base * (y_top + lh - y0) / big_h if big_h > 0 else base
        y_at += lh + gap
        x = x0 + (base - w_bot) / 2.0
        inset = (w_bot - w_top) / 2.0

        geom = "triangle" if i == 0 else "trapezoid"
        adj = (
            [50000]
            if i == 0
            else [round(inset / min(w_bot, lh) * 100000)]
            if min(w_bot, lh) > 0
            else [0]
        )
        tw = w_bot * 0.5 if i == 0 else w_top + inset * 0.8
        th = lh * 0.5 if i == 0 else lh

        out.append(
            node_shape(
                it,
                i,
                n,
                geom,
                x,
                y_top,
                w_bot,
                lh,
                {
                    "adj": adj,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(x + (w_bot - tw) / 2.0, y_top + lh - th, tw, th),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )
    return out


def make_inverted_pyramid(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Inverted Pyramid."""
    n = max(1, len(items))
    a = 0.87
    base = min(box["w"], box["h"] / a)
    big_h = base * a
    gap = big_h * 0.015 if n > 1 else 0.0

    def wt(i: int) -> float:
        return 1.7 if (i == n - 1 and n > 1) else 1.0

    sum_wt = sum(wt(i) for i in range(n))
    unit = (big_h - (n - 1) * gap) / sum_wt if sum_wt > 0 else big_h
    cx = box["x"] + box["w"] / 2.0
    y0 = box["y"] + (box["h"] - big_h) / 2.0

    def w_at(y: float) -> float:
        return base * (1.0 - (y - y0) / big_h) if big_h > 0 else 0.0

    y_at = y0
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        lh = unit * wt(i)
        y_top = y_at
        y_bot = y_top + lh
        w_t = w_at(y_top)
        w_b = w_at(y_bot)
        y_at += lh + gap
        last = i == n - 1

        if last:
            pts = [[cx - w_t / 2.0, y_top], [cx + w_t / 2.0, y_top], [cx, y_bot]]
        else:
            pts = [
                [cx - w_t / 2.0, y_top],
                [cx + w_t / 2.0, y_top],
                [cx + w_b / 2.0, y_bot],
                [cx - w_b / 2.0, y_bot],
            ]

        g = poly_box(pts)
        tw = w_t * 0.5 if last else w_b + (w_t - w_b) * 0.4
        th = lh * 0.5 if last else lh

        out.append(
            node_shape(
                it,
                i,
                n,
                "poly",
                g["x"],
                g["y"],
                g["w"],
                g["h"],
                {
                    "poly": g["poly"],
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(cx - tw / 2.0, y_top, tw, th),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )
    return out


def make_pyramid_list(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Pyramid List."""
    n = max(1, len(items))
    a = 0.87
    base = min(box["w"], box["h"] / a)
    big_h = base * a
    x0 = box["x"] + (box["w"] - base) / 2.0
    y0 = box["y"] + (box["h"] - big_h) / 2.0

    out: list[dict[str, Any]] = [
        {
            "role": "bg",
            "geom": "triangle",
            "adj": [50000],
            "x": x0,
            "y": y0,
            "w": base,
            "h": big_h,
            "rot": 0.0,
            "itemId": items[0].id if items else None,
            "level": 0,
            "styleLbl": "bgShp",
            "colorIdx": 0,
            "colorCnt": 1,
        }
    ]

    top = y0 + big_h * 0.28
    avail = big_h * 0.7
    g = 0.15
    denom = n + (n - 1) * g
    h = avail / denom if denom > 0 else avail
    w = base * 0.5

    for i, it in enumerate(items):
        out.append(
            node_shape(
                it,
                i,
                n,
                "roundRect",
                x0 + base / 2.0 - w / 2.0,
                top + i * h * (1.0 + g),
                w,
                h,
                {"adj": [16667]},
            )
        )
    return out
