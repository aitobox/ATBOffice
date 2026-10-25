"""Regression, covariance, and linear trend worksheet functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import flatten_values
from atboffice.modules.spreadsheet.calc.statistical.common import (
    mean,
    opt,
    register_stat,
    to_float,
)


def extract_pairs(
    arr1: Any, arr2: Any, ctx: EvalContext | None = None
) -> tuple[list[float], list[float]] | ExcelError:
    f1 = flatten_values([arr1], ctx)
    f2 = flatten_values([arr2], ctx)
    if len(f1) != len(f2):
        return NA
    xs: list[float] = []
    ys: list[float] = []
    for a, b in zip(f1, f2):
        if is_error(a):
            return a
        if is_error(b):
            return b
        if isinstance(a, bool) or isinstance(b, bool):
            continue
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            xs.append(float(a))
            ys.append(float(b))
    if len(xs) < 2:
        return DIV0
    return (xs, ys)


def calc_lin_reg(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float, float] | ExcelError:
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return DIV0
    slope = sxy / sxx
    intercept = my - slope * mx
    return (slope, intercept, sxx, syy)


@register_stat("CORREL")
@register_stat("PEARSON")
def fn_correl(array1: Any, array2: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    pairs = extract_pairs(array1, array2, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return DIV0
    return sxy / math.sqrt(sxx * syy)


@register_stat("RSQ")
def fn_rsq(array1: Any, array2: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    r = fn_correl(array1, array2, ctx=ctx)
    if is_error(r):
        return r
    assert isinstance(r, float)
    return r * r


@register_stat("COVAR")
@register_stat("COVARIANCE.P")
def fn_covariance_p(
    array1: Any, array2: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    pairs = extract_pairs(array1, array2, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / len(xs)


@register_stat("COVARIANCE.S")
def fn_covariance_s(
    array1: Any, array2: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    pairs = extract_pairs(array1, array2, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    if len(xs) < 2:
        return DIV0
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (len(xs) - 1.0)


@register_stat("SLOPE")
def fn_slope(known_y: Any, known_x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    pairs = extract_pairs(known_x, known_y, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    return res[0]


@register_stat("INTERCEPT")
def fn_intercept(
    known_y: Any, known_x: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    pairs = extract_pairs(known_x, known_y, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    return res[1]


@register_stat("STEYX")
def fn_steyx(known_y: Any, known_x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    pairs = extract_pairs(known_x, known_y, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    n = len(xs)
    if n < 3:
        return DIV0
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    slope, intercept, _, _ = res
    ssr = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return math.sqrt(ssr / (n - 2.0))


@register_stat("FORECAST")
@register_stat("FORECAST.LINEAR")
def fn_forecast(
    x: Any, known_y: Any, known_x: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    pairs = extract_pairs(known_x, known_y, ctx)
    if is_error(pairs):
        return pairs
    assert isinstance(pairs, tuple)
    xs, ys = pairs
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    slope, intercept, _, _ = res
    return intercept + slope * float(x_val)


@register_stat("FORECAST.ETS")
def fn_forecast_ets(
    target_date: Any, values: Any, timeline: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    return fn_forecast(target_date, values, timeline, ctx=ctx)


@register_stat("TREND")
def fn_trend(
    known_y: Any,
    known_x: Any = None,
    new_x: Any = None,
    const_b: Any = None,
    ctx: EvalContext | None = None,
) -> Arr | ExcelError:
    f_y = flatten_values([known_y], ctx)
    ys = [float(v) for v in f_y if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not ys:
        return NUM
    if known_x is not None and known_x != "":
        f_x = flatten_values([known_x], ctx)
        xs = [float(v) for v in f_x if isinstance(v, (int, float)) and not isinstance(v, bool)]
    else:
        xs = [float(i + 1) for i in range(len(ys))]
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    slope, intercept, _, _ = res
    if new_x is not None and new_x != "":
        f_nx = flatten_values([new_x], ctx)
        target_xs = [
            float(v) for v in f_nx if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
    else:
        target_xs = xs
    out = [intercept + slope * x for x in target_xs]
    return Arr([[v] for v in out])


@register_stat("GROWTH")
def fn_growth(
    known_y: Any,
    known_x: Any = None,
    new_x: Any = None,
    const_b: Any = None,
    ctx: EvalContext | None = None,
) -> Arr | ExcelError:
    f_y = flatten_values([known_y], ctx)
    ys = [float(v) for v in f_y if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not ys or any(y <= 0 for y in ys):
        return NUM
    log_ys = [math.log(y) for y in ys]
    if known_x is not None and known_x != "":
        f_x = flatten_values([known_x], ctx)
        xs = [float(v) for v in f_x if isinstance(v, (int, float)) and not isinstance(v, bool)]
    else:
        xs = [float(i + 1) for i in range(len(ys))]
    res = calc_lin_reg(xs, log_ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    m, b, _, _ = res
    if new_x is not None and new_x != "":
        f_nx = flatten_values([new_x], ctx)
        target_xs = [
            float(v) for v in f_nx if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
    else:
        target_xs = xs
    out = [math.exp(b + m * x) for x in target_xs]
    return Arr([[v] for v in out])


@register_stat("LINEST")
def fn_linest(
    known_y: Any,
    known_x: Any = None,
    const_b: Any = None,
    stats: Any = None,
    ctx: EvalContext | None = None,
) -> Arr | ExcelError:
    f_y = flatten_values([known_y], ctx)
    ys = [float(v) for v in f_y if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not ys:
        return NUM
    if known_x is not None and known_x != "":
        f_x = flatten_values([known_x], ctx)
        xs = [float(v) for v in f_x if isinstance(v, (int, float)) and not isinstance(v, bool)]
    else:
        xs = [float(i + 1) for i in range(len(ys))]
    res = calc_lin_reg(xs, ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    slope, intercept, _, _ = res
    return Arr([[slope, intercept]])


@register_stat("LOGEST")
def fn_logest(
    known_y: Any,
    known_x: Any = None,
    const_b: Any = None,
    stats: Any = None,
    ctx: EvalContext | None = None,
) -> Arr | ExcelError:
    f_y = flatten_values([known_y], ctx)
    ys = [float(v) for v in f_y if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not ys or any(y <= 0 for y in ys):
        return NUM
    log_ys = [math.log(y) for y in ys]
    if known_x is not None and known_x != "":
        f_x = flatten_values([known_x], ctx)
        xs = [float(v) for v in f_x if isinstance(v, (int, float)) and not isinstance(v, bool)]
    else:
        xs = [float(i + 1) for i in range(len(ys))]
    res = calc_lin_reg(xs, log_ys)
    if is_error(res):
        return res
    assert isinstance(res, tuple)
    m, b, _, _ = res
    return Arr([[math.exp(m), math.exp(b)]])
