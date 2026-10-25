"""Worksheet bond, security, and treasury bill calculation functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import (
    date_to_serial,
    days360,
    days_in_month,
    is_leap_year,
    serial_to_parts,
    yearfrac,
)
from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import opt, register_fin, to_float


def coupon_date(mat: int, months: int, date1904: bool = False) -> int:
    p = serial_to_parts(mat, date1904)
    y, m, d = p["y"], p["m"], p["d"]
    last_d = days_in_month(y, m)
    eom = d == last_d
    y += math.floor((m - 1 + months) / 12)
    m = ((((m - 1 + months) % 12) + 12) % 12) + 1
    new_last_d = days_in_month(y, m)
    d = new_last_d if eom else min(d, new_last_d)
    res = date_to_serial(y, m, d, date1904)
    if is_error(res):
        return mat
    return int(res)


def pcd_data(
    settlement: int, maturity: int, freq: int, date1904: bool = False
) -> dict[str, Any]:
    step = 12 // freq
    years = math.floor((maturity - settlement) / 366.0)
    k = -years * freq
    d = coupon_date(maturity, k * step, date1904)
    while d <= settlement:
        k += 1
        d = coupon_date(maturity, k * step, date1904)
    while d > settlement:
        k -= 1
        d = coupon_date(maturity, k * step, date1904)
    ncd = coupon_date(maturity, (k + 1) * step, date1904)
    return {"pcd": d, "ncd": ncd, "k": k}


def validate_bond_args(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> dict[str, int] | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    f_val = to_float(frequency)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, f_val, b_val):
        if is_error(v):
            return v
    s_int = int(math.floor(float(s_val)))
    m_int = int(math.floor(float(m_val)))
    f_int = int(float(f_val))
    b_int = int(float(b_val))
    if s_int >= m_int or f_int not in (1, 2, 4) or b_int < 0 or b_int > 4:
        return NUM
    return {"set": s_int, "mat": m_int, "freq": f_int, "basis": b_int}


def day_count(a: int, b: int, basis: int, date1904: bool = False) -> float:
    if basis == 0:
        return float(days360(a, b, False, date1904))
    if basis == 4:
        return float(days360(a, b, True, date1904))
    return float(b - a)


def calc_coupdays(b: dict[str, int], date1904: bool = False) -> float:
    if b["basis"] == 1:
        c = pcd_data(b["set"], b["mat"], b["freq"], date1904)
        return float(c["ncd"] - c["pcd"])
    return (365.0 if b["basis"] == 3 else 360.0) / b["freq"]


def calc_coupdaybs(b: dict[str, int], date1904: bool = False) -> float:
    c = pcd_data(b["set"], b["mat"], b["freq"], date1904)
    return day_count(c["pcd"], b["set"], b["basis"], date1904)


def calc_coupdaysnc(b: dict[str, int], date1904: bool = False) -> float:
    c = pcd_data(b["set"], b["mat"], b["freq"], date1904)
    if b["basis"] in (0, 4):
        return calc_coupdays(b, date1904) - calc_coupdaybs(b, date1904)
    return float(c["ncd"] - b["set"])


def calc_coupnum(b: dict[str, int], date1904: bool = False) -> int:
    c = pcd_data(b["set"], b["mat"], b["freq"], date1904)
    return -c["k"]


@register_fin("COUPDAYS")
def fn_coupdays(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return calc_coupdays(b, date1904)


@register_fin("COUPDAYBS")
def fn_coupdaybs(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return calc_coupdaybs(b, date1904)


@register_fin("COUPDAYSNC")
def fn_coupdaysnc(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return calc_coupdaysnc(b, date1904)


@register_fin("COUPNCD")
def fn_coupncd(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return pcd_data(b["set"], b["mat"], b["freq"], date1904)["ncd"]


@register_fin("COUPPCD")
def fn_couppcd(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return pcd_data(b["set"], b["mat"], b["freq"], date1904)["pcd"]


@register_fin("COUPNUM")
def fn_coupnum(
    settlement: Any,
    maturity: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    date1904 = ctx.date1904 if ctx else False
    return calc_coupnum(b, date1904)


def calc_price(
    b: dict[str, int],
    rate: float,
    yld: float,
    redemption: float,
    date1904: bool = False,
) -> float:
    ed = calc_coupdays(b, date1904)
    a = calc_coupdaybs(b, date1904)
    dsc = calc_coupdaysnc(b, date1904)
    n = calc_coupnum(b, date1904)
    f = b["freq"]
    cpn = (100.0 * rate) / f
    if n == 1:
        return (redemption + cpn) / (1.0 + (dsc / ed) * (yld / f)) - cpn * (a / ed)
    p = redemption / ((1.0 + yld / f) ** (n - 1 + dsc / ed))
    for k in range(1, n + 1):
        p += cpn / ((1.0 + yld / f) ** (k - 1 + dsc / ed))
    return p - cpn * (a / ed)


@register_fin("PRICE")
def fn_price(
    settlement: Any,
    maturity: Any,
    rate: Any,
    yld: Any,
    redemption: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    r_val = to_float(rate)
    y_val = to_float(yld)
    red_val = to_float(redemption)
    for v in (r_val, y_val, red_val):
        if is_error(v):
            return v
    r_f, y_f, red_f = float(r_val), float(y_val), float(red_val)
    if r_f < 0 or y_f < 0 or red_f <= 0:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    try:
        return calc_price(b, r_f, y_f, red_f, date1904)
    except Exception:
        return NUM


@register_fin("YIELD")
def fn_yield(
    settlement: Any,
    maturity: Any,
    rate: Any,
    pr: Any,
    redemption: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    r_val = to_float(rate)
    pr_val = to_float(pr)
    red_val = to_float(redemption)
    for v in (r_val, pr_val, red_val):
        if is_error(v):
            return v
    r_f, pr_f, red_f = float(r_val), float(pr_val), float(red_val)
    if r_f < 0 or pr_f <= 0 or red_f <= 0:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    n = calc_coupnum(b, date1904)
    if n == 1:
        ed = calc_coupdays(b, date1904)
        a = calc_coupdaybs(b, date1904)
        dsr = ed - a
        f = b["freq"]
        if dsr == 0 or (pr_f / 100.0 + (a / ed) * r_f / f) == 0:
            return NUM
        num = red_f / 100.0 + r_f / f - (pr_f / 100.0 + (a / ed) * r_f / f)
        den = pr_f / 100.0 + (a / ed) * r_f / f
        return (num / den) * ((f * ed) / dsr)

    y = r_f or 0.05
    for _ in range(200):
        try:
            pv0 = calc_price(b, r_f, y, red_f, date1904) - pr_f
            h = 1e-7
            d = (
                calc_price(b, r_f, y + h, red_f, date1904)
                - calc_price(b, r_f, y - h, red_f, date1904)
            ) / (2.0 * h)
            if not math.isfinite(d) or d == 0:
                break
            ny = y - pv0 / d
            if not math.isfinite(ny):
                break
            if abs(ny - y) < 1e-12:
                return ny
            y = ny
        except Exception:
            break

    try:
        if abs(calc_price(b, r_f, y, red_f, date1904) - pr_f) < 1e-7:
            return y
    except Exception:
        pass
    return NUM


def calc_duration(
    b: dict[str, int], coupon: float, yld: float, date1904: bool = False
) -> float:
    ed = calc_coupdays(b, date1904)
    dsc = calc_coupdaysnc(b, date1904)
    n = calc_coupnum(b, date1904)
    f = b["freq"]
    c = (100.0 * coupon) / f
    y = yld / f
    num = 0.0
    den = 0.0
    for k in range(1, n + 1):
        t = k - 1 + dsc / ed
        cf = c + (100.0 if k == n else 0.0)
        pvk = cf / ((1.0 + y) ** t)
        num += t * pvk
        den += pvk
    if den == 0 or f == 0:
        return 0.0
    return num / den / f


@register_fin("DURATION")
def fn_duration(
    settlement: Any,
    maturity: Any,
    coupon: Any,
    yld: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    c_val = to_float(coupon)
    y_val = to_float(yld)
    for v in (c_val, y_val):
        if is_error(v):
            return v
    c_f, y_f = float(c_val), float(y_val)
    if c_f < 0 or y_f < 0:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    try:
        return calc_duration(b, c_f, y_f, date1904)
    except Exception:
        return NUM


@register_fin("MDURATION")
def fn_mduration(
    settlement: Any,
    maturity: Any,
    coupon: Any,
    yld: Any,
    frequency: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    dur = fn_duration(settlement, maturity, coupon, yld, frequency, basis, ctx)
    if is_error(dur):
        return dur
    assert isinstance(dur, float)
    b = validate_bond_args(settlement, maturity, frequency, basis, ctx)
    if is_error(b):
        return b
    assert isinstance(b, dict)
    y_f = float(to_float(yld))
    return dur / (1.0 + y_f / b["freq"])


@register_fin("ACCRINT")
def fn_accrint(
    issue: Any,
    first_interest: Any,
    settlement: Any,
    rate: Any,
    par: Any = None,
    frequency: Any = None,
    basis: Any = None,
    calc_method: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    iss_val = to_float(issue)
    first_val = to_float(first_interest)
    set_val = to_float(settlement)
    r_val = to_float(rate)
    p_val = to_float(opt(par, 1000.0))
    fr_val = to_float(opt(frequency, 1))
    b_val = to_float(opt(basis, 0))
    for v in (iss_val, first_val, set_val, r_val, p_val, fr_val, b_val):
        if is_error(v):
            return v
    iss_f, set_f, r_f, p_f = (
        float(iss_val),
        float(set_val),
        float(r_val),
        float(p_val),
    )
    fr_int, b_int = int(float(fr_val)), int(float(b_val))
    if (
        r_f <= 0
        or p_f <= 0
        or fr_int not in (1, 2, 4)
        or b_int < 0
        or b_int > 4
        or iss_f >= set_f
    ):
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(iss_f, set_f, b_int, date1904)
    if is_error(yf):
        return yf
    assert isinstance(yf, float)
    return p_f * r_f * yf


@register_fin("ACCRINTM")
def fn_accrintm(
    issue: Any,
    settlement: Any,
    rate: Any,
    par: Any = None,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    iss_val = to_float(issue)
    set_val = to_float(settlement)
    r_val = to_float(rate)
    p_val = to_float(opt(par, 1000.0))
    b_val = to_float(opt(basis, 0))
    for v in (iss_val, set_val, r_val, p_val, b_val):
        if is_error(v):
            return v
    iss_f, set_f, r_f, p_f = (
        float(iss_val),
        float(set_val),
        float(r_val),
        float(p_val),
    )
    b_int = int(float(b_val))
    if r_f <= 0 or p_f <= 0 or b_int < 0 or b_int > 4 or iss_f >= set_f:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(iss_f, set_f, b_int, date1904)
    if is_error(yf):
        return yf
    assert isinstance(yf, float)
    return p_f * r_f * yf


@register_fin("DISC")
def fn_disc(
    settlement: Any,
    maturity: Any,
    pr: Any,
    redemption: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    pr_val = to_float(pr)
    red_val = to_float(redemption)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, pr_val, red_val, b_val):
        if is_error(v):
            return v
    s_f, m_f, pr_f, red_f = (
        float(s_val),
        float(m_val),
        float(pr_val),
        float(red_val),
    )
    b_int = int(float(b_val))
    if s_f >= m_f or pr_f <= 0 or red_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(s_f, m_f, b_int, date1904)
    if is_error(yf) or yf == 0:
        return NUM
    assert isinstance(yf, float)
    return (red_f - pr_f) / red_f / yf


@register_fin("INTRATE")
def fn_intrate(
    settlement: Any,
    maturity: Any,
    investment: Any,
    redemption: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    inv_val = to_float(investment)
    red_val = to_float(redemption)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, inv_val, red_val, b_val):
        if is_error(v):
            return v
    s_f, m_f, inv_f, red_f = (
        float(s_val),
        float(m_val),
        float(inv_val),
        float(red_val),
    )
    b_int = int(float(b_val))
    if s_f >= m_f or inv_f <= 0 or red_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(s_f, m_f, b_int, date1904)
    if is_error(yf) or yf == 0:
        return NUM
    assert isinstance(yf, float)
    return (red_f - inv_f) / inv_f / yf


@register_fin("RECEIVED")
def fn_received(
    settlement: Any,
    maturity: Any,
    investment: Any,
    discount: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    inv_val = to_float(investment)
    dsc_val = to_float(discount)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, inv_val, dsc_val, b_val):
        if is_error(v):
            return v
    s_f, m_f, inv_f, dsc_f = (
        float(s_val),
        float(m_val),
        float(inv_val),
        float(dsc_val),
    )
    b_int = int(float(b_val))
    if s_f >= m_f or inv_f <= 0 or dsc_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(s_f, m_f, b_int, date1904)
    if is_error(yf):
        return NUM
    assert isinstance(yf, float)
    r = 1.0 - dsc_f * yf
    if r <= 0:
        return NUM
    return inv_f / r


@register_fin("PRICEDISC")
def fn_pricedisc(
    settlement: Any,
    maturity: Any,
    discount: Any,
    redemption: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    dsc_val = to_float(discount)
    red_val = to_float(redemption)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, dsc_val, red_val, b_val):
        if is_error(v):
            return v
    s_f, m_f, dsc_f, red_f = (
        float(s_val),
        float(m_val),
        float(dsc_val),
        float(red_val),
    )
    b_int = int(float(b_val))
    if s_f >= m_f or dsc_f <= 0 or red_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(s_f, m_f, b_int, date1904)
    if is_error(yf):
        return NUM
    assert isinstance(yf, float)
    return red_f * (1.0 - dsc_f * yf)


@register_fin("YIELDDISC")
def fn_yielddisc(
    settlement: Any,
    maturity: Any,
    pr: Any,
    redemption: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    pr_val = to_float(pr)
    red_val = to_float(redemption)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, pr_val, red_val, b_val):
        if is_error(v):
            return v
    s_f, m_f, pr_f, red_f = (
        float(s_val),
        float(m_val),
        float(pr_val),
        float(red_val),
    )
    b_int = int(float(b_val))
    if s_f >= m_f or pr_f <= 0 or red_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    yf = yearfrac(s_f, m_f, b_int, date1904)
    if is_error(yf) or yf == 0:
        return NUM
    assert isinstance(yf, float)
    return (red_f - pr_f) / pr_f / yf


def year_days(y: int, basis: int) -> float:
    if basis == 1:
        return 366.0 if is_leap_year(y) else 365.0
    return 365.0 if basis == 3 else 360.0


@register_fin("PRICEMAT")
def fn_pricemat(
    settlement: Any,
    maturity: Any,
    issue: Any,
    rate: Any,
    yld: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    iss_val = to_float(issue)
    r_val = to_float(rate)
    y_val = to_float(yld)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, iss_val, r_val, y_val, b_val):
        if is_error(v):
            return v
    s_int, m_int, iss_int = (
        int(math.floor(float(s_val))),
        int(math.floor(float(m_val))),
        int(math.floor(float(iss_val))),
    )
    r_f, y_f = float(r_val), float(y_val)
    b_int = int(float(b_val))
    if s_int >= m_int or r_f < 0 or y_f < 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    b_days = year_days(serial_to_parts(s_int, date1904)["y"], b_int)
    dim = day_count(iss_int, m_int, b_int, date1904)
    dsm = day_count(s_int, m_int, b_int, date1904)
    a = day_count(iss_int, s_int, b_int, date1904)
    return (
        (100.0 + (dim / b_days) * r_f * 100.0) / (1.0 + (dsm / b_days) * y_f)
        - (a / b_days) * r_f * 100.0
    )


@register_fin("YIELDMAT")
def fn_yieldmat(
    settlement: Any,
    maturity: Any,
    issue: Any,
    rate: Any,
    pr: Any,
    basis: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    iss_val = to_float(issue)
    r_val = to_float(rate)
    pr_val = to_float(pr)
    b_val = to_float(opt(basis, 0))
    for v in (s_val, m_val, iss_val, r_val, pr_val, b_val):
        if is_error(v):
            return v
    s_int, m_int, iss_int = (
        int(math.floor(float(s_val))),
        int(math.floor(float(m_val))),
        int(math.floor(float(iss_val))),
    )
    r_f, pr_f = float(r_val), float(pr_val)
    b_int = int(float(b_val))
    if s_int >= m_int or r_f < 0 or pr_f <= 0 or b_int < 0 or b_int > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    b_days = year_days(serial_to_parts(s_int, date1904)["y"], b_int)
    dim = day_count(iss_int, m_int, b_int, date1904)
    dsm = day_count(s_int, m_int, b_int, date1904)
    a = day_count(iss_int, s_int, b_int, date1904)
    t = pr_f / 100.0 + (a / b_days) * r_f
    if t == 0 or dsm == 0:
        return NUM
    return ((1.0 + (dim / b_days) * r_f - t) / t) * (b_days / dsm)


def tbill_days(s: float, m: float) -> int | None:
    s_int = int(math.floor(s))
    m_int = int(math.floor(m))
    d = m_int - s_int
    if s_int >= m_int or d > 366:
        return None
    return d


@register_fin("TBILLPRICE")
def fn_tbillprice(
    settlement: Any, maturity: Any, discount: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    dsc_val = to_float(discount)
    for v in (s_val, m_val, dsc_val):
        if is_error(v):
            return v
    d = tbill_days(float(s_val), float(m_val))
    dsc_f = float(dsc_val)
    if d is None or dsc_f <= 0:
        return NUM
    p = 100.0 * (1.0 - (dsc_f * d) / 360.0)
    return NUM if p <= 0 else p


@register_fin("TBILLYIELD")
def fn_tbillyield(
    settlement: Any, maturity: Any, pr: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    pr_val = to_float(pr)
    for v in (s_val, m_val, pr_val):
        if is_error(v):
            return v
    d = tbill_days(float(s_val), float(m_val))
    pr_f = float(pr_val)
    if d is None or pr_f <= 0:
        return NUM
    return ((100.0 - pr_f) / pr_f) * (360.0 / d)


@register_fin("TBILLEQ")
def fn_tbilleq(
    settlement: Any, maturity: Any, discount: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    s_val = to_float(settlement)
    m_val = to_float(maturity)
    dsc_val = to_float(discount)
    for v in (s_val, m_val, dsc_val):
        if is_error(v):
            return v
    d = tbill_days(float(s_val), float(m_val))
    dsc_f = float(dsc_val)
    if d is None or dsc_f <= 0:
        return NUM
    if d <= 182:
        denom = 360.0 - dsc_f * d
        if denom == 0:
            return NUM
        return (365.0 * dsc_f) / denom
    pr = 100.0 * (1.0 - (dsc_f * d) / 360.0)
    if pr == 0:
        return NUM
    a = d / (2.0 * 365.0) - 0.25
    b = d / 365.0
    c = (pr - 100.0) / pr
    disc = b * b - 4.0 * a * c
    if disc < 0 or a == 0:
        return NUM
    return (-b + math.sqrt(disc)) / (2.0 * a)


# Stubs for odd coupon bonds
@register_fin("ODDFPRICE")
@register_fin("ODDFYIELD")
@register_fin("ODDLPRICE")
@register_fin("ODDLYIELD")
def fn_odd_bonds(*args: Any, ctx: EvalContext | None = None) -> float:
    return 0.0
