"""Descriptive statistics worksheet functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.statistical.common import (
    collect_stat_numbers,
    devsq,
    mean,
    register_stat,
    to_float,
)


@register_stat("AVERAGE")
def fn_average(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return DIV0
    return mean(nums)


@register_stat("AVERAGEA")
def fn_averagea(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return DIV0
    return mean(nums)


@register_stat("MAX")
def fn_max(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return max(nums) if nums else 0.0


@register_stat("MAXA")
def fn_maxa(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return max(nums) if nums else 0.0


@register_stat("MIN")
def fn_min(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return min(nums) if nums else 0.0


@register_stat("MINA")
def fn_mina(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return min(nums) if nums else 0.0


@register_stat("MEDIAN")
def fn_median(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return NUM
    s = sorted(nums)
    n = len(s)
    return s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def calc_modes(nums: list[float]) -> list[float]:
    counts: dict[float, int] = {}
    best = 1
    for x in nums:
        c = counts.get(x, 0) + 1
        counts[x] = c
        if c > best:
            best = c
    if best < 2:
        return []
    out: list[float] = []
    seen: set[float] = set()
    for x in nums:
        if counts[x] == best and x not in seen:
            seen.add(x)
            out.append(x)
    return out


@register_stat("MODE")
@register_stat("MODE.SNGL")
def fn_mode(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    m = calc_modes(nums)
    return m[0] if m else NA


@register_stat("MODE.MULT")
def fn_mode_mult(*args: Any, ctx: EvalContext | None = None) -> Arr | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    m = calc_modes(nums)
    if not m:
        return NA
    return Arr([[x] for x in m])


@register_stat("GEOMEAN")
def fn_geomean(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums or any(x <= 0 for x in nums):
        return NUM
    return math.exp(sum(math.log(x) for x in nums) / len(nums))


@register_stat("HARMEAN")
def fn_harmean(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums or any(x <= 0 for x in nums):
        return NUM
    return len(nums) / sum(1.0 / x for x in nums)


@register_stat("TRIMMEAN")
def fn_trimmean(array: Any, percent: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    p_val = to_float(percent)
    if is_error(p_val):
        return p_val
    p = float(p_val)
    if p < 0 or p >= 1:
        return NUM
    nums = collect_stat_numbers([array], ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return NUM
    k = math.floor(len(nums) * p / 2.0)
    s = sorted(nums)
    trimmed = s[k : len(s) - k] if k > 0 else s
    return mean(trimmed)


@register_stat("AVEDEV")
def fn_avedev(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return NUM
    m = mean(nums)
    return sum(abs(x - m) for x in nums) / len(nums)


@register_stat("DEVSQ")
def fn_devsq(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return NUM
    return devsq(nums)


@register_stat("VAR")
@register_stat("VAR.S")
def fn_var(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if len(nums) < 2:
        return DIV0
    return devsq(nums) / (len(nums) - 1.0)


@register_stat("VARP")
@register_stat("VAR.P")
def fn_varp(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if len(nums) < 1:
        return DIV0
    return devsq(nums) / len(nums)


@register_stat("VARA")
def fn_vara(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if len(nums) < 2:
        return DIV0
    return devsq(nums) / (len(nums) - 1.0)


@register_stat("VARPA")
def fn_varpa(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if len(nums) < 1:
        return DIV0
    return devsq(nums) / len(nums)


@register_stat("STDEV")
@register_stat("STDEV.S")
def fn_stdev(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = fn_var(*args, ctx=ctx)
    if is_error(v):
        return v
    assert isinstance(v, float)
    return math.sqrt(v)


@register_stat("STDEVP")
@register_stat("STDEV.P")
def fn_stdevp(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = fn_varp(*args, ctx=ctx)
    if is_error(v):
        return v
    assert isinstance(v, float)
    return math.sqrt(v)


@register_stat("STDEVA")
def fn_stdeva(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = fn_vara(*args, ctx=ctx)
    if is_error(v):
        return v
    assert isinstance(v, float)
    return math.sqrt(v)


@register_stat("STDEVPA")
def fn_stdevpa(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = fn_varpa(*args, ctx=ctx)
    if is_error(v):
        return v
    assert isinstance(v, float)
    return math.sqrt(v)


@register_stat("SKEW")
def fn_skew(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    n = len(nums)
    if n < 3:
        return DIV0
    s = fn_stdev(*args, ctx=ctx)
    if is_error(s) or s == 0:
        return DIV0
    assert isinstance(s, float)
    m = mean(nums)
    return (n / ((n - 1.0) * (n - 2.0))) * sum(((x - m) / s) ** 3 for x in nums)


@register_stat("SKEW.P")
def fn_skew_p(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    n = len(nums)
    if n < 1:
        return DIV0
    s = fn_stdevp(*args, ctx=ctx)
    if is_error(s) or s == 0:
        return DIV0
    assert isinstance(s, float)
    m = mean(nums)
    return (1.0 / n) * sum(((x - m) / s) ** 3 for x in nums)


@register_stat("KURT")
def fn_kurt(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_stat_numbers(args, ctx, False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    n = len(nums)
    if n < 4:
        return DIV0
    s = fn_stdev(*args, ctx=ctx)
    if is_error(s) or s == 0:
        return DIV0
    assert isinstance(s, float)
    m = mean(nums)
    term1 = (n * (n + 1.0)) / ((n - 1.0) * (n - 2.0) * (n - 3.0))
    term2 = (3.0 * (n - 1.0) ** 2) / ((n - 2.0) * (n - 3.0))
    return term1 * sum(((x - m) / s) ** 4 for x in nums) - term2
