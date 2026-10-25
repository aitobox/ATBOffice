"""Worksheet Math & Trigonometry calculation functions."""

from __future__ import annotations

import math
import random
from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.core_fns.common import (
    opt,
    register_core,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import (
    DIV0,
    NA,
    NUM,
    VALUE,
    ExcelError,
    is_error,
)
from atboffice.modules.spreadsheet.calc.financial.common import flatten_values


# Trig & Inverse Trig
@register_core("PI")
def fn_pi(ctx: EvalContext | None = None) -> float:
    return math.pi


@register_core("DEGREES")
def fn_degrees(angle: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(angle)
    if is_error(v):
        return v
    return math.degrees(float(v))


@register_core("RADIANS")
def fn_radians(angle: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(angle)
    if is_error(v):
        return v
    return math.radians(float(v))


@register_core("COS")
def fn_cos(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.cos(float(v))


@register_core("COSH")
def fn_cosh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.cosh(float(v))
    except OverflowError:
        return NUM


@register_core("ACOS")
def fn_acos(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.acos(float(v))
    except ValueError:
        return NUM


@register_core("ACOSH")
def fn_acosh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.acosh(float(v))
    except ValueError:
        return NUM


@register_core("SIN")
def fn_sin(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.sin(float(v))


@register_core("SINH")
def fn_sinh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.sinh(float(v))
    except OverflowError:
        return NUM


@register_core("ASIN")
def fn_asin(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.asin(float(v))
    except ValueError:
        return NUM


@register_core("ASINH")
def fn_asinh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.asinh(float(v))


@register_core("TAN")
def fn_tan(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.tan(float(v))


@register_core("TANH")
def fn_tanh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.tanh(float(v))


@register_core("ATAN")
def fn_atan(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.atan(float(v))


@register_core("ATAN2")
def fn_atan2(x_num: Any, y_num: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x = to_float(x_num)
    y = to_float(y_num)
    for v in (x, y):
        if is_error(v):
            return v
    # Excel atan2 takes x, y (opposite of math.atan2(y, x))
    if float(x) == 0.0 and float(y) == 0.0:
        return DIV0
    return math.atan2(float(y), float(x))


@register_core("ATANH")
def fn_atanh(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.atanh(float(v))
    except ValueError:
        return NUM


@register_core("COT")
def fn_cot(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    t = math.tan(float(v))
    if t == 0:
        return DIV0
    return 1.0 / t


@register_core("COTH")
def fn_coth(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    t = math.tanh(float(v))
    if t == 0:
        return DIV0
    return 1.0 / t


@register_core("ACOT")
def fn_acot(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return math.pi / 2.0 - math.atan(float(v))


@register_core("ACOTH")
def fn_acoth(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    if abs(val) <= 1.0:
        return NUM
    return 0.5 * math.log((val + 1.0) / (val - 1.0))


@register_core("CSC")
def fn_csc(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    s = math.sin(float(v))
    if s == 0:
        return DIV0
    return 1.0 / s


@register_core("CSCH")
def fn_csch(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        s = math.sinh(float(v))
        if s == 0:
            return DIV0
        return 1.0 / s
    except OverflowError:
        return NUM


@register_core("SEC")
def fn_sec(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    c = math.cos(float(v))
    if c == 0:
        return DIV0
    return 1.0 / c


@register_core("SECH")
def fn_sech(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        c = math.cosh(float(v))
        return 1.0 / c
    except OverflowError:
        return 0.0


# Exponential, Log & Roots
@register_core("EXP")
def fn_exp(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    try:
        return math.exp(float(v))
    except OverflowError:
        return NUM


@register_core("LN")
def fn_ln(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    if val <= 0:
        return NUM
    return math.log(val)


@register_core("LOG")
def fn_log(number: Any, base: Any = None, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    b_val = to_float(opt(base, 10.0))
    for x in (v, b_val):
        if is_error(x):
            return x
    val, b = float(v), float(b_val)
    if val <= 0 or b <= 0 or b == 1.0:
        return NUM
    return math.log(val, b)


@register_core("LOG10")
def fn_log10(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    return fn_log(number, 10.0, ctx=ctx)


@register_core("SQRTPI")
def fn_sqrtpi(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    if val < 0:
        return NUM
    return math.sqrt(val * math.pi)


@register_core("SIGN")
def fn_sign(number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    return 1 if val > 0 else -1 if val < 0 else 0


@register_core("QUOTIENT")
def fn_quotient(
    numerator: Any, denominator: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    n = to_float(numerator)
    d = to_float(denominator)
    for v in (n, d):
        if is_error(v):
            return v
    if float(d) == 0:
        return DIV0
    return int(float(n) / float(d))


# Rounding
@register_core("TRUNC")
def fn_trunc(
    number: Any, num_digits: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    n = to_float(number)
    d = to_float(opt(num_digits, 0))
    for v in (n, d):
        if is_error(v):
            return v
    dig = int(float(d))
    factor = 10.0**dig
    return math.trunc(float(n) * factor) / factor


@register_core("EVEN")
def fn_even(number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    sgn = 1 if val >= 0 else -1
    c = math.ceil(abs(val))
    if c % 2 != 0:
        c += 1
    return sgn * c


@register_core("ODD")
def fn_odd(number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    val = float(v)
    if val == 0:
        return 1
    sgn = 1 if val >= 0 else -1
    c = math.ceil(abs(val))
    if c % 2 == 0:
        c += 1
    return sgn * c


@register_core("MROUND")
def fn_mround(number: Any, multiple: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    n = to_float(number)
    m = to_float(multiple)
    for v in (n, m):
        if is_error(v):
            return v
    n_f, m_f = float(n), float(m)
    if m_f == 0:
        return 0.0
    if (n_f > 0 and m_f < 0) or (n_f < 0 and m_f > 0):
        return NUM
    return round(n_f / m_f) * m_f


@register_core("CEILING")
@register_core("CEILING.MATH")
@register_core("CEILING.PRECISE")
@register_core("ISO.CEILING")
@register_core("ECMA.CEILING")
def fn_ceiling(
    number: Any,
    significance: Any = None,
    mode: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    n = to_float(number)
    s = to_float(opt(significance, 1.0))
    for v in (n, s):
        if is_error(v):
            return v
    n_f, s_f = float(n), float(s)
    if s_f == 0:
        return 0.0
    return math.ceil(n_f / s_f) * s_f


@register_core("FLOOR")
@register_core("FLOOR.MATH")
@register_core("FLOOR.PRECISE")
def fn_floor(
    number: Any,
    significance: Any = None,
    mode: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    n = to_float(number)
    s = to_float(opt(significance, 1.0))
    for v in (n, s):
        if is_error(v):
            return v
    n_f, s_f = float(n), float(s)
    if s_f == 0:
        return DIV0
    return math.floor(n_f / s_f) * s_f


# Combinatorics & Math
@register_core("FACT")
def fn_fact(number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    n = int(float(v))
    if n < 0:
        return NUM
    try:
        return math.factorial(n)
    except Exception:
        return NUM


@register_core("FACTDOUBLE")
def fn_factdouble(number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    n = int(float(v))
    if n < -1:
        return NUM
    if n in (-1, 0):
        return 1
    prod = 1
    for k in range(n, 0, -2):
        prod *= k
    return prod


@register_core("COMBIN")
def fn_combin(number: Any, number_chosen: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    n_val = to_float(number)
    k_val = to_float(number_chosen)
    for v in (n_val, k_val):
        if is_error(v):
            return v
    n, k = int(float(n_val)), int(float(k_val))
    if n < 0 or k < 0 or n < k:
        return NUM
    return math.comb(n, k)


@register_core("COMBINA")
def fn_combina(number: Any, number_chosen: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    n_val = to_float(number)
    k_val = to_float(number_chosen)
    for v in (n_val, k_val):
        if is_error(v):
            return v
    n, k = int(float(n_val)), int(float(k_val))
    if n == 0 and k == 0:
        return 1
    if n < 1 or k < 0:
        return NUM
    return math.comb(n + k - 1, k)


@register_core("MULTINOMIAL")
def fn_multinomial(*numbers: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    flat = flatten_values(list(numbers), ctx)
    nums: list[int] = []
    for item in flat:
        v = to_float(item)
        if is_error(v):
            return v
        k = int(float(v))
        if k < 0:
            return NUM
        nums.append(k)
    total = sum(nums)
    res = math.factorial(total)
    denom = 1
    for k in nums:
        denom *= math.factorial(k)
    return res // denom


@register_core("GCD")
def fn_gcd(*numbers: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    flat = flatten_values(list(numbers), ctx)
    if not flat:
        return NUM
    g = 0
    for item in flat:
        v = to_float(item)
        if is_error(v):
            return v
        k = int(float(v))
        if k < 0:
            return NUM
        g = math.gcd(g, k)
    return g


@register_core("LCM")
def fn_lcm(*numbers: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    flat = flatten_values(list(numbers), ctx)
    if not flat:
        return NUM
    lcm_val = 1
    for item in flat:
        v = to_float(item)
        if is_error(v):
            return v
        k = int(float(v))
        if k < 0:
            return NUM
        lcm_val = math.lcm(lcm_val, k)
    return lcm_val


@register_core("SERIESSUM")
def fn_seriessum(
    x: Any, n: Any, m: Any, coefficients: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    n_val = to_float(n)
    m_val = to_float(m)
    for v in (x_val, n_val, m_val):
        if is_error(v):
            return v
    x_f, cur_pow, step = float(x_val), float(n_val), float(m_val)
    coeffs = flatten_values([coefficients], ctx)
    s = 0.0
    for c in coeffs:
        c_val = to_float(c)
        if is_error(c_val):
            return c_val
        s += float(c_val) * (x_f**cur_pow)
        cur_pow += step
    return s


# Base, Roman, Arabic
ROMAN_NUMS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


@register_core("ROMAN")
def fn_roman(number: Any, form: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    n = int(float(v))
    if n < 0 or n > 3999:
        return VALUE
    if n == 0:
        return ""
    res = []
    for val, roman_str in ROMAN_NUMS:
        while n >= val:
            res.append(roman_str)
            n -= val
    return "".join(res)


@register_core("ARABIC")
def fn_arabic(text: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    s = str(text).strip().upper()
    if not s:
        return 0
    mapping = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        if ch not in mapping:
            return VALUE
        curr = mapping[ch]
        if curr < prev:
            total -= curr
        else:
            total += curr
            prev = curr
    return total


@register_core("BASE")
def fn_base(
    number: Any, radix: Any, min_length: Any = None, ctx: EvalContext | None = None
) -> str | ExcelError:
    n_val = to_float(number)
    r_val = to_float(radix)
    for v in (n_val, r_val):
        if is_error(v):
            return v
    n, r = int(float(n_val)), int(float(r_val))
    if n < 0 or r < 2 or r > 36:
        return NUM
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n == 0:
        res = "0"
    else:
        chars = []
        while n > 0:
            chars.append(digits[n % r])
            n //= r
        res = "".join(reversed(chars))
    if min_length is not None and min_length != "":
        ml_val = to_float(min_length)
        if is_error(ml_val):
            return ml_val
        ml = int(float(ml_val))
        res = res.zfill(ml)
    return res


@register_core("DECIMAL")
def fn_decimal(text: Any, radix: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    s = str(text).strip()
    r_val = to_float(radix)
    if is_error(r_val):
        return r_val
    r = int(float(r_val))
    if r < 2 or r > 36:
        return NUM
    try:
        return int(s, r)
    except ValueError:
        return NUM


# Random
@register_core("RAND")
def fn_rand(ctx: EvalContext | None = None) -> float:
    return random.random()


@register_core("RANDBETWEEN")
def fn_randbetween(bottom: Any, top: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    b = to_float(bottom)
    t = to_float(top)
    for v in (b, t):
        if is_error(v):
            return v
    b_int, t_int = int(float(b)), int(float(t))
    if b_int > t_int:
        return NUM
    return random.randint(b_int, t_int)


# Matrix & Sums
@register_core("SUMSQ")
def fn_sumsq(*numbers: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    flat = flatten_values(list(numbers), ctx)
    s = 0.0
    for item in flat:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            s += float(item) ** 2
    return s


@register_core("SUMPRODUCT")
def fn_sumproduct(*arrays: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    if not arrays:
        return 0.0
    flats = [flatten_values([a], ctx) for a in arrays]
    length = len(flats[0])
    if any(len(f) != length for f in flats):
        return VALUE
    total = 0.0
    for i in range(length):
        term = 1.0
        for f in flats:
            item = f[i]
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                term *= float(item)
            else:
                term = 0.0
                break
        total += term
    return total


@register_core("SUMX2MY2")
def fn_sumx2my2(array_x: Any, array_y: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    fx = flatten_values([array_x], ctx)
    fy = flatten_values([array_y], ctx)
    if len(fx) != len(fy):
        return NA
    total = 0.0
    for a, b in zip(fx, fy):
        if (
            isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and not isinstance(a, bool)
            and not isinstance(b, bool)
        ):
            total += float(a) ** 2 - float(b) ** 2
    return total


@register_core("SUMX2PY2")
def fn_sumx2py2(array_x: Any, array_y: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    fx = flatten_values([array_x], ctx)
    fy = flatten_values([array_y], ctx)
    if len(fx) != len(fy):
        return NA
    total = 0.0
    for a, b in zip(fx, fy):
        if (
            isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and not isinstance(a, bool)
            and not isinstance(b, bool)
        ):
            total += float(a) ** 2 + float(b) ** 2
    return total


@register_core("SUMXMY2")
def fn_sumxmy2(array_x: Any, array_y: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    fx = flatten_values([array_x], ctx)
    fy = flatten_values([array_y], ctx)
    if len(fx) != len(fy):
        return NA
    total = 0.0
    for a, b in zip(fx, fy):
        if (
            isinstance(a, (int, float))
            and isinstance(b, (int, float))
            and not isinstance(a, bool)
            and not isinstance(b, bool)
        ):
            total += (float(a) - float(b)) ** 2
    return total


@register_core("MDETERM")
def fn_mdeterm(array: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    if isinstance(array, Ref):
        array = array.to_array()
    if not isinstance(array, Arr) or array.rows != array.cols:
        return VALUE
    # Simple determinant for square matrices
    mat = [[float(v) for v in row] for row in array.data]
    n = len(mat)
    det = 1.0
    for i in range(n):
        pivot = i
        for j in range(i + 1, n):
            if abs(mat[j][i]) > abs(mat[pivot][i]):
                pivot = j
        if abs(mat[pivot][i]) < 1e-15:
            return 0.0
        if pivot != i:
            mat[i], mat[pivot] = mat[pivot], mat[i]
            det = -det
        det *= mat[i][i]
        for j in range(i + 1, n):
            factor = mat[j][i] / mat[i][i]
            for k in range(i + 1, n):
                mat[j][k] -= factor * mat[i][k]
    return det


@register_core("MINVERSE")
def fn_minverse(array: Any, ctx: EvalContext | None = None) -> Arr | ExcelError:
    if isinstance(array, Ref):
        array = array.to_array()
    if not isinstance(array, Arr) or array.rows != array.cols:
        return VALUE
    n = array.rows
    # Augmented matrix [A | I]
    aug = [
        [float(array.data[r][c]) for c in range(n)] + [1.0 if r == c else 0.0 for c in range(n)]
        for r in range(n)
    ]
    for i in range(n):
        pivot = i
        for j in range(i + 1, n):
            if abs(aug[j][i]) > abs(aug[pivot][i]):
                pivot = j
        if abs(aug[pivot][i]) < 1e-15:
            return NUM
        aug[i], aug[pivot] = aug[pivot], aug[i]
        p_val = aug[i][i]
        for k in range(2 * n):
            aug[i][k] /= p_val
        for j in range(n):
            if j != i:
                factor = aug[j][i]
                for k in range(2 * n):
                    aug[j][k] -= factor * aug[i][k]
    inv = [[aug[r][n + c] for c in range(n)] for r in range(n)]
    return Arr(inv)


@register_core("MMULT")
def fn_mmult(array1: Any, array2: Any, ctx: EvalContext | None = None) -> Arr | ExcelError:
    if isinstance(array1, Ref):
        array1 = array1.to_array()
    if isinstance(array2, Ref):
        array2 = array2.to_array()
    if not isinstance(array1, Arr) or not isinstance(array2, Arr):
        return VALUE
    if array1.cols != array2.rows:
        return VALUE
    r1, c1 = array1.rows, array1.cols
    c2 = array2.cols
    res = [[0.0 for _ in range(c2)] for _ in range(r1)]
    for i in range(r1):
        for j in range(c2):
            res[i][j] = sum(float(array1.data[i][k]) * float(array2.data[k][j]) for k in range(c1))
    return Arr(res)


@register_core("MUNIT")
def fn_munit(dimension: Any, ctx: EvalContext | None = None) -> Arr | ExcelError:
    d = to_float(dimension)
    if is_error(d):
        return d
    n = int(float(d))
    if n < 1:
        return VALUE
    return Arr([[1.0 if r == c else 0.0 for c in range(n)] for r in range(n)])


@register_core("AGGREGATE")
def fn_aggregate(
    function_num: Any, options: Any, ref1: Any, *refs: Any, ctx: EvalContext | None = None
) -> Any:
    # Basic aggregate fallback mapping to subtotal/function
    return VALUE
