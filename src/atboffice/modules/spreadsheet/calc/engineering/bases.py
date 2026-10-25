"""Worksheet number base conversions and bitwise operations."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.engineering.common import (
    opt,
    register_eng,
    to_float,
)

BITS = {2: 10, 8: 30, 16: 40}


def from_base(s_val: Any, base: int) -> int | ExcelError:
    if isinstance(s_val, bool):
        return VALUE
    if isinstance(s_val, (int, float)):
        s = str(int(s_val))
    else:
        s = str(s_val).strip().upper()
    if len(s) > 10:
        return NUM
    if not s:
        return 0
    try:
        val = int(s, base)
    except ValueError:
        return NUM
    bits = BITS[base]
    if len(s) == 10 and val >= (1 << (bits - 1)):
        val -= 1 << bits
    return val


def to_base(n_val: Any, base: int, places: Any = None) -> str | ExcelError:
    if is_error(n_val):
        return n_val
    try:
        n = int(float(n_val))
    except Exception:
        return VALUE
    bits = BITS[base]
    lim = 1 << (bits - 1)
    if n < -lim or n >= lim:
        return NUM
    if n < 0:
        n += 1 << bits
        if base == 16:
            s = f"{n:X}"
        elif base == 8:
            s = f"{n:o}".upper()
        else:
            s = f"{n:b}"
        if places is not None and places != "":
            return NUM if len(s) > 10 else s
        return s
    if base == 16:
        s = f"{n:X}"
    elif base == 8:
        s = f"{n:o}".upper()
    else:
        s = f"{n:b}"
    if places is not None and places != "":
        try:
            p = int(float(places))
            if p < len(s) or p > 10 or p < 0:
                return NUM
            s = s.zfill(p)
        except Exception:
            return VALUE
    return s


# Base conversions
for src_name, src_base in [("BIN", 2), ("OCT", 8), ("HEX", 16)]:

    def make_to_dec(b: int):
        return lambda s, ctx=None: from_base(s, b)

    register_eng(f"{src_name}2DEC")(make_to_dec(src_base))

    for tgt_name, tgt_base in [("BIN", 2), ("OCT", 8), ("HEX", 16)]:
        if src_name == tgt_name:
            continue

        def make_conv(sb: int, tb: int):
            def conv_fn(s: Any, places: Any = None, ctx: EvalContext | None = None):
                v = from_base(s, sb)
                if is_error(v):
                    return v
                return to_base(v, tb, places)

            return conv_fn

        register_eng(f"{src_name}2{tgt_name}")(make_conv(src_base, tgt_base))


@register_eng("DEC2BIN")
def fn_dec2bin(number: Any, places: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    return to_base(number, 2, places)


@register_eng("DEC2OCT")
def fn_dec2oct(number: Any, places: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    return to_base(number, 8, places)


@register_eng("DEC2HEX")
def fn_dec2hex(number: Any, places: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    return to_base(number, 16, places)


# Bitwise functions
MAX_BIT = 281474976710656  # 2**48


def bit_arg(val: Any) -> int | None:
    if is_error(val) or isinstance(val, bool):
        return None
    try:
        f = float(val)
        if f < 0 or f >= MAX_BIT or not f.is_integer():
            return None
        return int(f)
    except Exception:
        return None


@register_eng("BITAND")
def fn_bitand(number1: Any, number2: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    a = bit_arg(number1)
    b = bit_arg(number2)
    if a is None or b is None:
        return NUM
    return a & b


@register_eng("BITOR")
def fn_bitor(number1: Any, number2: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    a = bit_arg(number1)
    b = bit_arg(number2)
    if a is None or b is None:
        return NUM
    return a | b


@register_eng("BITXOR")
def fn_bitxor(number1: Any, number2: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    a = bit_arg(number1)
    b = bit_arg(number2)
    if a is None or b is None:
        return NUM
    return a ^ b


@register_eng("BITLSHIFT")
def fn_bitlshift(
    number: Any, shift_amount: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    a = bit_arg(number)
    if a is None:
        return NUM
    try:
        s = int(float(shift_amount))
        if abs(s) > 53:
            return NUM
        r = (a << s) if s >= 0 else (a >> (-s))
        if r >= MAX_BIT:
            return NUM
        return r
    except Exception:
        return NUM


@register_eng("BITRSHIFT")
def fn_bitrshift(
    number: Any, shift_amount: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    a = bit_arg(number)
    if a is None:
        return NUM
    try:
        s = int(float(shift_amount))
        if abs(s) > 53:
            return NUM
        r = (a >> s) if s >= 0 else (a << (-s))
        if r >= MAX_BIT:
            return NUM
        return r
    except Exception:
        return NUM


# Step, Delta, Error Functions
@register_eng("DELTA")
def fn_delta(number1: Any, number2: Any = None, ctx: EvalContext | None = None) -> int | ExcelError:
    a = to_float(number1)
    b = to_float(opt(number2, 0.0))
    for v in (a, b):
        if is_error(v):
            return v
    return 1 if float(a) == float(b) else 0


@register_eng("GESTEP")
def fn_gestep(number: Any, step: Any = None, ctx: EvalContext | None = None) -> int | ExcelError:
    a = to_float(number)
    b = to_float(opt(step, 0.0))
    for v in (a, b):
        if is_error(v):
            return v
    return 1 if float(a) >= float(b) else 0


@register_eng("ERF")
def fn_erf(
    lower_limit: Any, upper_limit: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    a = to_float(lower_limit)
    if is_error(a):
        return a
    if upper_limit is not None and upper_limit != "":
        b = to_float(upper_limit)
        if is_error(b):
            return b
        return math.erf(float(b)) - math.erf(float(a))
    return math.erf(float(a))


@register_eng("ERF.PRECISE")
def fn_erf_precise(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    a = to_float(x)
    if is_error(a):
        return a
    return math.erf(float(a))


@register_eng("ERFC")
@register_eng("ERFC.PRECISE")
def fn_erfc(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    a = to_float(x)
    if is_error(a):
        return a
    return math.erfc(float(a))


@register_eng("PY")
def fn_py(*args: Any, ctx: EvalContext | None = None) -> Any:
    return NUM
