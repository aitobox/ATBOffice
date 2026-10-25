"""Worksheet text manipulation functions."""

from __future__ import annotations

import re
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import to_num, to_str
from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.core_fns.common import (
    opt,
    register_core,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import VALUE, ExcelError, is_error


@register_core("CHAR")
def fn_char(number: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    n = int(float(v))
    if n < 1 or n > 255:
        return VALUE
    try:
        return chr(n)
    except Exception:
        return VALUE


@register_core("UNICHAR")
def fn_unichar(number: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    n = int(float(v))
    if n < 1:
        return VALUE
    try:
        return chr(n)
    except Exception:
        return VALUE


@register_core("CODE")
def fn_code(text: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    s = str(text)
    if not s:
        return VALUE
    return ord(s[0])


@register_core("UNICODE")
def fn_unicode(text: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    s = str(text)
    if not s:
        return VALUE
    return ord(s[0])


@register_core("CLEAN")
def fn_clean(text: Any, ctx: EvalContext | None = None) -> str:
    s = str(text)
    # Remove ASCII control characters 0..31
    return "".join(ch for ch in s if ord(ch) >= 32)


@register_core("EXACT")
def fn_exact(text1: Any, text2: Any, ctx: EvalContext | None = None) -> bool:
    return str(text1) == str(text2)


@register_core("FIND")
@register_core("FINDB")
def fn_find(
    find_text: Any, within_text: Any, start_num: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    f_str = str(find_text)
    w_str = str(within_text)
    s_val = to_float(opt(start_num, 1))
    if is_error(s_val):
        return s_val
    s = int(float(s_val))
    if s < 1 or s > len(w_str) + 1:
        return VALUE
    idx = w_str.find(f_str, s - 1)
    if idx == -1:
        return VALUE
    return idx + 1


@register_core("SEARCH")
@register_core("SEARCHB")
def fn_search(
    find_text: Any, within_text: Any, start_num: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    f_str = str(find_text)
    w_str = str(within_text)
    s_val = to_float(opt(start_num, 1))
    if is_error(s_val):
        return s_val
    s = int(float(s_val))
    if s < 1 or s > len(w_str) + 1:
        return VALUE
    # Wildcard support: ? and *
    pattern = re.escape(f_str).replace(r"\*", ".*").replace(r"\?", ".")
    m = re.search(pattern, w_str[s - 1 :], re.IGNORECASE)
    if not m:
        return VALUE
    return s + m.start()


@register_core("PROPER")
def fn_proper(text: Any, ctx: EvalContext | None = None) -> str:
    return str(text).title()


@register_core("REPLACE")
@register_core("REPLACEB")
def fn_replace(
    old_text: Any,
    start_num: Any,
    num_chars: Any,
    new_text: Any,
    ctx: EvalContext | None = None,
) -> str | ExcelError:
    s_val = to_float(start_num)
    n_val = to_float(num_chars)
    for v in (s_val, n_val):
        if is_error(v):
            return v
    s = int(float(s_val))
    n = int(float(n_val))
    old_str = str(old_text)
    if s < 1 or n < 0:
        return VALUE
    start_idx = min(s - 1, len(old_str))
    end_idx = min(start_idx + n, len(old_str))
    return old_str[:start_idx] + str(new_text) + old_str[end_idx:]


@register_core("REPT")
def fn_rept(text: Any, number_times: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    n_val = to_float(number_times)
    if is_error(n_val):
        return n_val
    n = int(float(n_val))
    if n < 0:
        return VALUE
    return str(text) * n


@register_core("T")
def fn_t(value: Any, ctx: EvalContext | None = None) -> str:
    return value if isinstance(value, str) else ""


@register_core("TEXT")
def fn_text(value: Any, format_text: Any, ctx: EvalContext | None = None) -> str:

    # Simple formatting fallback
    return to_str(value)


@register_core("VALUE")
def fn_value(text: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    num = to_num(text)
    if is_error(num):
        return VALUE
    return float(num)


@register_core("FIXED")
def fn_fixed(
    number: Any,
    decimals: Any = None,
    no_commas: Any = None,
    ctx: EvalContext | None = None,
) -> str | ExcelError:
    n_val = to_float(number)
    if is_error(n_val):
        return n_val
    dec_val = to_float(opt(decimals, 2))
    if is_error(dec_val):
        return dec_val
    d = int(float(dec_val))
    commas = not bool(opt(no_commas, False))
    fmt = f",.{d}f" if commas else f".{d}f"
    return f"{float(n_val):{fmt}}"


@register_core("DOLLAR")
def fn_dollar(
    number: Any, decimals: Any = None, ctx: EvalContext | None = None
) -> str | ExcelError:
    f = fn_fixed(number, decimals, False, ctx=ctx)
    if is_error(f):
        return f
    return f"${f}"


@register_core("NUMBERVALUE")
def fn_numbervalue(
    text: Any,
    decimal_separator: Any = None,
    group_separator: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    s = str(text).strip()
    dec = str(opt(decimal_separator, "."))
    grp = str(opt(group_separator, ","))
    s = s.replace(grp, "").replace(dec, ".")
    return to_float(s)


@register_core("LEFTB")
def fn_leftb(text: Any, num_bytes: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    from atboffice.modules.spreadsheet.calc.functions import fn_left

    return fn_left(text, num_bytes, ctx=ctx)


@register_core("RIGHTB")
def fn_rightb(text: Any, num_bytes: Any = None, ctx: EvalContext | None = None) -> str | ExcelError:
    from atboffice.modules.spreadsheet.calc.functions import fn_right

    return fn_right(text, num_bytes, ctx=ctx)


@register_core("MIDB")
def fn_midb(
    text: Any, start_num: Any, num_bytes: Any, ctx: EvalContext | None = None
) -> str | ExcelError:
    from atboffice.modules.spreadsheet.calc.functions import fn_mid

    return fn_mid(text, start_num, num_bytes, ctx=ctx)


@register_core("LENB")
def fn_lenb(text: Any, ctx: EvalContext | None = None) -> int:
    return len(str(text).encode("utf-8"))


@register_core("ASC")
@register_core("DBCS")
@register_core("JIS")
@register_core("BAHTTEXT")
@register_core("PHONETIC")
def fn_text_misc(text: Any, ctx: EvalContext | None = None) -> str:
    return str(text)
