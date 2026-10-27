"""Relationship category layouts for SmartArt (venn, target, linearVenn, funnel)."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import (
    lines_of,
    node_shape,
    poly_box,
    tb,
)


def make_venn(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Venn."""
    n = max(1, len(items))
    s_dim = min(box["w"], box["h"])
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0

    k = 0.0 if n == 1 else (0.35 if n == 2 else 0.375 / math.sin(math.pi / n))
    d = s_dim / (1.0 + 2.0 * k)
    r = k * d

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        t = (0.0 if i else math.pi) if n == 2 else -math.pi / 2.0 + (2.0 * math.pi * i) / n
        ex = cx + r * math.cos(t)
        ey = cy + r * math.sin(t)
        x = ex - d / 2.0
        y = ey - d / 2.0
        off = 0.0 if n == 1 else d * 0.18
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
                    "styleLbl": "vennNode1",
                    "alpha": 0.5,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(
                            ex + off * math.cos(t) - d * 0.3,
                            ey + off * math.sin(t) - d * 0.22,
                            d * 0.6,
                            d * 0.44,
                        ),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )
    return out


def make_target(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Target."""
    n = max(1, len(items))
    s_dim = min(box["w"], box["h"])
    cx = box["x"] + box["w"] / 2.0
    cy = box["y"] + box["h"] / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        d = s_dim * (n - i) / n
        inner = s_dim * (n - i - 1) / n
        x = cx - d / 2.0
        y = cy - d / 2.0
        if i == n - 1:
            band = tb(cx - d * 0.35, cy - d * 0.25, d * 0.7, d * 0.5)
        else:
            band = tb(cx - d * 0.3, y + d * 0.02, d * 0.6, max(0.01, (d - inner) / 2.0 * 0.96))
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
                        "box": band,
                        "anchor": "ctr",
                        "align": "ctr",
                    }
                },
            )
        )
    return out


def make_linear_venn(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Linear Venn."""
    n = max(1, len(items))
    ov = 0.75
    d = min(box["h"], box["w"] / (1.0 + (n - 1) * ov))
    x0 = box["x"] + (box["w"] - d * (1.0 + (n - 1) * ov)) / 2.0
    y = box["y"] + (box["h"] - d) / 2.0

    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        x = x0 + i * d * ov
        mid = 0.1 if i == 0 else (0.3 if i == n - 1 else 0.2)
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
                    "styleLbl": "vennNode1",
                    "alpha": 0.5,
                    "text": {
                        "lines": lines_of(it, False),
                        "box": tb(x + d * mid, y + d * 0.3, d * 0.6, d * 0.4),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )
    return out


def make_funnel(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Funnel."""
    if not items:
        return []
    n = len(items)
    layers = items[:-1] if n > 1 else []
    last = items[-1]

    big_w = min(box["w"], box["h"] * 1.15)
    x0 = box["x"] + (box["w"] - big_w) / 2.0
    d = big_w * 0.3
    fh = box["h"] - d * 1.05
    lh = fh / len(layers) if layers else 0.0
    spout = big_w * 0.22

    out: list[dict[str, Any]] = []
    for i, it in enumerate(layers):
        w_top = big_w - (big_w - spout) * i / len(layers)
        w_bot = big_w - (big_w - spout) * (i + 1) / len(layers)
        x = box["x"] + (box["w"] - w_top) / 2.0
        y = box["y"] + i * lh
        inset = (w_top - w_bot) / 2.0
        hh = lh * 0.94
        poly = [
            [x, y],
            [x + w_top, y],
            [x + w_top - inset, y + hh],
            [x + inset, y + hh],
        ]
        g = poly_box(poly)
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
                        "box": tb(x + inset * 0.5, y, max(0.01, w_bot + inset), hh),
                        "anchor": "ctr",
                        "align": "ctr",
                    },
                },
            )
        )

    cx = x0 + big_w / 2.0
    y_last = box["y"] + box["h"] - d
    out.append(
        node_shape(
            last,
            n - 1,
            n,
            "ellipse",
            cx - d / 2.0,
            y_last,
            d,
            d,
            {
                "text": {
                    "lines": lines_of(last, False),
                    "box": tb(cx - d * 0.354, y_last + d * 0.146, d * 0.708, d * 0.708),
                    "anchor": "ctr",
                    "align": "ctr",
                }
            },
        )
    )
    return out
