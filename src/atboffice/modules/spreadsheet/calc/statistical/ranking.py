"""Ranking, quantile, and frequency worksheet statistical functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import NA, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.statistical.common import (
    collect_stat_numbers,
    opt,
    register_stat,
    to_float,
)


@register_stat("LARGE")
def fn_large(array: Any, k: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    k_val = to_float(k)
    if is_error(k_val):
        return k_val
    k_int = int(float(k_val))
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if k_int < 1 or k_int > len(nums):
        return NUM
    s = sorted(nums, reverse=True)
    return s[k_int - 1]


@register_stat("SMALL")
def fn_small(array: Any, k: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    k_val = to_float(k)
    if is_error(k_val):
        return k_val
    k_int = int(float(k_val))
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if k_int < 1 or k_int > len(nums):
        return NUM
    s = sorted(nums)
    return s[k_int - 1]


@register_stat("RANK")
@register_stat("RANK.EQ")
def fn_rank_eq(
    number: Any, ref: Any, order: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    n_val = to_float(number)
    if is_error(n_val):
        return n_val
    x = float(n_val)
    asc = bool(to_float(opt(order, 0)))
    nums = collect_stat_numbers([ref], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if x not in nums:
        return NA
    if asc:
        return sum(1 for v in nums if v < x) + 1
    return sum(1 for v in nums if v > x) + 1


@register_stat("RANK.AVG")
def fn_rank_avg(
    number: Any, ref: Any, order: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    n_val = to_float(number)
    if is_error(n_val):
        return n_val
    x = float(n_val)
    asc = bool(to_float(opt(order, 0)))
    nums = collect_stat_numbers([ref], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if x not in nums:
        return NA
    if asc:
        smaller = sum(1 for v in nums if v < x)
        eq = sum(1 for v in nums if v == x)
        return smaller + 1.0 + (eq - 1.0) / 2.0
    greater = sum(1 for v in nums if v > x)
    eq = sum(1 for v in nums if v == x)
    return greater + 1.0 + (eq - 1.0) / 2.0


def calc_percentile(nums: list[float], k: float) -> float | ExcelError:
    if k < 0.0 or k > 1.0:
        return NUM
    if not nums:
        return NUM
    s = sorted(nums)
    n = len(s)
    idx = k * (n - 1)
    i = int(math.floor(idx))
    frac = idx - i
    if i >= n - 1:
        return s[-1]
    return s[i] + frac * (s[i + 1] - s[i])


@register_stat("PERCENTILE")
@register_stat("PERCENTILE.INC")
def fn_percentile_inc(
    array: Any, k: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    k_val = to_float(k)
    if is_error(k_val):
        return k_val
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return calc_percentile(nums, float(k_val))


@register_stat("PERCENTILE.EXC")
def fn_percentile_exc(
    array: Any, k: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    k_val = to_float(k)
    if is_error(k_val):
        return k_val
    k_f = float(k_val)
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    n = len(nums)
    if k_f <= 0.0 or k_f >= 1.0 or k_f < 1.0 / (n + 1.0) or k_f > n / (n + 1.0):
        return NUM
    s = sorted(nums)
    idx = k_f * (n + 1.0)
    i = int(math.floor(idx))
    frac = idx - i
    return s[i - 1] + frac * (s[i] - s[i - 1])


@register_stat("QUARTILE")
@register_stat("QUARTILE.INC")
def fn_quartile_inc(
    array: Any, quart: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    q_val = to_float(quart)
    if is_error(q_val):
        return q_val
    q_int = int(float(q_val))
    if q_int not in (0, 1, 2, 3, 4):
        return NUM
    return fn_percentile_inc(array, q_int * 0.25, ctx=ctx)


@register_stat("QUARTILE.EXC")
def fn_quartile_exc(
    array: Any, quart: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    q_val = to_float(quart)
    if is_error(q_val):
        return q_val
    q_int = int(float(q_val))
    if q_int not in (1, 2, 3):
        return NUM
    return fn_percentile_exc(array, q_int * 0.25, ctx=ctx)


@register_stat("PERCENTRANK")
@register_stat("PERCENTRANK.INC")
def fn_percentrank_inc(
    array: Any, x: Any, significance: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    sig_val = to_float(opt(significance, 3))
    if is_error(sig_val):
        return sig_val
    sig = int(float(sig_val))
    if sig < 1:
        return NUM
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    x_f = float(x_val)
    s = sorted(nums)
    if x_f < s[0] or x_f > s[-1]:
        return NA
    if s[0] == s[-1]:
        return 1.0
    for i in range(len(s) - 1):
        if s[i] <= x_f <= s[i + 1]:
            if s[i] == s[i + 1]:
                frac = 0.0
            else:
                frac = (x_f - s[i]) / (s[i + 1] - s[i])
            rank = (i + frac) / (len(s) - 1.0)
            return round(rank, sig)
    return 1.0


@register_stat("PERCENTRANK.EXC")
def fn_percentrank_exc(
    array: Any, x: Any, significance: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    sig_val = to_float(opt(significance, 3))
    if is_error(sig_val):
        return sig_val
    sig = int(float(sig_val))
    if sig < 1:
        return NUM
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    x_f = float(x_val)
    s = sorted(nums)
    if x_f <= s[0] or x_f >= s[-1]:
        return NA
    for i in range(len(s) - 1):
        if s[i] <= x_f <= s[i + 1]:
            frac = (x_f - s[i]) / (s[i + 1] - s[i]) if s[i] != s[i + 1] else 0.0
            rank = (i + 1.0 + frac) / (len(s) + 1.0)
            return round(rank, sig)
    return 1.0


@register_stat("FREQUENCY")
def fn_frequency(
    data_array: Any, bins_array: Any, ctx: EvalContext | None = None
) -> Arr | ExcelError:
    data = collect_stat_numbers([data_array], ctx, False)
    bins = collect_stat_numbers([bins_array], ctx, False)
    if is_error(data):
        return data
    if is_error(bins):
        return bins
    assert isinstance(data, list) and isinstance(bins, list)
    s_bins = sorted(bins)
    counts = [0] * (len(s_bins) + 1)
    for x in data:
        placed = False
        for i, b in enumerate(s_bins):
            if x <= b:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return Arr([[c] for c in counts])


@register_stat("PROB")
def fn_prob(
    x_range: Any,
    prob_range: Any,
    lower_limit: Any,
    upper_limit: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    lo_val = to_float(lower_limit)
    if is_error(lo_val):
        return lo_val
    hi_val = lo_val if upper_limit is None or upper_limit == "" else to_float(upper_limit)
    if is_error(hi_val):
        return hi_val
    lo = float(lo_val)
    hi = float(hi_val)
    if lo > hi:
        return NUM
    xs = collect_stat_numbers([x_range], ctx, False)
    ps = collect_stat_numbers([prob_range], ctx, False)
    if is_error(xs):
        return xs
    if is_error(ps):
        return ps
    assert isinstance(xs, list) and isinstance(ps, list)
    if len(xs) != len(ps) or not xs or any(p < 0 or p > 1 for p in ps):
        return NUM
    if abs(sum(ps) - 1.0) > 1e-6:
        return NUM
    return sum(p for x, p in zip(xs, ps) if lo <= x <= hi)
