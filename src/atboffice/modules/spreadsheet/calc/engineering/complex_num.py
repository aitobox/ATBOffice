"""Worksheet complex number calculation functions."""

from __future__ import annotations

import cmath
import math
import re
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import round_15
from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.engineering.common import (
    opt,
    register_eng,
    to_float,
)

CX_REGEX = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)?(?:([+-]?(?:\d+\.?\d*|\.\d+)?(?:[eE][+-]?\d+)?)([ij]))?$",
    re.IGNORECASE,
)


def parse_cx(v: Any) -> tuple[complex, str] | ExcelError:
    if isinstance(v, bool):
        return VALUE
    if isinstance(v, (int, float)):
        return (complex(float(v), 0.0), "i")
    s = str(v if v is not None else "").strip()
    if not s:
        return (complex(0.0, 0.0), "i")
    m = CX_REGEX.match(s)
    if not m or (not m.group(1) and not m.group(3)):
        return NUM
    suffix = m.group(3).lower() if m.group(3) else "i"
    re_str = m.group(1)
    im_str = m.group(2)
    try:
        re_val = float(re_str) if re_str else 0.0
    except ValueError:
        return NUM

    if m.group(3):
        if not im_str or im_str == "+":
            im_val = 1.0
        elif im_str == "-":
            im_val = -1.0
        else:
            try:
                im_val = float(im_str)
            except ValueError:
                return NUM
    else:
        im_val = 0.0

    return (complex(re_val, im_val), suffix)


def fmt_float(x: float) -> str:
    r = round_15(x)
    if isinstance(r, float) and r.is_integer():
        return str(int(r))
    return f"{r:g}"


def fmt_cx(z: complex, suffix: str = "i") -> str | ExcelError:
    re_val = z.real
    im_val = z.imag
    if not math.isfinite(re_val) or not math.isfinite(im_val):
        return NUM
    if im_val == 0.0:
        return fmt_float(re_val)
    if im_val == 1.0:
        ims = ""
    elif im_val == -1.0:
        ims = "-"
    else:
        ims = fmt_float(im_val)
    if re_val == 0.0:
        return f"{ims}{suffix}"
    sign = "+" if im_val > 0 else ""
    return f"{fmt_float(re_val)}{sign}{ims}{suffix}"


@register_eng("COMPLEX")
def fn_complex(
    real_num: Any, i_num: Any, suffix: Any = None, ctx: EvalContext | None = None
) -> str | ExcelError:
    r = to_float(real_num)
    i = to_float(i_num)
    for v in (r, i):
        if is_error(v):
            return v
    s = str(opt(suffix, "i")).lower()
    if s not in ("i", "j", ""):
        return VALUE
    sfx = s if s else "i"
    return fmt_cx(complex(float(r), float(i)), sfx)


