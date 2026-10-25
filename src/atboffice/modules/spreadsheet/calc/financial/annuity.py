"""Worksheet annuity and loan amortization calculation functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NUM, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import opt, register_fin, to_float


def calc_pv(r: float, n: float, p: float, f: float = 0.0, t: int = 0) -> float:
    """Calculate present value."""
    if r == 0:
        return -(p * n + f)
    term = (1.0 + r) ** n
    return -(f + p * (1.0 + r * t) * (term - 1.0) / r) / term


def calc_fv(r: float, n: float, p: float, v: float = 0.0, t: int = 0) -> float:
    """Calculate future value."""
    if r == 0:
        return -(v + p * n)
    term = (1.0 + r) ** n
    return -(v * term + p * (1.0 + r * t) * (term - 1.0) / r)


def calc_pmt(r: float, n: float, v: float, f: float = 0.0, t: int = 0) -> float | ExcelError:
    """Calculate periodic payment for an annuity."""
    if n == 0:
        return NUM
    if r == 0:
        return -(v + f) / n
    term = (1.0 + r) ** n
    denom = (1.0 + r * t) * (term - 1.0)
    if denom == 0:
        return NUM
    return -(r * (f + v * term)) / denom


def calc_ipmt(
    r: float, per: int, n: float, v: float, f: float = 0.0, t: int = 0
) -> float | ExcelError:
    """Calculate interest payment for an investment for a given period."""
    if per < 1 or per > n:
        return NUM
    p = calc_pmt(r, n, v, f, t)
    if is_error(p):
        return p
    assert isinstance(p, float)
    if per == 1:
        interest_base = 0.0 if t == 1 else -v
    else:
        if t == 1:
            interest_base = calc_fv(r, per - 2, p, v, 1) - p
        else:
            interest_base = calc_fv(r, per - 1, p, v, 0)
    return interest_base * r


@register_fin("PV")
def fn_pv(
    r: Any,
    n: Any,
    p: Any,
    f: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    n_val = to_float(n)
    p_val = to_float(p)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, n_val, p_val, f_val):
        if is_error(val):
            return val
    try:
        return calc_pv(float(r_val), float(n_val), float(p_val), float(f_val), t_val)
    except Exception:
        return NUM


@register_fin("FV")
def fn_fv(
    r: Any,
    n: Any,
    p: Any,
    v: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    n_val = to_float(n)
    p_val = to_float(p)
    v_val = to_float(opt(v, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, n_val, p_val, v_val):
        if is_error(val):
            return val
    try:
        return calc_fv(float(r_val), float(n_val), float(p_val), float(v_val), t_val)
    except Exception:
        return NUM


@register_fin("PMT")
def fn_pmt(
    r: Any,
    n: Any,
    v: Any,
    f: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    n_val = to_float(n)
    v_val = to_float(v)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, n_val, v_val, f_val):
        if is_error(val):
            return val
    try:
        return calc_pmt(float(r_val), float(n_val), float(v_val), float(f_val), t_val)
    except Exception:
        return NUM


@register_fin("NPER")
def fn_nper(
    r: Any,
    p: Any,
    v: Any,
    f: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    p_val = to_float(p)
    v_val = to_float(v)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, p_val, v_val, f_val):
        if is_error(val):
            return val
    r_f, p_f, v_f, f_f = float(r_val), float(p_val), float(v_val), float(f_val)
    if r_f == 0:
        if p_f == 0:
            return NUM
        return -(v_f + f_f) / p_f
    a = p_f * (1.0 + r_f * t_val) - f_f * r_f
    b = p_f * (1.0 + r_f * t_val) + v_f * r_f
    if b == 0 or a / b <= 0 or (1.0 + r_f) <= 0:
        return NUM
    try:
        return math.log(a / b) / math.log(1.0 + r_f)
    except Exception:
        return NUM


@register_fin("RATE")
def fn_rate(
    n: Any,
    p: Any,
    v: Any,
    f: Any = None,
    t: Any = None,
    guess: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    n_val = to_float(n)
    p_val = to_float(p)
    v_val = to_float(v)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    g_val = to_float(opt(guess, 0.1))
    for val in (n_val, p_val, v_val, f_val, g_val):
        if is_error(val):
            return val
    n_f, p_f, v_f, f_f, rate_val = (
        float(n_val),
        float(p_val),
        float(v_val),
        float(f_val),
        float(g_val),
    )

    def func(r: float) -> float:
        if abs(r) < 1e-12:
            return v_f + p_f * n_f + f_f
        term = (1.0 + r) ** n_f
        return v_f * term + p_f * (1.0 + r * t_val) * (term - 1.0) / r + f_f

    # Newton-Raphson
    for _ in range(100):
        try:
            y = func(rate_val)
            h = 1e-7 * max(1.0, abs(rate_val))
            d = (func(rate_val + h) - func(rate_val - h)) / (2.0 * h)
            if not math.isfinite(d) or d == 0:
                break
            new_r = rate_val - y / d
            if not math.isfinite(new_r):
                break
            if abs(new_r - rate_val) < 1e-12:
                return new_r
            rate_val = new_r
            if rate_val <= -1.0:
                rate_val = -0.999999
        except Exception:
            break

    try:
        if abs(func(rate_val)) < 1e-7:
            return rate_val
    except Exception:
        pass

    # Bisection fallback
    lo, hi = -0.9999, 10.0
    try:
        flo, fhi = func(lo), func(hi)
        if flo * fhi <= 0:
            for _ in range(200):
                mid = (lo + hi) / 2.0
                fmid = func(mid)
                if abs(fmid) < 1e-10:
                    return mid
                if (fmid < 0) == (flo < 0):
                    lo, flo = mid, fmid
                else:
                    hi = mid
            return (lo + hi) / 2.0
    except Exception:
        pass

    return NUM


@register_fin("IPMT")
def fn_ipmt(
    r: Any,
    per: Any,
    n: Any,
    v: Any,
    f: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    per_val = to_float(per)
    n_val = to_float(n)
    v_val = to_float(v)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, per_val, n_val, v_val, f_val):
        if is_error(val):
            return val
    try:
        return calc_ipmt(
            float(r_val),
            int(float(per_val)),
            float(n_val),
            float(v_val),
            float(f_val),
            t_val,
        )
    except Exception:
        return NUM


@register_fin("PPMT")
def fn_ppmt(
    r: Any,
    per: Any,
    n: Any,
    v: Any,
    f: Any = None,
    t: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    per_val = to_float(per)
    n_val = to_float(n)
    v_val = to_float(v)
    f_val = to_float(opt(f, 0.0))
    t_val = 1 if to_float(opt(t, 0.0)) else 0
    for val in (r_val, per_val, n_val, v_val, f_val):
        if is_error(val):
            return val
    per_int = int(float(per_val))
    if per_int < 1 or per_int > float(n_val):
        return NUM
    try:
        p = calc_pmt(float(r_val), float(n_val), float(v_val), float(f_val), t_val)
        ip = calc_ipmt(
            float(r_val),
            per_int,
            float(n_val),
            float(v_val),
            float(f_val),
            t_val,
        )
        if is_error(p) or is_error(ip):
            return NUM
        assert isinstance(p, float) and isinstance(ip, float)
        return p - ip
    except Exception:
        return NUM


@register_fin("CUMIPMT")
def fn_cumipmt(
    r: Any,
    n: Any,
    v: Any,
    s: Any,
    e: Any,
    t: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    n_val = to_float(n)
    v_val = to_float(v)
    s_val = to_float(s)
    e_val = to_float(e)
    t_val = to_float(t)
    for val in (r_val, n_val, v_val, s_val, e_val, t_val):
        if is_error(val):
            return val
    r_f, n_f, v_f = float(r_val), float(n_val), float(v_val)
    s_int, e_int, t_int = int(float(s_val)), int(float(e_val)), int(float(t_val))
    if (
        r_f <= 0
        or n_f <= 0
        or v_f <= 0
        or s_int < 1
        or e_int < 1
        or s_int > e_int
        or e_int > n_f
        or t_int not in (0, 1)
    ):
        return NUM
    tot = 0.0
    for k in range(s_int, e_int + 1):
        ip = calc_ipmt(r_f, k, n_f, v_f, 0.0, t_int)
        if is_error(ip):
            return ip
        assert isinstance(ip, float)
        tot += ip
    return tot


@register_fin("CUMPRINC")
def fn_cumprinc(
    r: Any,
    n: Any,
    v: Any,
    s: Any,
    e: Any,
    t: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    n_val = to_float(n)
    v_val = to_float(v)
    s_val = to_float(s)
    e_val = to_float(e)
    t_val = to_float(t)
    for val in (r_val, n_val, v_val, s_val, e_val, t_val):
        if is_error(val):
            return val
    r_f, n_f, v_f = float(r_val), float(n_val), float(v_val)
    s_int, e_int, t_int = int(float(s_val)), int(float(e_val)), int(float(t_val))
    if (
        r_f <= 0
        or n_f <= 0
        or v_f <= 0
        or s_int < 1
        or e_int < 1
        or s_int > e_int
        or e_int > n_f
        or t_int not in (0, 1)
    ):
        return NUM
    tot = 0.0
    for k in range(s_int, e_int + 1):
        p = calc_pmt(r_f, n_f, v_f, 0.0, t_int)
        ip = calc_ipmt(r_f, k, n_f, v_f, 0.0, t_int)
        if is_error(p) or is_error(ip):
            return NUM
        assert isinstance(p, float) and isinstance(ip, float)
        tot += p - ip
    return tot


@register_fin("ISPMT")
def fn_ispmt(
    r: Any,
    per: Any,
    n: Any,
    v: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    r_val = to_float(r)
    per_val = to_float(per)
    n_val = to_float(n)
    v_val = to_float(v)
    for val in (r_val, per_val, n_val, v_val):
        if is_error(val):
            return val
    n_f = float(n_val)
    if n_f == 0:
        return DIV0
    return float(v_val) * float(r_val) * (float(per_val) / n_f - 1.0)
