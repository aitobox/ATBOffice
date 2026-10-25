"""Type coercion, criteria compilation, wildcard pattern matching, and date serial math."""

from __future__ import annotations

import datetime
import math
import re
from collections.abc import Callable
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    NUM,
    VALUE,
    ExcelError,
    is_error,
)


def round_15(val: float) -> float:
    """Round float to 15 significant digits (standard Excel floating point precision)."""
    if val == 0.0 or not math.isfinite(val):
        return val
    sign = -1.0 if val < 0 else 1.0
    val_abs = abs(val)
    order = math.floor(math.log10(val_abs))
    factor = 10.0 ** (14 - order)
    return sign * (round(val_abs * factor) / factor)


def num_eq(a: float | int, b: float | int, tol: float = 1e-12) -> bool:
    """Compare numbers with floating point tolerance."""
    if a == b:
        return True
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def parse_number_str(s: str) -> float | None:
    """Parse string representation of number including percent, commas, and scientific notation."""
    t = s.strip()
    if not t:
        return None
    pct = 0
    while t.endswith("%"):
        pct += 1
        t = t[:-1].strip()
    t = t.replace(",", "")
    try:
        val = float(t)
        if pct > 0:
            val = val / (100.0**pct)
        return val
    except ValueError:
        return None


def to_num(val: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    """Coerce value to number per Excel formula coercion rules."""
    if is_error(val):
        return val
    if val is None or val == "":
        return 0
    if isinstance(val, bool):
        return 1 if val else 0
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return NUM
        return val
    if isinstance(val, Ref):
        val = val.cell_value(val.r1, val.c1)
        return to_num(val, ctx)

    s = str(val).strip()
    if not s:
        return VALUE
    n = parse_number_str(s)
    if n is not None:
        return n
    return VALUE


def to_bool(val: Any) -> bool | ExcelError:
    """Coerce value to boolean per Excel formula coercion rules."""
    if is_error(val):
        return val
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        upper = val.strip().upper()
        if upper == "TRUE":
            return True
        if upper == "FALSE":
            return False
        n = parse_number_str(upper)
        if n is not None:
            return n != 0
        return VALUE
    if val is None:
        return False
    return VALUE


def to_str(val: Any) -> str:
    """Format value as string following Excel rules (15 significant digits for numbers)."""
    if is_error(val):
        return str(val)
    if val is None:
        return ""
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return "#NUM!"
        r = round_15(val)
        if r.is_integer() and abs(r) < 1e15:
            return str(int(r))
        s = f"{r:.15g}"
        return s
    return str(val)


# Regex matching escaped characters ~*, ~?, ~~ and unescaped *, ?
_RE_ESCAPE = re.compile(r"~([*?~])|([*?])|([.+^${}()|[\]\\])")


def wildcard_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert an Excel wildcard pattern (*, ?, ~) to a case-insensitive regex."""
    parts: list[str] = ["^"]

    def _replace(match: re.Match[str]) -> str:
        esc, wild, special = match.groups()
        if esc:
            return re.escape(esc)
        if wild == "*":
            return r"[\s\S]*"
        if wild == "?":
            return r"[\s\S]"
        return re.escape(special)

    parts.append(_RE_ESCAPE.sub(_replace, pattern))
    parts.append("$")
    return re.compile("".join(parts), re.IGNORECASE)


def build_criteria_matcher(crit: Any, ctx: EvalContext | None = None) -> Callable[[Any], bool]:
    """Compile an Excel COUNTIF/SUMIF criterion into a predicate function (value -> bool)."""
    if isinstance(crit, Ref):
        crit = crit.cell_value(crit.r1, crit.c1)
    if crit is None or crit == "":
        return lambda v: v is None or v == ""
    if isinstance(crit, bool):
        return lambda v: v is crit
    if is_error(crit):
        return lambda v: v == crit
    if isinstance(crit, (int, float)):
        return lambda v: (
            num_eq(v, crit)
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            else (
                parse_number_str(str(v)) is not None and num_eq(parse_number_str(str(v)), crit)  # type: ignore
                if isinstance(v, str)
                else False
            )
        )

    s = str(crit).strip()
    match = re.match(r"^(<=|>=|<>|<|>|=)?([\s\S]*)$", s)
    if not match:
        return lambda v: False

    op = match.group(1) or "="
    rhs = match.group(2)

    if rhs == "":
        if op == "=":
            return lambda v: v is None or v == ""
        if op == "<>":
            return lambda v: not (v is None or v == "")
        return lambda v: False

    upper = rhs.upper()
    if upper in ("TRUE", "FALSE"):
        b = upper == "TRUE"
        if op == "=":
            return lambda v: v is b
        if op == "<>":
            return lambda v: v is not b
        return lambda v: False

    if upper.startswith("#"):
        if op == "=":
            return lambda v: str(v) == upper
        if op == "<>":
            return lambda v: str(v) != upper
        return lambda v: False

    num = parse_number_str(rhs)
    if num is not None:

        def cmp_num(n: float | int) -> bool:
            if op == "=":
                return num_eq(n, num)
            if op == "<>":
                return not num_eq(n, num)
            if op == "<":
                return n < num and not num_eq(n, num)
            if op == ">":
                return n > num and not num_eq(n, num)
            if op == "<=":
                return n <= num or num_eq(n, num)
            if op == ">=":
                return n >= num or num_eq(n, num)
            return False

        def matcher_num(v: Any) -> bool:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return cmp_num(v)
            if isinstance(v, str):
                if op == "<>":
                    parsed = parse_number_str(v)
                    return parsed is None or cmp_num(parsed)
                if op == "=":
                    parsed = parse_number_str(v)
                    return parsed is not None and cmp_num(parsed)
            return op == "<>"

        return matcher_num

    # Text comparison
    if op in ("=", "<>"):
        has_wildcard = any(ch in rhs for ch in ("*", "?", "~"))
        if has_wildcard:
            rx = wildcard_to_regex(rhs)

            def match_wild(v: Any) -> bool:
                if v is None:
                    return False
                res = bool(rx.match(to_str(v)))
                return res if op == "=" else not res

            return match_wild

        low_rhs = rhs.lower()

        def match_eq(v: Any) -> bool:
            if v is None:
                return False
            res = to_str(v).lower() == low_rhs
            return res if op == "=" else not res

        return match_eq

    # Ordering comparison (<, >, <=, >=)
    def match_order(v: Any) -> bool:
        if not isinstance(v, str):
            return False
        if op == "<":
            return v.lower() < rhs.lower()
        if op == ">":
            return v.lower() > rhs.lower()
        if op == "<=":
            return v.lower() <= rhs.lower()
        if op == ">=":
            return v.lower() >= rhs.lower()
        return False

    return match_order


# --- Excel Date & Time serial utilities ---


def date_to_serial(y: int, m: int, d: int, date1904: bool = False) -> int | ExcelError:
    """Convert year, month, day to an Excel serial day number.

    Faithfully reproduces Excel's 1900 leap year bug (Feb 29, 1900 = serial 60).
    """
    if y < 0 or y >= 10000:
        return NUM
    if y < 1900:
        y += 1900

    # Normalize month overflow
    y += (m - 1) // 12
    m = ((m - 1) % 12) + 1

    if not date1904 and y == 1900 and m == 2 and d == 29:
        return 60

    try:
        dt_start = datetime.date(y, m, 1) + datetime.timedelta(days=d - 1)
    except (ValueError, OverflowError):
        return NUM

    if date1904:
        ref_date = datetime.date(1904, 1, 1)
        s = (dt_start - ref_date).days
    else:
        ref_date = datetime.date(1899, 12, 30)
        s = (dt_start - ref_date).days
        if s <= 60:
            s -= 1

    if s < 0 or s >= 2958466:
        return NUM
    return s


def serial_to_parts(v: float, date1904: bool = False) -> dict[str, Any]:
    """Convert an Excel serial date number to its date & time parts.

    Parts returned: y, m (1-12), d (1-31), wd (0=Sunday, 6=Saturday), H, M, S.
    """
    days = math.floor(v)
    secs = round((v - days) * 86400.0)
    if secs >= 86400:
        secs -= 86400
        days += 1

    if date1904:
        base = datetime.datetime(1904, 1, 1, tzinfo=datetime.UTC)
        dt = base + datetime.timedelta(days=days)
        y, m, d = dt.year, dt.month, dt.day
        wd = (dt.weekday() + 1) % 7
    elif days == 0:
        y, m, d, wd = 1900, 1, 0, 6
    elif days == 60:
        y, m, d, wd = 1900, 2, 29, 3
    elif days < 60:
        base = datetime.datetime(1899, 12, 31, tzinfo=datetime.UTC)
        dt = base + datetime.timedelta(days=days)
        y, m, d = dt.year, dt.month, dt.day
        wd = (days % 7 + 6) % 7
    else:
        base = datetime.datetime(1899, 12, 30, tzinfo=datetime.UTC)
        dt = base + datetime.timedelta(days=days)
        y, m, d = dt.year, dt.month, dt.day
        wd = (dt.weekday() + 1) % 7

    H = secs // 3600
    M = (secs % 3600) // 60
    S = secs % 60
    return {"y": y, "m": m, "d": d, "wd": wd, "H": H, "M": M, "S": S}


def js_date_to_serial(dt: datetime.datetime, date1904: bool = False) -> float:
    """Convert a Python datetime to an Excel serial date number with time fraction."""
    serial_day = date_to_serial(dt.year, dt.month, dt.day, date1904)
    if isinstance(serial_day, ExcelError):
        return 0.0
    day_frac = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6) / 86400.0
    return serial_day + day_frac