@register_eng("IMREAL")
def fn_imreal(inumber: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    parsed = parse_cx(inumber)
    if is_error(parsed):
        return parsed
    assert isinstance(parsed, tuple)
    return parsed[0].real


@register_eng("IMAGINARY")
def fn_imaginary(inumber: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    parsed = parse_cx(inumber)
    if is_error(parsed):
        return parsed
    assert isinstance(parsed, tuple)
    return parsed[0].imag


@register_eng("IMABS")
def fn_imabs(inumber: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    parsed = parse_cx(inumber)
    if is_error(parsed):
        return parsed
    assert isinstance(parsed, tuple)
    return abs(parsed[0])


@register_eng("IMARGUMENT")
def fn_imargument(inumber: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    parsed = parse_cx(inumber)
    if is_error(parsed):
        return parsed
    assert isinstance(parsed, tuple)
    z = parsed[0]
    if z.real == 0.0 and z.imag == 0.0:
        return DIV0
    return cmath.phase(z)


@register_eng("IMCONJUGATE")
def fn_imconjugate(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    parsed = parse_cx(inumber)
    if is_error(parsed):
        return parsed
    assert isinstance(parsed, tuple)
    return fmt_cx(parsed[0].conjugate(), parsed[1])


@register_eng("IMSUM")
def fn_imsum(*inumbers: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    acc = complex(0.0, 0.0)
    suffix = "i"
    from atboffice.modules.spreadsheet.calc.financial.common import flatten_values

    flat = flatten_values(list(inumbers), ctx)
    for item in flat:
        parsed = parse_cx(item)
        if is_error(parsed):
            return parsed
        assert isinstance(parsed, tuple)
        acc += parsed[0]
        if parsed[0].imag != 0:
            suffix = parsed[1]
    return fmt_cx(acc, suffix)


@register_eng("IMSUB")
def fn_imsub(inumber1: Any, inumber2: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p1 = parse_cx(inumber1)
    p2 = parse_cx(inumber2)
    for p in (p1, p2):
        if is_error(p):
            return p
    assert isinstance(p1, tuple) and isinstance(p2, tuple)
    return fmt_cx(p1[0] - p2[0], p1[1])


@register_eng("IMPRODUCT")
def fn_improduct(*inumbers: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    acc = complex(1.0, 0.0)
    suffix = "i"
    from atboffice.modules.spreadsheet.calc.financial.common import flatten_values

    flat = flatten_values(list(inumbers), ctx)
    for item in flat:
        parsed = parse_cx(item)
        if is_error(parsed):
            return parsed
        assert isinstance(parsed, tuple)
        acc *= parsed[0]
        if parsed[0].imag != 0:
            suffix = parsed[1]
    return fmt_cx(acc, suffix)


@register_eng("IMDIV")
def fn_imdiv(inumber1: Any, inumber2: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p1 = parse_cx(inumber1)
    p2 = parse_cx(inumber2)
    for p in (p1, p2):
        if is_error(p):
            return p
    assert isinstance(p1, tuple) and isinstance(p2, tuple)
    if p2[0] == 0:
        return NUM
    try:
        return fmt_cx(p1[0] / p2[0], p1[1])
    except Exception:
        return NUM


@register_eng("IMPOWER")
def fn_impower(inumber: Any, number: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    n = to_float(number)
    for v in (p, n):
        if is_error(v):
            return v
    assert isinstance(p, tuple)
    z, sfx = p
    n_f = float(n)
    if z == 0 and n_f <= 0:
        return NUM
    try:
        res = z**n_f
        return fmt_cx(res, sfx)
    except Exception:
        return NUM


@register_eng("IMSQRT")
def fn_imsqrt(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.sqrt(p[0]), p[1])


@register_eng("IMEXP")
def fn_imexp(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.exp(p[0]), p[1])


@register_eng("IMLN")
def fn_imln(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    if p[0] == 0:
        return NUM
    return fmt_cx(cmath.log(p[0]), p[1])


@register_eng("IMLOG10")
def fn_imlog10(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    if p[0] == 0:
        return NUM
    return fmt_cx(cmath.log10(p[0]), p[1])


@register_eng("IMLOG2")
def fn_imlog2(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    if p[0] == 0:
        return NUM
    return fmt_cx(cmath.log(p[0]) / math.log(2.0), p[1])


@register_eng("IMSIN")
def fn_imsin(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.sin(p[0]), p[1])


@register_eng("IMCOS")
def fn_imcos(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.cos(p[0]), p[1])


@register_eng("IMTAN")
def fn_imtan(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(cmath.tan(p[0]), p[1])
    except Exception:
        return NUM


@register_eng("IMCOT")
def fn_imcot(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(1.0 / cmath.tan(p[0]), p[1])
    except Exception:
        return NUM


@register_eng("IMSEC")
def fn_imsec(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(1.0 / cmath.cos(p[0]), p[1])
    except Exception:
        return NUM


@register_eng("IMCSC")
def fn_imcsc(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(1.0 / cmath.sin(p[0]), p[1])
    except Exception:
        return NUM


@register_eng("IMSINH")
def fn_imsinh(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.sinh(p[0]), p[1])


@register_eng("IMCOSH")
def fn_imcosh(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    return fmt_cx(cmath.cosh(p[0]), p[1])


@register_eng("IMSECH")
def fn_imsech(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(1.0 / cmath.cosh(p[0]), p[1])
    except Exception:
        return NUM


@register_eng("IMCSCH")
def fn_imcsch(inumber: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    p = parse_cx(inumber)
    if is_error(p):
        return p
    assert isinstance(p, tuple)
    try:
        return fmt_cx(1.0 / cmath.sinh(p[0]), p[1])
    except Exception:
        return NUM
