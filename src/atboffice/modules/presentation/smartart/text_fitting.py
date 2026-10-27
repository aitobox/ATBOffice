"""Adaptive text measurement, word wrapping, and uniform font size solver."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

LINE_HEIGHT: float = 1.2


def measure_with(font: str = "") -> Callable[[str, float], float]:
    """Return text measurement function calculating width in points.

    By default, uses an average glyph width factor of 0.5 * font size.
    """

    def _measure(text: str, size: float) -> float:
        if not text:
            return 0.0
        # If Qt QFontMetrics is available, we could use it,
        # but 0.5 * len * size is fast and deterministic
        return len(text) * size * 0.5

    return _measure


def wrap_text(
    lines: list[dict[str, Any]],
    width: float,
    size: float,
    measure: Callable[[str, float], float] | None = None,
) -> list[dict[str, Any]] | None:
    """Break lines into words fitting width at font size; returns None if single word cannot fit."""
    if measure is None:
        measure = measure_with()

    out: list[dict[str, Any]] = []
    for ln in lines:
        lvl = ln.get("lvl", 0)
        indent = size * 0.9 if lvl else 0.0
        raw_t = str(ln.get("t", ""))
        words = [w for w in raw_t.split() if w]
        if not words:
            out.append({"t": "", "lvl": lvl})
            continue

        cur = ""
        for w in words:
            if measure(w, size) > width - indent:
                return None
            next_line = f"{cur} {w}" if cur else w
            if measure(next_line, size) <= width - indent:
                cur = next_line
            else:
                out.append({"t": cur, "lvl": lvl})
                cur = w
        out.append({"t": cur, "lvl": lvl})

    return out


def fits(
    sh: dict[str, Any],
    size: float,
    measure: Callable[[str, float], float] | None = None,
) -> bool:
    """Check if shape text fits within its text box at given font size."""
    if measure is None:
        measure = measure_with()

    text_info = sh.get("text")
    if not text_info or "box" not in text_info:
        return True

    b = text_info["box"]
    inset = size * 0.25
    avail_w = b["w"] - 2.0 * inset
    avail_h = b["h"] - 2.0 * inset

    if avail_w <= 0 or avail_h <= 0:
        return False

    lines = text_info.get("lines", [])
    wrapped = wrap_text(lines, avail_w, size, measure)
    if wrapped is None:
        return False

    return len(wrapped) * size * LINE_HEIGHT <= avail_h + 0.01


def fit_text(
    shapes: list[dict[str, Any]],
    opts: dict[str, Any] | None = None,
) -> None:
    """Solve uniform maximum adaptive font size across all shapes of each role."""
    opts = opts or {}
    measure = opts.get("measure") or measure_with()

    groups: dict[str, list[dict[str, Any]]] = {}
    for sh in shapes:
        if sh.get("text"):
            k = "child" if sh.get("role") == "child" else "node"
            groups.setdefault(k, []).append(sh)

    for k, sh_list in groups.items():
        max_font = opts.get("maxChildFont", 24.0) if k == "child" else opts.get("maxFont", 40.0)
        min_font = opts.get("minFont", 6.0)

        lo = min_font
        hi = max_font
        if all(fits(s, hi, measure) for s in sh_list):
            lo = hi
        else:
            for _ in range(20):
                mid = (lo + hi) / 2.0
                if all(fits(s, mid, measure) for s in sh_list):
                    lo = mid
                else:
                    hi = mid

        size = max(min_font, math.floor(lo * 2.0) / 2.0)
        for s in sh_list:
            s["fontSize"] = size

    # Sub-item bullets are never bigger than 90% of their primary node's text
    node_shape = next((s for s in shapes if s.get("text") and s.get("role") != "child"), None)
    if node_shape and "fontSize" in node_shape:
        node_font = node_shape["fontSize"]
        cap = math.floor(node_font * 0.9 * 2.0) / 2.0
        for s in shapes:
            if s.get("role") == "child" and s.get("fontSize", 0.0) > cap:
                s["fontSize"] = cap
