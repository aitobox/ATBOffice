"""Automatic axis scaling and number formatting algorithms for DrawingML charts."""

from __future__ import annotations

import math
from typing import Any

from atboffice.drawing.numfmt import format_value


def nice_step(raw: float) -> float:
    """Calculate Office-standard nice step interval (1, 2, 5, or 10 * 10^n)."""
    if not (raw > 0.0):
        return 1.0
    mag = 10.0 ** math.floor(math.log10(raw))
    norm = raw / mag
    if norm <= 1.0000001:
        factor = 1.0
    elif norm <= 2.0000001:
        factor = 2.0
    elif norm <= 5.0000001:
        factor = 5.0
    else:
        factor = 10.0
    return factor * mag


def scale(
    lo: float,
    hi: float,
    ax: dict[str, Any] | None = None,
    length: float = 100.0,
    label_sz: float = 10.0,
    opts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Office automatic value-axis scale algorithm.

    Zero is included unless the minimum data point is well above zero (> 5/6 max).
    The axis top gets about 5% headroom, and the major unit is the smallest 1-2-5 step
    that keeps the interval count readable for the axis pixel length.
    """
    ax = ax or {}
    opts = opts or {}

    # 1. Logarithmic scale
    if ax.get("log"):
        base = float(ax.get("log", 10.0))
        if base <= 1.0:
            base = 10.0
        min_spec = ax.get("min")
        max_spec = ax.get("max")

        safe_lo = max(lo, 1e-12) if lo > 0.0 else 1.0
        mn = (
            float(min_spec)
            if min_spec is not None and float(min_spec) > 0.0
            else base ** math.floor(math.log(safe_lo) / math.log(base))
        )
        safe_hi = max(hi, mn * base)
        mx = (
            float(max_spec)
            if max_spec is not None
            else base ** math.ceil(math.log(safe_hi) / math.log(base))
        )
        if not (mx > mn):
            mx = mn * base

        ticks: list[float] = []
        cur = mn
        while cur <= mx * 1.0001:
            ticks.append(cur)
            cur *= base
        return {"min": mn, "max": mx, "ticks": ticks, "step": None, "log": base}

    # 2. Linear scale
    if not math.isfinite(lo) or not math.isfinite(hi):
        lo, hi = 0.0, 1.0
    if lo > hi:
        lo, hi = hi, lo

    fix_min = ax.get("min") is not None
    fix_max = ax.get("max") is not None

    if not opts.get("noZero"):
        if lo >= 0.0 and hi > 0.0:
            if not fix_min:
                if lo > hi * (5.0 / 6.0):
                    lo = max(0.0, lo - (hi - lo) / 2.0)
                else:
                    lo = 0.0
        elif hi <= 0.0 and lo < 0.0:
            if not fix_max:
                if hi < lo * (5.0 / 6.0):
                    hi = min(0.0, hi + (hi - lo) / 2.0)
                else:
                    hi = 0.0

    if fix_min and not fix_max and hi <= float(ax["min"]):
        hi = float(ax["min"]) + abs(float(ax["min"]) or 1.0)
    if fix_max and not fix_min and lo >= float(ax["max"]):
        lo = float(ax["max"]) - abs(float(ax["max"]) or 1.0)
    if lo == hi:
        if lo == 0.0:
            hi = 1.0
        elif lo > 0.0:
            lo = 0.0
        else:
            hi = 0.0

    max_n = max(2, min(10, int(math.floor(length / max(label_sz * 1.6, 10.0)))))
    lo0 = float(ax["min"]) if fix_min else lo
    hi0 = float(ax["max"]) if fix_max else hi

    head = 0.0 if opts.get("noHead") else (hi0 - lo0) * 0.05
    hi_h = hi0 if fix_max else (hi0 + head if hi0 > 0.0 else hi0)
    lo_h = lo0 if fix_min else (lo0 - head if lo0 < 0.0 else lo0)

    major_spec = ax.get("major")
    if major_spec is not None and float(major_spec) > 0.0:
        step = float(major_spec)
    else:
        span = hi_h - lo_h
        step = nice_step(span / max_n if span > 0 else 1.0)

    mx = float(ax["max"]) if fix_max else math.ceil(hi_h / step - 1e-9) * step
    mn = float(ax["min"]) if fix_min else math.floor(lo_h / step + 1e-9) * step

    max_v, min_v = mx, mn
    if not (max_v > min_v):
        max_v = min_v + (step or 1.0)
    if not (step > 0.0) or (max_v - min_v) / step > 200:
        step = nice_step((max_v - min_v) / max_n)

    ticks_list: list[float] = []
    first = math.ceil(min_v / step - 1e-9) * step
    cur_v = first
    limit = max_v + step * 1e-6
    while cur_v <= limit:
        val = 0.0 if abs(cur_v) < step * 1e-9 else round(cur_v, 8)
        ticks_list.append(val)
        cur_v += step

    return {"min": min_v, "max": max_v, "ticks": ticks_list, "step": step, "log": None}


def format_val(v: float | None, code: str | None = None) -> str:
    """Format numerical value using Excel-compatible number format code."""
    if v is None or not math.isfinite(v):
        return ""
    if code and code != "General":
        try:
            return format_value(v, code).text
        except Exception:
            pass
    try:
        return format_value(v, "General").text
    except Exception:
        return str(round(v, 2)) if v != int(v) else str(int(v))
