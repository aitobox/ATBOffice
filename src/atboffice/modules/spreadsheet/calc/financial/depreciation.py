"""Worksheet asset depreciation calculation functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import yearfrac
from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NUM, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import opt, register_fin, to_float


@register_fin("SLN")
def fn_sln(
    cost: Any, salvage: Any, life: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    c_val = to_float(cost)
    s_val = to_float(salvage)
    l_val = to_float(life)
    for val in (c_val, s_val, l_val):
        if is_error(val):
            return val
    l_f = float(l_val)
    if l_f == 0:
        return DIV0
    return (float(c_val) - float(s_val)) / l_f


@register_fin("SYD")
def fn_syd(
    cost: Any, salvage: Any, life: Any, per: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    c_val = to_float(cost)
    s_val = to_float(salvage)
    l_val = to_float(life)
    p_val = to_float(per)
    for val in (c_val, s_val, l_val, p_val):
        if is_error(val):
            return val
    c_f, s_f, l_f, p_f = float(c_val), float(s_val), float(l_val), float(p_val)
    if l_f <= 0 or p_f <= 0 or p_f > l_f or s_f < 0:
        return NUM
    return ((c_f - s_f) * (l_f - p_f + 1.0) * 2.0) / (l_f * (l_f + 1.0))


@register_fin("DB")
def fn_db(
    cost: Any,
    salvage: Any,
    life: Any,
    period: Any,
    month: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    c_val = to_float(cost)
    s_val = to_float(salvage)
    l_val = to_float(life)
    p_val = to_float(period)
    m_val = to_float(opt(month, 12))
    for val in (c_val, s_val, l_val, p_val, m_val):
        if is_error(val):
            return val
    c_f, s_f, l_f = float(c_val), float(s_val), float(l_val)
    p_int, m_int = int(float(p_val)), int(float(m_val))
    if (
        c_f < 0
        or s_f < 0
        or l_f <= 0
        or p_int <= 0
        or m_int < 1
        or m_int > 12
        or p_int > l_f + 1
        or (p_int > l_f and m_int == 12)
    ):
        return NUM
    if c_f == 0:
        return 0.0
    r = round((1.0 - (s_f / c_f) ** (1.0 / l_f)) * 1000.0) / 1000.0
    total = (c_f * r * m_int) / 12.0
    if p_int == 1:
        return total
    dep = 0.0
    for i in range(2, p_int + 1):
        dep = ((c_f - total) * r * (12 - m_int)) / 12.0 if i == int(l_f) + 1 else (c_f - total) * r
        total += dep
    return dep


def calc_ddb(c: float, s: float, life_val: float, p: float, f: float) -> float:
    r = f / life_val
    if r >= 1.0:
        r = 1.0
        old = c if p == 1 else 0.0
    else:
        old = c * ((1.0 - r) ** (p - 1.0))
    nw = c * ((1.0 - r) ** p)
    d = old - s if nw < s else old - nw
    return max(0.0, d)


@register_fin("DDB")
def fn_ddb(
    cost: Any,
    salvage: Any,
    life: Any,
    period: Any,
    factor: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    c_val = to_float(cost)
    s_val = to_float(salvage)
    l_val = to_float(life)
    p_val = to_float(period)
    f_val = to_float(opt(factor, 2.0))
    for val in (c_val, s_val, l_val, p_val, f_val):
        if is_error(val):
            return val
    c_f, s_f, l_f, p_f, f_f = (
        float(c_val),
        float(s_val),
        float(l_val),
        float(p_val),
        float(f_val),
    )
    if c_f < 0 or s_f < 0 or l_f <= 0 or p_f <= 0 or f_f <= 0 or p_f > l_f:
        return NUM
    return calc_ddb(c_f, s_f, l_f, p_f, f_f)


def vdb_amounts(
    c: float, s: float, life_val: float, n: int, f: float, no_switch: bool
) -> list[float]:
    rate = min(f / life_val, 1.0)
    out: list[float] = []
    book = c
    line = 0.0
    for k in range(1, n + 1):
        d = max(0.0, min(book * rate, book - s))
        if not no_switch and line == 0.0:
            sl = (book - s) / (life_val - (k - 1))
            if sl > d:
                line = sl
        if line != 0.0:
            d = line
        out.append(d)
        book -= d
    return out


@register_fin("VDB")
def fn_vdb(
    cost: Any,
    salvage: Any,
    life: Any,
    start_period: Any,
    end_period: Any,
    factor: Any = None,
    no_switch: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    c_val = to_float(cost)
    s_val = to_float(salvage)
    l_val = to_float(life)
    a_val = to_float(start_period)
    b_val = to_float(end_period)
    f_val = to_float(opt(factor, 2.0))
    ns_bool = bool(opt(no_switch, False))
    for val in (c_val, s_val, l_val, a_val, b_val, f_val):
        if is_error(val):
            return val
    c_f, s_f, l_f, a_f, b_f, f_f = (
        float(c_val),
        float(s_val),
        float(l_val),
        float(a_val),
        float(b_val),
        float(f_val),
    )
    if c_f < 0 or s_f < 0 or l_f <= 0 or a_f < 0 or b_f < a_f or b_f > l_f or f_f <= 0:
        return NUM

    # Snap values very close to integer
    if abs(a_f - round(a_f)) < 1e-12:
        a_f = float(round(a_f))
    if abs(b_f - round(b_f)) < 1e-12:
        b_f = float(round(b_f))

    amounts = vdb_amounts(c_f, s_f, l_f, math.ceil(b_f), f_f, ns_bool)
    v = 0.0
    for k in range(int(math.floor(a_f)) + 1, len(amounts) + 1):
        share = min(b_f, float(k)) - max(a_f, float(k - 1))
        if share > 0:
            v += share * amounts[k - 1]
    return v


@register_fin("AMORLINC")
def fn_amorlinc(
    cost: Any,
    date_purchased: Any,
    first_period: Any,
    salvage: Any,
    period: Any,
    rate: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    c_val = to_float(cost)
    d0_val = to_float(date_purchased)
    f_val = to_float(first_period)
    s_val = to_float(salvage)
    p_val = to_float(period)
    r_val = to_float(rate)
    b_val = to_float(opt(basis, 0))
    for val in (c_val, d0_val, f_val, s_val, p_val, r_val, b_val):
        if is_error(val):
            return val
    c_f, s_f, r_f = float(c_val), float(s_val), float(r_val)
    p_int, b_int = int(float(p_val)), int(float(b_val))
    if r_f <= 0 or s_f > c_f or c_f <= 0 or b_int == 2 or b_int < 0 or b_int > 4:
        return NUM

    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(float(d0_val), float(f_val), b_int, date1904)
    if is_error(yf):
        return yf
    assert isinstance(yf, float)
    one = c_f * r_f
    delta = c_f - s_f
    r0 = yf * r_f * c_f
    full = int((c_f - s_f - r0) / one)
    if p_int == 0:
        return r0
    if p_int <= full:
        return one
    if p_int == full + 1:
        return delta - one * full - r0
    return 0.0


@register_fin("AMORDEGRC")
def fn_amordegrc(
    cost: Any,
    date_purchased: Any,
    first_period: Any,
    salvage: Any,
    period: Any,
    rate: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    c_val = to_float(cost)
    d0_val = to_float(date_purchased)
    f_val = to_float(first_period)
    s_val = to_float(salvage)
    p_val = to_float(period)
    r_val = to_float(rate)
    b_val = to_float(opt(basis, 0))
    for val in (c_val, d0_val, f_val, s_val, p_val, r_val, b_val):
        if is_error(val):
            return val
    c_f, s_f, r_f = float(c_val), float(s_val), float(r_val)
    p_int, b_int = int(float(p_val)), int(float(b_val))
    if r_f <= 0 or c_f <= 0 or s_f > c_f or b_int == 2 or b_int < 0 or b_int > 4:
        return NUM

    use = 1.0 / r_f
    coeff = 1.0 if use < 3.0 else 1.5 if use < 5.0 else 2.0 if use <= 6.0 else 2.5
    r = r_f * coeff

    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(float(d0_val), float(f_val), b_int, date1904)
    if is_error(yf):
        return yf
    assert isinstance(yf, float)

    nr = round(yf * r * c_f)
    if p_int == 0:
        return float(nr)
    c_f -= nr
    rest = c_f - s_f
    for n in range(p_int):
        nr = round(r * c_f)
        rest -= nr
        if rest < 0:
            rem = p_int - n
            if rem in (0, 1):
                return float(round(c_f * 0.5))
            return 0.0
        c_f -= nr
    return float(nr)
