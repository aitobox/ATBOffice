"""Core worksheet calculation functions for Ledger spreadsheet engine."""

from __future__ import annotations

import datetime
import math
from collections.abc import Callable, Iterator
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import (
    build_criteria_matcher,
    date_to_serial,
    num_eq,
    round_15,
    serial_to_parts,
    to_bool,
    to_num,
    to_str,
)
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    DIV0,
    NA,
    NUM,
    REF,
    VALUE,
    ExcelError,
    is_error,
)

FUNCTION_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_function(
    name: str, aliases: list[str] | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register a calculation function by uppercase name and optional aliases."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        FUNCTION_REGISTRY[name.upper()] = fn
        if aliases:
            for alias in aliases:
                FUNCTION_REGISTRY[alias.upper()] = fn
        return fn

    return decorator


def call_function(name: str, args: list[Any], ctx: EvalContext | None = None) -> Any:
    """Invoke a registered worksheet function by name."""
    fn = FUNCTION_REGISTRY.get(name.upper())
    if fn is None:
        return ExcelError("#NAME?")
    try:
        return fn(*args, ctx=ctx)
    except TypeError:
        # Fallback if function doesn't accept ctx keyword argument
        try:
            return fn(*args)
        except Exception:
            return VALUE
    except Exception:
        return VALUE


# --- Iteration and Argument Normalization Helpers ---


def iterate_values(
    args: tuple[Any, ...] | list[Any], ctx: EvalContext | None = None
) -> Iterator[tuple[Any, bool]]:
    """Yield tuples of (value, is_direct) for all elements in args.

    `is_direct` is True for top-level scalar arguments and False for items coming from
    Ref or Arr collections.
    """
    for arg in args:
        if isinstance(arg, Ref):
            for r in range(arg.r1, arg.r2 + 1):
                for c in range(arg.c1, arg.c2 + 1):
                    yield (arg.cell_value(r, c), False)
        elif isinstance(arg, Arr):
            for row in arg.data:
                for item in row:
                    yield (item, False)
        elif isinstance(arg, (list, tuple)):
            for item in arg:
                yield from iterate_values([item], ctx)
        else:
            yield (arg, True)


def collect_numbers(
    args: tuple[Any, ...] | list[Any],
    ctx: EvalContext | None = None,
    allow_empty: bool = True,
) -> list[float | int] | ExcelError:
    """Collect and coerce numbers according to Excel aggregation rules.

    In ranges, strings/booleans/empty are ignored.
    In direct top-level arguments, strings and booleans are coerced;
    invalid strings produce #VALUE!.
    Any encountered ExcelError is propagated immediately.
    """
    nums: list[float | int] = []
    for val, is_direct in iterate_values(args, ctx):
        if is_error(val):
            return val
        if is_direct:
            if val is None or val == "":
                continue
            if isinstance(val, bool):
                nums.append(1 if val else 0)
            elif isinstance(val, (int, float)):
                nums.append(val)
            else:
                n = to_num(val, ctx)
                if is_error(n):
                    return n
                nums.append(n)
        else:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                nums.append(val)
    if not nums and not allow_empty:
        return DIV0
    return nums


def get_lookup_vector(target: Any) -> list[Any] | ExcelError:
    """Extract a 1D sequence of values from a Ref, Arr, or sequence."""
    if is_error(target):
        return target
    if isinstance(target, Ref):
        out: list[Any] = []
        for r in range(target.r1, target.r2 + 1):
            for c in range(target.c1, target.c2 + 1):
                out.append(target.cell_value(r, c))
        return out
    if isinstance(target, Arr):
        return target.to_flat_list()
    if isinstance(target, (list, tuple)):
        return list(target)
    return [target]


def get_table_dimensions(table: Any) -> tuple[int, int] | ExcelError:
    """Return (rows, cols) for a table range or array."""
    if is_error(table):
        return table
    if isinstance(table, (Ref, Arr)):
        return (table.rows, table.cols)
    if isinstance(table, list) and table and isinstance(table[0], list):
        return (len(table), len(table[0]))
    return (1, 1)


def get_table_cell(table: Any, r_idx: int, c_idx: int) -> Any:
    """Retrieve cell value at 0-based coordinates from table/array."""
    if isinstance(table, Ref):
        return table.cell_value(table.r1 + r_idx, table.c1 + c_idx)
    if isinstance(table, Arr):
        return table.get(r_idx, c_idx)
    if isinstance(table, list):
        if isinstance(table[r_idx], list):
            return table[r_idx][c_idx]
        return table[r_idx]
    return table


# ==============================================================================
# 1. Math & Trigonometry Functions
# ==============================================================================


@register_function("SUM")
def fn_sum(*args: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nums = collect_numbers(args, ctx, allow_empty=True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return round_15(sum(nums))


@register_function("SUMIF")
def fn_sumif(
    rg: Any,
    criteria: Any,
    sum_rg: Any = None,
    ctx: EvalContext | None = None,
) -> float | int | ExcelError:
    if is_error(rg):
        return rg
    if is_error(criteria):
        return criteria
    if sum_rg is not None and is_error(sum_rg):
        return sum_rg

    pred = build_criteria_matcher(criteria, ctx)
    s_rg = sum_rg if sum_rg is not None else rg

    total: float = 0.0
    rg_rows, rg_cols = (rg.rows, rg.cols) if isinstance(rg, (Ref, Arr)) else (1, 1)

    for r in range(rg_rows):
        for c in range(rg_cols):
            val = get_table_cell(rg, r, c)
            if is_error(val):
                return val
            if pred(val):
                s_val = get_table_cell(s_rg, r, c)
                if is_error(s_val):
                    return s_val
                if isinstance(s_val, (int, float)) and not isinstance(s_val, bool):
                    total += s_val
    return round_15(total)


@register_function("SUMIFS")
def fn_sumifs(
    sum_rg: Any,
    *criteria_pairs: Any,
    ctx: EvalContext | None = None,
) -> float | int | ExcelError:
    if len(criteria_pairs) % 2 != 0:
        return VALUE
    if not isinstance(sum_rg, (Ref, Arr)):
        return VALUE

    num_conditions = len(criteria_pairs) // 2
    conds: list[tuple[Any, Callable[[Any], bool]]] = []
    for i in range(num_conditions):
        cr_rg = criteria_pairs[2 * i]
        cr_val = criteria_pairs[2 * i + 1]
        if not isinstance(cr_rg, (Ref, Arr)):
            return VALUE
        if cr_rg.rows != sum_rg.rows or cr_rg.cols != sum_rg.cols:
            return VALUE
        conds.append((cr_rg, build_criteria_matcher(cr_val, ctx)))

    total: float = 0.0
    for r in range(sum_rg.rows):
        for c in range(sum_rg.cols):
            match = True
            for cr_rg, pred in conds:
                v = get_table_cell(cr_rg, r, c)
                if is_error(v):
                    return v
                if not pred(v):
                    match = False
                    break
            if match:
                s_val = get_table_cell(sum_rg, r, c)
                if is_error(s_val):
                    return s_val
                if isinstance(s_val, (int, float)) and not isinstance(s_val, bool):
                    total += s_val
    return round_15(total)


@register_function("ROUND")
def fn_round(x: Any, num_digits: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nx = to_num(x, ctx)
    nd = to_num(num_digits, ctx)
    if is_error(nx):
        return nx
    if is_error(nd):
        return nd
    d = math.trunc(nd)  # type: ignore
    factor = 10.0**d
    val = round_15(abs(nx) * factor)  # type: ignore
    res = math.floor(val + 0.5) / factor
    if nx < 0:  # type: ignore
        res = -res
    return round_15(int(res) if d <= 0 else res)


@register_function("ROUNDUP")
def fn_roundup(x: Any, num_digits: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nx = to_num(x, ctx)
    nd = to_num(num_digits, ctx)
    if is_error(nx):
        return nx
    if is_error(nd):
        return nd
    d = math.trunc(nd)  # type: ignore
    factor = 10.0**d
    val = round_15(abs(nx) * factor)  # type: ignore
    res = math.ceil(val) / factor
    if nx < 0:  # type: ignore
        res = -res
    return round_15(int(res) if d <= 0 else res)


@register_function("ROUNDDOWN")
def fn_rounddown(
    x: Any, num_digits: Any, ctx: EvalContext | None = None
) -> float | int | ExcelError:
    nx = to_num(x, ctx)
    nd = to_num(num_digits, ctx)
    if is_error(nx):
        return nx
    if is_error(nd):
        return nd
    d = math.trunc(nd)  # type: ignore
    factor = 10.0**d
    val = round_15(abs(nx) * factor)  # type: ignore
    res = math.floor(val) / factor
    if nx < 0:  # type: ignore
        res = -res
    return round_15(int(res) if d <= 0 else res)


@register_function("ABS")
def fn_abs(x: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nx = to_num(x, ctx)
    if is_error(nx):
        return nx
    return abs(nx)  # type: ignore


@register_function("INT")
def fn_int(x: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    nx = to_num(x, ctx)
    if is_error(nx):
        return nx
    return math.floor(round_15(nx))  # type: ignore


@register_function("MOD")
def fn_mod(n: Any, d: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nn = to_num(n, ctx)
    nd = to_num(d, ctx)
    if is_error(nn):
        return nn
    if is_error(nd):
        return nd
    if nd == 0:
        return DIV0
    res = nn % nd  # type: ignore
    return 0 if abs(res) < 1e-15 else round_15(res)


@register_function("PRODUCT")
def fn_product(*args: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nums = collect_numbers(args, ctx, allow_empty=True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    if not nums:
        return 0
    p: float = 1.0
    for x in nums:
        p *= x
    return round_15(p)


@register_function("POWER")
def fn_power(base: Any, exp: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nb = to_num(base, ctx)
    ne = to_num(exp, ctx)
    if is_error(nb):
        return nb
    if is_error(ne):
        return ne
    try:
        res = math.pow(nb, ne)  # type: ignore
        if math.isnan(res) or math.isinf(res):
            return NUM
        return round_15(res)
    except (ValueError, OverflowError):
        return NUM


@register_function("SQRT")
def fn_sqrt(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nx = to_num(x, ctx)
    if is_error(nx):
        return nx
    if nx < 0:  # type: ignore
        return NUM
    return round_15(math.sqrt(nx))  # type: ignore


@register_function("SUBTOTAL")
def fn_subtotal(function_num: Any, *refs: Any, ctx: EvalContext | None = None) -> Any:
    code = to_num(function_num, ctx)
    if is_error(code):
        return code
    code_int = math.trunc(code)  # type: ignore
    base_code = code_int - 100 if code_int > 100 else code_int

    sub_map = {
        1: fn_average,
        2: fn_count,
        3: fn_counta,
        4: fn_max,
        5: fn_min,
        6: fn_product,
        9: fn_sum,
    }
    func = sub_map.get(base_code)
    if func is None:
        return VALUE
    return func(*refs, ctx=ctx)


# ==============================================================================
# 2. Statistical Functions
# ==============================================================================


@register_function("AVERAGE")
def fn_average(*args: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nums = collect_numbers(args, ctx, allow_empty=False)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return round_15(sum(nums) / len(nums))


@register_function("AVERAGEIF")
def fn_averageif(
    rg: Any,
    criteria: Any,
    avg_rg: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    if is_error(rg):
        return rg
    if is_error(criteria):
        return criteria
    pred = build_criteria_matcher(criteria, ctx)
    a_rg = avg_rg if avg_rg is not None else rg

    total: float = 0.0
    count: int = 0
    rg_rows, rg_cols = (rg.rows, rg.cols) if isinstance(rg, (Ref, Arr)) else (1, 1)

    for r in range(rg_rows):
        for c in range(rg_cols):
            val = get_table_cell(rg, r, c)
            if is_error(val):
                return val
            if pred(val):
                a_val = get_table_cell(a_rg, r, c)
                if is_error(a_val):
                    return a_val
                if isinstance(a_val, (int, float)) and not isinstance(a_val, bool):
                    total += a_val
                    count += 1
    return round_15(total / count) if count > 0 else DIV0


@register_function("AVERAGEIFS")
def fn_averageifs(
    avg_rg: Any,
    *criteria_pairs: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    if len(criteria_pairs) % 2 != 0:
        return VALUE
    if not isinstance(avg_rg, (Ref, Arr)):
        return VALUE

    num_conditions = len(criteria_pairs) // 2
    conds: list[tuple[Any, Callable[[Any], bool]]] = []
    for i in range(num_conditions):
        cr_rg = criteria_pairs[2 * i]
        cr_val = criteria_pairs[2 * i + 1]
        if not isinstance(cr_rg, (Ref, Arr)):
            return VALUE
        if cr_rg.rows != avg_rg.rows or cr_rg.cols != avg_rg.cols:
            return VALUE
        conds.append((cr_rg, build_criteria_matcher(cr_val, ctx)))

    total: float = 0.0
    count: int = 0
    for r in range(avg_rg.rows):
        for c in range(avg_rg.cols):
            match = True
            for cr_rg, pred in conds:
                v = get_table_cell(cr_rg, r, c)
                if is_error(v):
                    return v
                if not pred(v):
                    match = False
                    break
            if match:
                a_val = get_table_cell(avg_rg, r, c)
                if is_error(a_val):
                    return a_val
                if isinstance(a_val, (int, float)) and not isinstance(a_val, bool):
                    total += a_val
                    count += 1
    return round_15(total / count) if count > 0 else DIV0


@register_function("COUNT")
def fn_count(*args: Any, ctx: EvalContext | None = None) -> int:
    cnt = 0
    for val, is_direct in iterate_values(args, ctx):
        if is_direct:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cnt += 1
            elif isinstance(val, str):
                if to_num(val, ctx) is not VALUE:
                    cnt += 1
        else:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cnt += 1
    return cnt


@register_function("COUNTA")
def fn_counta(*args: Any, ctx: EvalContext | None = None) -> int:
    cnt = 0
    for val, _ in iterate_values(args, ctx):
        if val is not None and val != "":
            cnt += 1
    return cnt


@register_function("COUNTBLANK")
def fn_countblank(rg: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    if is_error(rg):
        return rg
    cnt = 0
    for val, _ in iterate_values([rg], ctx):
        if val is None or val == "":
            cnt += 1
    return cnt


@register_function("COUNTIF")
def fn_countif(rg: Any, criteria: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    if is_error(rg):
        return rg
    if is_error(criteria):
        return criteria
    pred = build_criteria_matcher(criteria, ctx)
    cnt = 0
    for val, _ in iterate_values([rg], ctx):
        if pred(val):
            cnt += 1
    return cnt


@register_function("COUNTIFS")
def fn_countifs(*criteria_pairs: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    if len(criteria_pairs) % 2 != 0:
        return VALUE
    num_conditions = len(criteria_pairs) // 2
    conds: list[tuple[Any, Callable[[Any], bool]]] = []
    base_rg = criteria_pairs[0]
    if not isinstance(base_rg, (Ref, Arr)):
        return VALUE

    for i in range(num_conditions):
        cr_rg = criteria_pairs[2 * i]
        cr_val = criteria_pairs[2 * i + 1]
        if not isinstance(cr_rg, (Ref, Arr)):
            return VALUE
        if cr_rg.rows != base_rg.rows or cr_rg.cols != base_rg.cols:
            return VALUE
        conds.append((cr_rg, build_criteria_matcher(cr_val, ctx)))

    cnt = 0
    for r in range(base_rg.rows):
        for c in range(base_rg.cols):
            match = True
            for cr_rg, pred in conds:
                v = get_table_cell(cr_rg, r, c)
                if not pred(v):
                    match = False
                    break
            if match:
                cnt += 1
    return cnt


@register_function("MAX")
def fn_max(*args: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nums = collect_numbers(args, ctx, allow_empty=True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return round_15(max(nums)) if nums else 0


@register_function("MIN")
def fn_min(*args: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    nums = collect_numbers(args, ctx, allow_empty=True)
    if is_error(nums):
        return nums
    assert isinstance(nums, list)
    return round_15(min(nums)) if nums else 0


# ==============================================================================
# 3. Lookup & Reference Functions
# ==============================================================================


def lookup_compare(a: Any, b: Any) -> int:
    """Compare two values for ascending lookup order (returns -1, 0, or 1)."""
    if a == b:
        return 0
    # Numbers compare before text
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return -1 if a < b else 1
    if isinstance(a, str) and isinstance(b, str):
        return -1 if a.lower() < b.lower() else 1
    if isinstance(a, (int, float)):
        return -1
    return 1


@register_function("VLOOKUP")
def fn_vlookup(
    lookup_val: Any,
    table: Any,
    col_idx: Any,
    range_lookup: Any = True,
    ctx: EvalContext | None = None,
) -> Any:
    if is_error(lookup_val):
        return lookup_val
    if lookup_val is None:
        return NA
    if not isinstance(table, (Ref, Arr)):
        return VALUE

    c_num = to_num(col_idx, ctx)
    if is_error(c_num):
        return c_num
    c = math.trunc(c_num)  # type: ignore
    if c < 1:
        return VALUE
    if c > table.cols:
        return REF

    approx = True
    if range_lookup is not None and range_lookup is not True:
        b = to_bool(range_lookup)
        if is_error(b):
            return b
        approx = bool(b)

    found_row = -1
    if not approx:
        # Exact match
        pred = build_criteria_matcher(lookup_val, ctx)
        for r in range(table.rows):
            key = get_table_cell(table, r, 0)
            if pred(key):
                found_row = r
                break
    else:
        # Approximate match (assumes table column 1 sorted ascending)
        for r in range(table.rows):
            key = get_table_cell(table, r, 0)
            if key is None:
                continue
            cmp = lookup_compare(key, lookup_val)
            if cmp <= 0:
                found_row = r
            else:
                break

    if found_row < 0:
        return NA
    res = get_table_cell(table, found_row, c - 1)
    return 0 if res is None else res


@register_function("HLOOKUP")
def fn_hlookup(
    lookup_val: Any,
    table: Any,
    row_idx: Any,
    range_lookup: Any = True,
    ctx: EvalContext | None = None,
) -> Any:
    if is_error(lookup_val):
        return lookup_val
    if lookup_val is None:
        return NA
    if not isinstance(table, (Ref, Arr)):
        return VALUE

    r_num = to_num(row_idx, ctx)
    if is_error(r_num):
        return r_num
    r = math.trunc(r_num)  # type: ignore
    if r < 1:
        return VALUE
    if r > table.rows:
        return REF

    approx = True
    if range_lookup is not None and range_lookup is not True:
        b = to_bool(range_lookup)
        if is_error(b):
            return b
        approx = bool(b)

    found_col = -1
    if not approx:
        pred = build_criteria_matcher(lookup_val, ctx)
        for c in range(table.cols):
            key = get_table_cell(table, 0, c)
            if pred(key):
                found_col = c
                break
    else:
        for c in range(table.cols):
            key = get_table_cell(table, 0, c)
            if key is None:
                continue
            cmp = lookup_compare(key, lookup_val)
            if cmp <= 0:
                found_col = c
            else:
                break

    if found_col < 0:
        return NA
    res = get_table_cell(table, r - 1, found_col)
    return 0 if res is None else res


@register_function("MATCH")
def fn_match(
    lookup_val: Any,
    lookup_arr: Any,
    match_type: Any = 1,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    if is_error(lookup_val):
        return lookup_val
    vec = get_lookup_vector(lookup_arr)
    if is_error(vec):
        return vec
    assert isinstance(vec, list)
    if not vec:
        return NA

    mt = 1
    if match_type is not None:
        m_num = to_num(match_type, ctx)
        if is_error(m_num):
            return m_num
        mt = math.trunc(m_num)  # type: ignore

    if mt == 0:
        pred = build_criteria_matcher(lookup_val, ctx)
        for i, val in enumerate(vec):
            if pred(val):
                return i + 1
        return NA
    elif mt > 0:
        # Largest value <= lookup_val (ascending)
        found = -1
        for i, val in enumerate(vec):
            if val is None:
                continue
            if lookup_compare(val, lookup_val) <= 0:
                found = i
            else:
                break
        return found + 1 if found >= 0 else NA
    else:
        # Smallest value >= lookup_val (descending)
        found = -1
        for i, val in enumerate(vec):
            if val is None:
                continue
            if lookup_compare(val, lookup_val) >= 0:
                found = i
            else:
                break
        return found + 1 if found >= 0 else NA


@register_function("INDEX")
def fn_index(
    arr: Any,
    row_num: Any = 0,
    col_num: Any = 0,
    area_num: Any = 1,
    ctx: EvalContext | None = None,
) -> Any:
    if is_error(arr):
        return arr
    if not isinstance(arr, (Ref, Arr)):
        return arr

    r_val = to_num(row_num, ctx) if row_num is not None else 0
    c_val = to_num(col_num, ctx) if col_num is not None else 0
    if is_error(r_val):
        return r_val
    if is_error(c_val):
        return c_val
    r = math.trunc(r_val)  # type: ignore
    c = math.trunc(c_val)  # type: ignore

    if arr.rows == 1 and arr.cols > 1 and c == 0:
        c, r = r, 0

    if r < 0 or c < 0 or r > arr.rows or c > arr.cols:
        return REF

    if r == 0 and c == 0:
        return arr
    if r == 0:
        # Entire column as Arr
        return Arr([[get_table_cell(arr, i, c - 1)] for i in range(arr.rows)])
    if c == 0:
        # Entire row as Arr
        return Arr([[get_table_cell(arr, r - 1, j) for j in range(arr.cols)]])

    res = get_table_cell(arr, r - 1, c - 1)
    return 0 if res is None else res


@register_function("LOOKUP")
def fn_lookup(
    lookup_val: Any,
    lookup_arr: Any,
    result_arr: Any = None,
    ctx: EvalContext | None = None,
) -> Any:
    if is_error(lookup_val):
        return lookup_val
    vec = get_lookup_vector(lookup_arr)
    if is_error(vec):
        return vec
    assert isinstance(vec, list)
    if not vec:
        return NA

    # Approximate match on lookup vector
    found = -1
    for i, val in enumerate(vec):
        if val is None:
            continue
        if lookup_compare(val, lookup_val) <= 0:
            found = i
        else:
            break
    if found < 0:
        return NA

    if result_arr is not None:
        r_vec = get_lookup_vector(result_arr)
        if is_error(r_vec):
            return r_vec
        assert isinstance(r_vec, list)
        return r_vec[found] if found < len(r_vec) else NA

    # Array form (last column/row)
    if isinstance(lookup_arr, (Ref, Arr)):
        if lookup_arr.cols > lookup_arr.rows:
            return get_table_cell(lookup_arr, lookup_arr.rows - 1, found)
        return get_table_cell(lookup_arr, found, lookup_arr.cols - 1)
    return vec[found]


@register_function("CHOOSE")
def fn_choose(index_num: Any, *values: Any, ctx: EvalContext | None = None) -> Any:
    idx = to_num(index_num, ctx)
    if is_error(idx):
        return idx
    k = math.trunc(idx)  # type: ignore
    if k < 1 or k > len(values):
        return VALUE
    return values[k - 1]


# ==============================================================================
# 4. Logical & Error Handling Functions
# ==============================================================================


@register_function("IF")
def fn_if(
    logical_test: Any,
    value_if_true: Any = True,
    value_if_false: Any = False,
    ctx: EvalContext | None = None,
) -> Any:
    if is_error(logical_test):
        return logical_test
    b = to_bool(logical_test)
    if is_error(b):
        return b
    return value_if_true if b else value_if_false


@register_function("IFS")
def fn_ifs(*pairs: Any, ctx: EvalContext | None = None) -> Any:
    if len(pairs) % 2 != 0:
        return VALUE
    for i in range(0, len(pairs), 2):
        cond = pairs[i]
        val = pairs[i + 1]
        if is_error(cond):
            return cond
        b = to_bool(cond)
        if is_error(b):
            return b
        if b:
            return val
    return NA


@register_function("AND")
def fn_and(*args: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    n = 0
    for val, is_direct in iterate_values(args, ctx):
        if is_error(val):
            return val
        if is_direct:
            b = to_bool(val)
            if is_error(b):
                return b
            if not b:
                return False
            n += 1
        else:
            if isinstance(val, bool):
                if not val:
                    return False
                n += 1
            elif isinstance(val, (int, float)):
                if val == 0:
                    return False
                n += 1
    return True if n > 0 else VALUE


@register_function("OR")
def fn_or(*args: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    n = 0
    has_true = False
    for val, is_direct in iterate_values(args, ctx):
        if is_error(val):
            return val
        if is_direct:
            b = to_bool(val)
            if is_error(b):
                return b
            if b:
                has_true = True
            n += 1
        else:
            if isinstance(val, bool):
                if val:
                    has_true = True
                n += 1
            elif isinstance(val, (int, float)):
                if val != 0:
                    has_true = True
                n += 1
    if n == 0:
        return VALUE
    return has_true


@register_function("NOT")
def fn_not(logical: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    if is_error(logical):
        return logical
    b = to_bool(logical)
    if is_error(b):
        return b
    return not b


@register_function("SWITCH")
def fn_switch(expr: Any, *args: Any, ctx: EvalContext | None = None) -> Any:
    if is_error(expr):
        return expr
    n = len(args)
    i = 0
    while i + 1 < n:
        val = args[i]
        res = args[i + 1]
        if is_error(val):
            return val
        if (
            num_eq(expr, val)
            if isinstance(expr, (int, float)) and isinstance(val, (int, float))
            else expr == val
        ):
            return res
        i += 2
    if i < n:
        return args[i]
    return NA


@register_function("IFERROR")
def fn_iferror(val: Any, val_if_error: Any, ctx: EvalContext | None = None) -> Any:
    return val_if_error if is_error(val) else val


@register_function("IFNA")
def fn_ifna(val: Any, val_if_na: Any, ctx: EvalContext | None = None) -> Any:
    return val_if_na if val == NA or (isinstance(val, str) and val.upper() == "#N/A") else val


# ==============================================================================
# 5. Text Functions
# ==============================================================================


@register_function("CONCAT")
def fn_concat(*args: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    out: list[str] = []
    for val, _ in iterate_values(args, ctx):
        if is_error(val):
            return val
        out.append(to_str(val))
    res = "".join(out)
    return res if len(res) <= 32767 else VALUE


@register_function("CONCATENATE")
def fn_concatenate(*args: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    out: list[str] = []
    for arg in args:
        if is_error(arg):
            return arg
        out.append(to_str(arg))
    res = "".join(out)
    return res if len(res) <= 32767 else VALUE


@register_function("LEFT")
def fn_left(text: Any, num_chars: Any = 1, ctx: EvalContext | None = None) -> str | ExcelError:
    if is_error(text):
        return text
    n = 1
    if num_chars is not None:
        nd = to_num(num_chars, ctx)
        if is_error(nd):
            return nd
        n = math.trunc(nd)  # type: ignore
    if n < 0:
        return VALUE
    s = to_str(text)
    return s[:n]


@register_function("RIGHT")
def fn_right(text: Any, num_chars: Any = 1, ctx: EvalContext | None = None) -> str | ExcelError:
    if is_error(text):
        return text
    n = 1
    if num_chars is not None:
        nd = to_num(num_chars, ctx)
        if is_error(nd):
            return nd
        n = math.trunc(nd)  # type: ignore
    if n < 0:
        return VALUE
    s = to_str(text)
    return "" if n == 0 else s[-n:]


@register_function("MID")
def fn_mid(
    text: Any, start_num: Any, num_chars: Any, ctx: EvalContext | None = None
) -> str | ExcelError:
    if is_error(text):
        return text
    st_val = to_num(start_num, ctx)
    nc_val = to_num(num_chars, ctx)
    if is_error(st_val):
        return st_val
    if is_error(nc_val):
        return nc_val
    st = math.trunc(st_val)  # type: ignore
    nc = math.trunc(nc_val)  # type: ignore
    if st < 1 or nc < 0:
        return VALUE
    s = to_str(text)
    return s[st - 1 : st - 1 + nc]


@register_function("LEN")
def fn_len(text: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    if is_error(text):
        return text
    return len(to_str(text))


@register_function("TRIM")
def fn_trim(text: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    if is_error(text):
        return text
    s = to_str(text).strip()
    return " ".join(s.split())


@register_function("UPPER")
def fn_upper(text: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    if is_error(text):
        return text
    return to_str(text).upper()


@register_function("LOWER")
def fn_lower(text: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    if is_error(text):
        return text
    return to_str(text).lower()


@register_function("SUBSTITUTE")
def fn_substitute(
    text: Any,
    old_text: Any,
    new_text: Any,
    instance_num: Any = None,
    ctx: EvalContext | None = None,
) -> str | ExcelError:
    if is_error(text):
        return text
    if is_error(old_text):
        return old_text
    if is_error(new_text):
        return new_text
    s = to_str(text)
    o = to_str(old_text)
    n = to_str(new_text)
    if o == "":
        return s

    if instance_num is None:
        return s.replace(o, n)

    inst_val = to_num(instance_num, ctx)
    if is_error(inst_val):
        return inst_val
    k = math.trunc(inst_val)  # type: ignore
    if k < 1:
        return VALUE

    idx = -1
    for _ in range(k):
        idx = s.find(o, idx + 1)
        if idx < 0:
            return s
    return s[:idx] + n + s[idx + len(o) :]


# ==============================================================================
# 6. Date & Time Functions
# ==============================================================================


@register_function("DATE")
def fn_date(y: Any, m: Any, d: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    ny = to_num(y, ctx)
    nm = to_num(m, ctx)
    nd = to_num(d, ctx)
    if is_error(ny):
        return ny
    if is_error(nm):
        return nm
    if is_error(nd):
        return nd
    d1904 = ctx.date1904 if ctx else False
    return date_to_serial(math.trunc(ny), math.trunc(nm), math.trunc(nd), d1904)  # type: ignore


@register_function("YEAR")
def fn_year(serial: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    ns = to_num(serial, ctx)
    if is_error(ns):
        return ns
    d1904 = ctx.date1904 if ctx else False
    return serial_to_parts(float(ns), d1904)["y"]  # type: ignore


@register_function("MONTH")
def fn_month(serial: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    ns = to_num(serial, ctx)
    if is_error(ns):
        return ns
    d1904 = ctx.date1904 if ctx else False
    return serial_to_parts(float(ns), d1904)["m"]  # type: ignore


@register_function("DAY")
def fn_day(serial: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    ns = to_num(serial, ctx)
    if is_error(ns):
        return ns
    d1904 = ctx.date1904 if ctx else False
    return serial_to_parts(float(ns), d1904)["d"]  # type: ignore


@register_function("TODAY")
def fn_today(ctx: EvalContext | None = None) -> int | ExcelError:
    now = datetime.datetime.now()
    d1904 = ctx.date1904 if ctx else False
    return date_to_serial(now.year, now.month, now.day, d1904)


@register_function("NOW")
def fn_now(ctx: EvalContext | None = None) -> float | ExcelError:
    now = datetime.datetime.now()
    d1904 = ctx.date1904 if ctx else False
    day_serial = date_to_serial(now.year, now.month, now.day, d1904)
    if is_error(day_serial):
        return day_serial
    day_frac = (now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6) / 86400.0
    return float(day_serial) + day_frac  # type: ignore


@register_function("DATEDIF")
def fn_datedif(
    start_date: Any, end_date: Any, unit: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    s_val = to_num(start_date, ctx)
    e_val = to_num(end_date, ctx)
    if is_error(s_val):
        return s_val
    if is_error(e_val):
        return e_val
    s = math.floor(s_val)  # type: ignore
    e = math.floor(e_val)  # type: ignore
    if s > e:
        return NUM

    d1904 = ctx.date1904 if ctx else False
    a = serial_to_parts(s, d1904)
    b = serial_to_parts(e, d1904)
    months = (b["y"] - a["y"]) * 12 + (b["m"] - a["m"]) - (1 if b["d"] < a["d"] else 0)

    u = to_str(unit).upper().strip()
    if u == "D":
        return e - s
    elif u == "M":
        return months
    elif u == "Y":
        return months // 12
    elif u == "MD":
        d = b["d"] - a["d"]
        if d < 0:
            # Days in preceding month
            prev_m = b["m"] - 1 if b["m"] > 1 else 12
            prev_y = b["y"] if b["m"] > 1 else b["y"] - 1
            if prev_m == 2:
                pm = 29 if (prev_y % 4 == 0 and (prev_y % 100 != 0 or prev_y % 400 == 0)) else 28
            elif prev_m in (4, 6, 9, 11):
                pm = 30
            else:
                pm = 31
            d += pm
        return d
    elif u == "YM":
        return months % 12
    elif u == "YD":
        st = date_to_serial(b["y"], a["m"], a["d"], d1904)
        if isinstance(st, ExcelError) or st > e:
            st = date_to_serial(b["y"] - 1, a["m"], a["d"], d1904)
        if isinstance(st, ExcelError):
            return NUM
        return e - st
    return NUM


@register_function("WEEKDAY")
def fn_weekday(
    serial: Any, return_type: Any = 1, ctx: EvalContext | None = None
) -> int | ExcelError:
    ns = to_num(serial, ctx)
    if is_error(ns):
        return ns
    rt = 1
    if return_type is not None:
        rt_val = to_num(return_type, ctx)
        if is_error(rt_val):
            return rt_val
        rt = math.trunc(rt_val)  # type: ignore

    d1904 = ctx.date1904 if ctx else False
    wd = serial_to_parts(float(ns), d1904)["wd"]  # 0 Sunday, ..., 6 Saturday
    if rt in (1, 17):
        return wd + 1
    elif rt in (2, 11):
        return ((wd + 6) % 7) + 1
    elif rt == 3:
        return (wd + 6) % 7
    elif rt == 12:
        return ((wd + 5) % 7) + 1
    elif rt == 13:
        return ((wd + 4) % 7) + 1
    elif rt == 14:
        return ((wd + 3) % 7) + 1
    elif rt == 15:
        return ((wd + 2) % 7) + 1
    elif rt == 16:
        return ((wd + 1) % 7) + 1
    return NUM
