"""Worksheet discounted cash flow and rate of return functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import (
    flatten_values,
    opt,
    register_fin,
    to_float,
)


@register_fin("NPV")
def fn_npv(rate: Any, *values: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    r_val = to_float(rate)
    if is_error(r_val):
        return r_val
    r_f = float(r_val)
    if r_f == -1.0:
        return DIV0

    flat = flatten_values(list(values), ctx)
    s = 0.0
    idx = 1
    for item in flat:
        if item is None or item == "":
            continue
        v_val = to_float(item)
        if is_error(v_val):
            return v_val
        try:
            s += float(v_val) / ((1.0 + r_f) ** idx)
            idx += 1
        except Exception:
            return NUM
    return s


def calc_irr(v: list[float], guess: float = 0.1) -> float | ExcelError:
    """Calculate internal rate of return using Newton-Raphson with bisection fallback."""
    if not any(x > 0 for x in v) or not any(x < 0 for x in v):
        return NUM

    def func(r: float) -> float:
        return sum(x / ((1.0 + r) ** i) for i, x in enumerate(v))

    def deriv(r: float) -> float:
        return sum(-i * x / ((1.0 + r) ** (i + 1)) for i, x in enumerate(v))

    r = guess
    for _ in range(100):
        try:
            f = func(r)
            d = deriv(r)
            if not math.isfinite(f) or not math.isfinite(d) or d == 0:
                break
            nr = r - f / d
            if abs(nr - r) < 1e-12 * max(1.0, abs(r)):
                return nr
            r = (r - 1.0) / 2.0 if nr <= -1.0 else nr
        except Exception:
            break

    try:
        if abs(func(r)) < 1e-7:
            return r
    except Exception:
        pass

    # Bisection fallback on (-0.9999, 10.0)
    lo, hi = -0.9999, 10.0
    try:
        flo, fhi = func(lo), func(hi)
        if flo * fhi <= 0:
            for _ in range(300):
                m = (lo + hi) / 2.0
                fm = func(m)
                if abs(fm) < 1e-12:
                    return m
                if (fm < 0) == (flo < 0):
                    lo, flo = m, fm
                else:
                    hi = m
            return (lo + hi) / 2.0
    except Exception:
        pass

    return NUM


@register_fin("IRR")
def fn_irr(values: Any, guess: Any = None, ctx: EvalContext | None = None) -> float | ExcelError:
    g_val = to_float(opt(guess, 0.1))
    if is_error(g_val):
        return g_val
    flat = flatten_values([values], ctx)
    nums: list[float] = []
    for item in flat:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            nums.append(float(item))
        elif item is not None and item != "":
            val = to_float(item)
            if not is_error(val):
                nums.append(float(val))
    if not nums:
        return NUM
    return calc_irr(nums, float(g_val))


@register_fin("MIRR")
def fn_mirr(
    values: Any,
    finance_rate: Any,
    reinvest_rate: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    fr_val = to_float(finance_rate)
    rr_val = to_float(reinvest_rate)
    for val in (fr_val, rr_val):
        if is_error(val):
            return val
    fr_f, rr_f = float(fr_val), float(rr_val)

    flat = flatten_values([values], ctx)
    nums: list[float] = []
    for item in flat:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            nums.append(float(item))
        elif item is not None and item != "":
            val = to_float(item)
            if not is_error(val):
                nums.append(float(val))

    n = len(nums)
    if n <= 1:
        return DIV0
    pos = sum(x * ((1.0 + rr_f) ** (n - 1 - i)) for i, x in enumerate(nums) if x > 0)
    neg = sum(x / ((1.0 + fr_f) ** i) for i, x in enumerate(nums) if x < 0)
    if pos == 0 or neg == 0:
        return DIV0
    try:
        return (-pos / neg) ** (1.0 / (n - 1)) - 1.0
    except Exception:
        return NUM


def extract_xflows(
    values: Any, dates: Any, ctx: EvalContext | None = None
) -> tuple[list[float], list[int]] | ExcelError:
    v_flat = flatten_values([values], ctx)
    d_flat = flatten_values([dates], ctx)
    if len(v_flat) != len(d_flat) or len(v_flat) == 0:
        return NUM
    v_list: list[float] = []
    d_list: list[int] = []
    for v_item, d_item in zip(v_flat, d_flat):
        if is_error(v_item):
            return v_item
        if is_error(d_item):
            return d_item
        v_num = to_float(v_item)
        d_num = to_float(d_item)
        if is_error(v_num) or is_error(d_num):
            return VALUE
        v_list.append(float(v_num))
        d_list.append(int(math.floor(float(d_num))))
    d0 = d_list[0]
    if any(d < d0 for d in d_list):
        return NUM
    return (v_list, d_list)


def calc_xnpv(r: float, v: list[float], d: list[int]) -> float:
    d0 = d[0]
    return sum(x / ((1.0 + r) ** ((dt - d0) / 365.0)) for x, dt in zip(v, d))


@register_fin("XNPV")
def fn_xnpv(
    rate: Any, values: Any, dates: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    r_val = to_float(rate)
    if is_error(r_val):
        return r_val
    r_f = float(r_val)
    if r_f <= -1.0:
        return NUM
    flows = extract_xflows(values, dates, ctx)
    if is_error(flows):
        return flows
    assert isinstance(flows, tuple)
    v_list, d_list = flows
    try:
        return calc_xnpv(r_f, v_list, d_list)
    except Exception:
        return NUM


@register_fin("XIRR")
def fn_xirr(
    values: Any,
    dates: Any,
    guess: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    g_val = to_float(opt(guess, 0.1))
    if is_error(g_val):
        return g_val
    flows = extract_xflows(values, dates, ctx)
    if is_error(flows):
        return flows
    assert isinstance(flows, tuple)
    v_list, d_list = flows
    if not any(x > 0 for x in v_list) or not any(x < 0 for x in v_list):
        return NUM

    d0 = d_list[0]

    def deriv(x: float) -> float:
        return sum(
            -((dt - d0) / 365.0) * c / ((1.0 + x) ** ((dt - d0) / 365.0 + 1.0))
            for c, dt in zip(v_list, d_list)
        )

    r = float(g_val)
    for _ in range(100):
        try:
            y = calc_xnpv(r, v_list, d_list)
            dy = deriv(r)
            if not math.isfinite(y) or dy == 0:
                break
            nr = r - y / dy
            if nr <= -1.0:
                nr = (r - 1.0) / 2.0
            if abs(nr - r) < 1e-12:
                return nr
            r = nr
        except Exception:
            break

    try:
        if abs(calc_xnpv(r, v_list, d_list)) < 1e-6:
            return r
    except Exception:
        pass

    # Bisection
    lo, hi = -0.9999, 100.0
    try:
        flo = calc_xnpv(lo, v_list, d_list)
        fhi = calc_xnpv(hi, v_list, d_list)
        if flo * fhi <= 0:
            for _ in range(400):
                m = (lo + hi) / 2.0
                fm = calc_xnpv(m, v_list, d_list)
                if abs(fm) < 1e-10:
                    return m
                if (fm < 0) == (flo < 0):
                    lo, flo = m, fm
                else:
                    hi = m
            return (lo + hi) / 2.0
    except Exception:
        pass

    return NUM
