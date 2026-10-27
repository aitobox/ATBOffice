"""Matrix category layouts for SmartArt (matrix)."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.presentation.smartart.item import SmartArtItem
from atboffice.modules.presentation.smartart.layouts.base import node_shape


def make_matrix(items: list[SmartArtItem], box: dict[str, float]) -> list[dict[str, Any]]:
    """Basic Matrix."""
    n = max(1, len(items))
    c = math.ceil(math.sqrt(n))
    r = math.ceil(n / c)
    g = 0.05
    s = min(box["w"] / (c + (c - 1) * g), box["h"] / (r + (r - 1) * g))
    w = min(box["w"] / (c + (c - 1) * g), s * 1.6)
    x0 = box["x"] + (box["w"] - (c * w + (c - 1) * g * s)) / 2.0
    y0 = box["y"] + (box["h"] - (r * s + (r - 1) * g * s)) / 2.0

    return [
        node_shape(
            it,
            i,
            n,
            "roundRect",
            x0 + (i % c) * (w + g * s),
            y0 + (i // c) * s * (1.0 + g),
            w,
            s,
            {"adj": [8000]},
        )
        for i, it in enumerate(items)
    ]
