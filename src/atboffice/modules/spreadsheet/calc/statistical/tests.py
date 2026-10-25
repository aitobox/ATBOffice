"""Statistical hypothesis tests and distribution functions (Chi-sq, T, F, Z)."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.statistical.common import (
    beta_i,
    collect_stat_numbers,
    gamma_p,
    gamma_q,
    invert_cdf,
    mean,
    norm_cdf,
    opt,
    register_stat,
    to_float,
)


# Chi-Square
def chi_cdf(x: float, df: float) -> float:
    return gamma_p(df / 2.0, x / 2.0)


def chi_tail(x: float, df: float) -> float:
    return gamma_q(df / 2.0, x / 2.0)


@register_stat("CHISQ.DIST")
def fn_chisq_dist(
    x: Any, deg_freedom: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    df_val = to_float(deg_freedom)
    for v in (x_val, df_val):
        if is_error(v):
            return v
    x_f, df = float(x_val), float(df_val)
    if x_f < 0 or df < 1:
        return NUM
    if bool(cumulative):
        return chi_cdf(x_f, df)
    return (
        (x_f ** (df / 2.0 - 1.0))
        * math.exp(-x_f / 2.0)
        / ((2.0 ** (df / 2.0)) * math.gamma(df / 2.0))
    )


@register_stat("CHIDIST")
@register_stat("CHISQ.DIST.RT")
def fn_chisq_dist_rt(
    x: Any, deg_freedom: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    df_val = to_float(deg_freedom)
    for v in (x_val, df_val):
        if is_error(v):
            return v
    x_f, df = float(x_val), float(df_val)
    if x_f < 0 or df < 1:
        return NUM
    return chi_tail(x_f, df)


@register_stat("CHISQ.INV")
def fn_chisq_inv(
    probability: Any, deg_freedom: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    df_val = to_float(deg_freedom)
    for v in (p_val, df_val):
        if is_error(v):
            return v
    p, df = float(p_val), float(df_val)
    if p <= 0 or p >= 1 or df < 1:
        return NUM
    return invert_cdf(lambda y: chi_cdf(y, df), p, 0.0, 1000.0)


@register_stat("CHIINV")
@register_stat("CHISQ.INV.RT")
def fn_chisq_inv_rt(
    probability: Any, deg_freedom: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    df_val = to_float(deg_freedom)
    for v in (p_val, df_val):
        if is_error(v):
            return v
    p, df = float(p_val), float(df_val)
    if p <= 0 or p > 1 or df < 1:
        return NUM
    return invert_cdf(lambda y: 1.0 - chi_tail(y, df), 1.0 - p, 0.0, 1000.0)


@register_stat("CHITEST")
@register_stat("CHISQ.TEST")
def fn_chisq_test(
    actual_range: Any, expected_range: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    actual = collect_stat_numbers([actual_range], ctx, False)
    expected = collect_stat_numbers([expected_range], ctx, False)
    if is_error(actual):
        return actual
    if is_error(expected):
        return expected
    assert isinstance(actual, list) and isinstance(expected, list)
    if len(actual) != len(expected) or len(actual) < 2:
        return NUM
    stat = 0.0
    for a, e in zip(actual, expected):
        if e == 0:
            return DIV0
        stat += ((a - e) ** 2) / e
    df = len(actual) - 1
    return chi_tail(stat, df)


# Student's T
def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    tail = 0.5 * beta_i(x, df / 2.0, 0.5)
    return 1.0 - tail if t > 0 else tail


@register_stat("T.DIST")
def fn_t_dist(
    x: Any, deg_freedom: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    df_val = to_float(deg_freedom)
    for v in (x_val, df_val):
        if is_error(v):
            return v
    x_f, df = float(x_val), float(df_val)
    if df < 1:
        return NUM
    if bool(cumulative):
        return t_cdf(x_f, df)
    coeff = math.exp(math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0))
    return coeff / (math.sqrt(df * math.pi) * ((1.0 + (x_f * x_f) / df) ** ((df + 1.0) / 2.0)))


@register_stat("TDIST")
@register_stat("T.DIST.RT")
def fn_t_dist_rt(
    x: Any, deg_freedom: Any, tails: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    df_val = to_float(deg_freedom)
    for v in (x_val, df_val):
        if is_error(v):
            return v
    x_f, df = float(x_val), float(df_val)
    t_int = int(float(to_float(opt(tails, 1))))
    if df < 1 or t_int not in (1, 2) or x_f < 0:
        return NUM
    p = 1.0 - t_cdf(x_f, df)
    return p * t_int


@register_stat("T.DIST.2T")
def fn_t_dist_2t(x: Any, deg_freedom: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    df_val = to_float(deg_freedom)
    for v in (x_val, df_val):
        if is_error(v):
            return v
    x_f, df = float(x_val), float(df_val)
    if df < 1 or x_f < 0:
        return NUM
    return 2.0 * (1.0 - t_cdf(x_f, df))


@register_stat("T.INV")
def fn_t_inv(
    probability: Any, deg_freedom: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    df_val = to_float(deg_freedom)
    for v in (p_val, df_val):
        if is_error(v):
            return v
    p, df = float(p_val), float(df_val)
    if p <= 0 or p >= 1 or df < 1:
        return NUM
    if p == 0.5:
        return 0.0
    return invert_cdf(lambda y: t_cdf(y, df), p, -1000.0, 1000.0)


@register_stat("TINV")
@register_stat("T.INV.2T")
def fn_t_inv_2t(
    probability: Any, deg_freedom: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    df_val = to_float(deg_freedom)
    for v in (p_val, df_val):
        if is_error(v):
            return v
    p, df = float(p_val), float(df_val)
    if p <= 0 or p > 1 or df < 1:
        return NUM
    inv = fn_t_inv(1.0 - p / 2.0, df, ctx=ctx)
    if is_error(inv):
        return inv
    assert isinstance(inv, float)
    return abs(inv)


@register_stat("TTEST")
@register_stat("T.TEST")
def fn_t_test(
    array1: Any,
    array2: Any,
    tails: Any,
    type_val: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    t_int = int(float(to_float(tails)))
    ty_int = int(float(to_float(type_val)))
    if t_int not in (1, 2) or ty_int not in (1, 2, 3):
        return NUM
    n1 = collect_stat_numbers([array1], ctx, False)
    n2 = collect_stat_numbers([array2], ctx, False)
    if is_error(n1):
        return n1
    if is_error(n2):
        return n2
    assert isinstance(n1, list) and isinstance(n2, list)
    if len(n1) < 2 or len(n2) < 2:
        return NUM

    m1, m2 = mean(n1), mean(n2)
    from atboffice.modules.spreadsheet.calc.statistical.common import devsq

    if ty_int == 1:
        # Paired
        if len(n1) != len(n2):
            return NA
        diffs = [a - b for a, b in zip(n1, n2)]
        md = mean(diffs)
        vd = devsq(diffs) / (len(diffs) - 1.0)
        if vd == 0:
            return DIV0
        t_stat = md / math.sqrt(vd / len(diffs))
        df = len(diffs) - 1
    elif ty_int == 2:
        # Equal variance
        v1 = devsq(n1) / (len(n1) - 1.0)
        v2 = devsq(n2) / (len(n2) - 1.0)
        df = len(n1) + len(n2) - 2
        sp = ((len(n1) - 1.0) * v1 + (len(n2) - 1.0) * v2) / df
        if sp == 0:
            return DIV0
        t_stat = (m1 - m2) / math.sqrt(sp * (1.0 / len(n1) + 1.0 / len(n2)))
    else:
        # Unequal variance (Welch)
        v1 = (devsq(n1) / (len(n1) - 1.0)) / len(n1)
        v2 = (devsq(n2) / (len(n2) - 1.0)) / len(n2)
        if v1 + v2 == 0:
            return DIV0
        t_stat = (m1 - m2) / math.sqrt(v1 + v2)
        df = ((v1 + v2) ** 2) / ((v1**2) / (len(n1) - 1.0) + (v2**2) / (len(n2) - 1.0))

    prob = 1.0 - t_cdf(abs(t_stat), df)
    return prob * t_int


# F-Distribution
def f_cdf(x: float, d1: float, d2: float) -> float:
    return 0.0 if x <= 0 else beta_i((d1 * x) / (d1 * x + d2), d1 / 2.0, d2 / 2.0)


def f_tail(x: float, d1: float, d2: float) -> float:
    return 1.0 if x <= 0 else beta_i(d2 / (d1 * x + d2), d2 / 2.0, d1 / 2.0)


@register_stat("F.DIST")
def fn_f_dist(
    x: Any,
    deg1: Any,
    deg2: Any,
    cumulative: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    x_val = to_float(x)
    d1_val = to_float(deg1)
    d2_val = to_float(deg2)
    for v in (x_val, d1_val, d2_val):
        if is_error(v):
            return v
    x_f, d1, d2 = float(x_val), float(d1_val), float(d2_val)
    if x_f < 0 or d1 < 1 or d2 < 1:
        return NUM
    if bool(cumulative):
        return f_cdf(x_f, d1, d2)
    top = (d1 ** (d1 / 2.0)) * (d2 ** (d2 / 2.0)) * (x_f ** (d1 / 2.0 - 1.0))
    bottom = beta_i(1.0, d1 / 2.0, d2 / 2.0) * ((d1 * x_f + d2) ** ((d1 + d2) / 2.0))
    return top / bottom if bottom != 0 else NUM


@register_stat("FDIST")
@register_stat("F.DIST.RT")
def fn_f_dist_rt(
    x: Any, deg1: Any, deg2: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    d1_val = to_float(deg1)
    d2_val = to_float(deg2)
    for v in (x_val, d1_val, d2_val):
        if is_error(v):
            return v
    x_f, d1, d2 = float(x_val), float(d1_val), float(d2_val)
    if x_f < 0 or d1 < 1 or d2 < 1:
        return NUM
    return f_tail(x_f, d1, d2)


@register_stat("F.INV")
def fn_f_inv(
    probability: Any, deg1: Any, deg2: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    d1_val = to_float(deg1)
    d2_val = to_float(deg2)
    for v in (p_val, d1_val, d2_val):
        if is_error(v):
            return v
    p, d1, d2 = float(p_val), float(d1_val), float(d2_val)
    if p <= 0 or p >= 1 or d1 < 1 or d2 < 1:
        return NUM
    return invert_cdf(lambda y: f_cdf(y, d1, d2), p, 0.0, 1000.0)


@register_stat("FINV")
@register_stat("F.INV.RT")
def fn_f_inv_rt(
    probability: Any, deg1: Any, deg2: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    d1_val = to_float(deg1)
    d2_val = to_float(deg2)
    for v in (p_val, d1_val, d2_val):
        if is_error(v):
            return v
    p, d1, d2 = float(p_val), float(d1_val), float(d2_val)
    if p <= 0 or p > 1 or d1 < 1 or d2 < 1:
        return NUM
    return invert_cdf(lambda y: 1.0 - f_tail(y, d1, d2), 1.0 - p, 0.0, 1000.0)


@register_stat("FTEST")
@register_stat("F.TEST")
def fn_f_test(array1: Any, array2: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    n1 = collect_stat_numbers([array1], ctx, False)
    n2 = collect_stat_numbers([array2], ctx, False)
    if is_error(n1):
        return n1
    if is_error(n2):
        return n2
    assert isinstance(n1, list) and isinstance(n2, list)
    if len(n1) < 2 or len(n2) < 2:
        return DIV0
    from atboffice.modules.spreadsheet.calc.statistical.common import devsq

    v1 = devsq(n1) / (len(n1) - 1.0)
    v2 = devsq(n2) / (len(n2) - 1.0)
    if v1 == 0 or v2 == 0:
        return DIV0
    f_stat = v1 / v2 if v1 > v2 else v2 / v1
    df1 = len(n1) - 1 if v1 > v2 else len(n2) - 1
    df2 = len(n2) - 1 if v1 > v2 else len(n1) - 1
    p = f_tail(f_stat, df1, df2)
    return min(1.0, 2.0 * p)


# Z-Test
@register_stat("ZTEST")
@register_stat("Z.TEST")
def fn_z_test(
    array: Any, x: Any, sigma: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return NA
    m = mean(nums)
    n = len(nums)
    if sigma is not None and sigma != "":
        s_val = to_float(sigma)
        if is_error(s_val):
            return s_val
        s = float(s_val)
    else:
        from atboffice.modules.spreadsheet.calc.statistical.common import devsq

        if n < 2:
            return NUM
        s = math.sqrt(devsq(nums) / (n - 1.0))
    if s <= 0:
        return NUM
    z = (m - float(x_val)) / (s / math.sqrt(n))
    return 1.0 - norm_cdf(z)
