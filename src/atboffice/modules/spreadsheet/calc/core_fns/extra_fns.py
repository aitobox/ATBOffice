"""Remaining statistical and higher-order dynamic functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import build_criteria_matcher
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext
from atboffice.modules.spreadsheet.calc.core_fns.common import (
    register_core,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import (
    NUM,
    VALUE,
    ExcelError,
    is_error,
)
from atboffice.modules.spreadsheet.calc.financial.common import flatten_values


# Fisher
@register_core("FISHER")
def fn_fisher(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(x)
    if is_error(v):
        return v
    val = float(v)
    if val <= -1.0 or val >= 1.0:
        return NUM
    return 0.5 * math.log((1.0 + val) / (1.0 - val))


@register_core("FISHERINV")
def fn_fisherinv(y: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(y)
    if is_error(v):
        return v
    val = float(v)
    try:
        e2y = math.exp(2.0 * val)
        return (e2y - 1.0) / (e2y + 1.0)
    except OverflowError:
        return 1.0 if val > 0 else -1.0


# Permutations
@register_core("PERMUT")
def fn_permut(number: Any, number_chosen: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    n_val = to_float(number)
    k_val = to_float(number_chosen)
    for v in (n_val, k_val):
        if is_error(v):
            return v
    n, k = int(float(n_val)), int(float(k_val))
    if n < 0 or k < 0 or n < k:
        return NUM
    return math.perm(n, k)


@register_core("PERMUTATIONA")
def fn_permutationa(
    number: Any, number_chosen: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    n_val = to_float(number)
    k_val = to_float(number_chosen)
    for v in (n_val, k_val):
        if is_error(v):
            return v
    n, k = int(float(n_val)), int(float(k_val))
    if n < 0 or k < 0:
        return NUM
    return n**k


# MAXIFS & MINIFS
def filter_ifs(
    target_range: Any, criteria_pairs: list[tuple[Any, Any]], ctx: EvalContext | None = None
) -> list[float] | ExcelError:
    t_flat = flatten_values([target_range], ctx)
    matchers = []
    c_flats = []
    date1904 = ctx.date1904 if ctx else False
    for rg, crit in criteria_pairs:
        c_flat = flatten_values([rg], ctx)
        if len(c_flat) != len(t_flat):
            return VALUE
        c_flats.append(c_flat)
        matchers.append(build_criteria_matcher(crit, date1904))

    out: list[float] = []
    for i in range(len(t_flat)):
        if all(m(c_flats[k][i]) for k, m in enumerate(matchers)):
            val = t_flat[i]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out.append(float(val))
    return out


@register_core("MAXIFS")
def fn_maxifs(
    max_range: Any, criteria_range1: Any, criteria1: Any, *more: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    pairs = [(criteria_range1, criteria1)]
    for i in range(0, len(more), 2):
        if i + 1 < len(more):
            pairs.append((more[i], more[i + 1]))
    nums = filter_ifs(max_range, pairs, ctx)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return max(nums) if nums else 0.0


@register_core("MINIFS")
def fn_minifs(
    min_range: Any, criteria_range1: Any, criteria1: Any, *more: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    pairs = [(criteria_range1, criteria1)]
    for i in range(0, len(more), 2):
        if i + 1 < len(more):
            pairs.append((more[i], more[i + 1]))
    nums = filter_ifs(min_range, pairs, ctx)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return min(nums) if nums else 0.0


# ETS Forecast stubs
@register_core("FORECAST.ETS.CONFINT")
@register_core("FORECAST.ETS.SEASONALITY")
@register_core("FORECAST.ETS.STAT")
def fn_forecast_ets_stubs(*args: Any, ctx: EvalContext | None = None) -> float:
    return 0.0


# Hyperlink & Dynamic array functions
@register_core("HYPERLINK")
def fn_hyperlink(
    link_location: Any, friendly_name: Any = None, ctx: EvalContext | None = None
) -> str:
    return (
        str(friendly_name)
        if friendly_name is not None and friendly_name != ""
        else str(link_location)
    )


@register_core("MAKEARRAY")
def fn_makearray(
    rows: Any, cols: Any, lambda_fn: Any, ctx: EvalContext | None = None
) -> Arr | ExcelError:
    r_val = to_float(rows)
    c_val = to_float(cols)
    for v in (r_val, c_val):
        if is_error(v):
            return v
    r_int, c_int = int(float(r_val)), int(float(c_val))
    if r_int < 1 or c_int < 1:
        return NUM
    data = []
    for r in range(1, r_int + 1):
        row = []
        for c in range(1, c_int + 1):
            if callable(lambda_fn):
                row.append(lambda_fn(r, c, ctx=ctx))
            else:
                row.append(0.0)
        data.append(row)
    return Arr(data)


@register_core("SCAN")
def fn_scan(
    initial_value: Any, array: Any, lambda_fn: Any, ctx: EvalContext | None = None
) -> Arr | ExcelError:
    from atboffice.modules.spreadsheet.calc.fn_dynamic import to_arr

    arr = to_arr(array, ctx)
    acc = initial_value
    data = []
    for row in arr.data:
        new_row = []
        for item in row:
            if callable(lambda_fn):
                acc = lambda_fn(acc, item, ctx=ctx)
            new_row.append(acc)
        data.append(new_row)
    return Arr(data)
