"""Worksheet Date & Time functions."""

from __future__ import annotations

import datetime
import math
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import (
    date_to_serial,
    days360,
    days_in_month,
    serial_to_parts,
    to_num,
    yearfrac,
)
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.core_fns.common import (
    opt,
    register_core,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import flatten_values


def check_date(v: float) -> bool:
    return v < 0 or v >= 2958466


@register_core("HOUR")
def fn_hour(serial_number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(serial_number)
    if is_error(v):
        return v
    date1904 = ctx.date1904 if ctx else False
    p = serial_to_parts(float(v), date1904)
    return p["H"]


@register_core("MINUTE")
def fn_minute(serial_number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(serial_number)
    if is_error(v):
        return v
    date1904 = ctx.date1904 if ctx else False
    p = serial_to_parts(float(v), date1904)
    return p["M"]


@register_core("SECOND")
def fn_second(serial_number: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(serial_number)
    if is_error(v):
        return v
    date1904 = ctx.date1904 if ctx else False
    p = serial_to_parts(float(v), date1904)
    return p["S"]


@register_core("TIME")
def fn_time(hour: Any, minute: Any, second: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    h_val = to_float(hour)
    m_val = to_float(minute)
    s_val = to_float(second)
    for v in (h_val, m_val, s_val):
        if is_error(v):
            return v
    h, m, s = int(float(h_val)), int(float(m_val)), int(float(s_val))
    t = h * 3600 + m * 60 + s
    if t < 0 or h > 32767 or m > 32767 or s > 32767:
        return NUM
    return (t % 86400) / 86400.0


@register_core("DAYS")
def fn_days(end_date: Any, start_date: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    e = to_float(end_date)
    s = to_float(start_date)
    for v in (e, s):
        if is_error(v):
            return v
    return int(math.floor(float(e))) - int(math.floor(float(s)))


@register_core("DAYS360")
def fn_days360(
    start_date: Any, end_date: Any, method: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    s = to_float(start_date)
    e = to_float(end_date)
    for v in (s, e):
        if is_error(v):
            return v
    m = bool(opt(method, False))
    date1904 = ctx.date1904 if ctx else False
    return days360(float(s), float(e), m, date1904)


@register_core("YEARFRAC")
def fn_yearfrac(
    start_date: Any, end_date: Any, basis: Any = None, ctx: EvalContext | None = None
) -> float | ExcelError:
    s = to_float(start_date)
    e = to_float(end_date)
    b_val = to_float(opt(basis, 0))
    for v in (s, e, b_val):
        if is_error(v):
            return v
    b = int(float(b_val))
    if b < 0 or b > 4:
        return NUM
    date1904 = ctx.date1904 if ctx else False
    return yearfrac(float(s), float(e), b, date1904)


def add_months(v: float, n: int, eom: bool, date1904: bool = False) -> float:
    p = serial_to_parts(v, date1904)
    y = p["y"]
    m = p["m"] + n
    y += math.floor((m - 1) / 12)
    m = ((((m - 1) % 12) + 12) % 12) + 1
    last_d = days_in_month(y, m)
    d = last_d if eom else min(p["d"], last_d)
    res = date_to_serial(y, m, d, date1904)
    return float(res) if not is_error(res) else 0.0


@register_core("EDATE")
def fn_edate(start_date: Any, months: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    s = to_float(start_date)
    m = to_float(months)
    for v in (s, m):
        if is_error(v):
            return v
    s_f = float(s)
    if check_date(s_f):
        return NUM
    date1904 = ctx.date1904 if ctx else False
    r = add_months(math.floor(s_f), int(float(m)), False, date1904)
    return NUM if check_date(r) else r


@register_core("EOMONTH")
def fn_eomonth(start_date: Any, months: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    s = to_float(start_date)
    m = to_float(months)
    for v in (s, m):
        if is_error(v):
            return v
    s_f = float(s)
    if check_date(s_f):
        return NUM
    date1904 = ctx.date1904 if ctx else False
    r = add_months(math.floor(s_f), int(float(m)), True, date1904)
    return NUM if check_date(r) else r


@register_core("WEEKNUM")
def fn_weeknum(
    serial_number: Any, return_type: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    v = to_float(serial_number)
    if is_error(v):
        return v
    v_f = float(v)
    if check_date(v_f):
        return NUM
    t_val = to_float(opt(return_type, 1))
    if is_error(t_val):
        return t_val
    t = int(float(t_val))
    date1904 = ctx.date1904 if ctx else False
    if t == 21:
        return fn_isoweeknum(serial_number, ctx)

    start_map = {1: 0, 17: 0, 2: 1, 11: 1, 12: 2, 13: 3, 14: 4, 15: 5, 16: 6}
    if t not in start_map:
        return NUM
    start = start_map[t]
    p = serial_to_parts(v_f, date1904)
    jan1_res = date_to_serial(p["y"], 1, 1, date1904)
    if is_error(jan1_res):
        return NUM
    jan1 = int(jan1_res)
    jan1_wd = serial_to_parts(jan1, date1904)["wd"]
    offset = (jan1_wd - start + 7) % 7
    return int(math.floor((math.floor(v_f) - jan1 + offset) / 7.0)) + 1


@register_core("ISOWEEKNUM")
def fn_isoweeknum(date_val: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    v = to_float(date_val)
    if is_error(v):
        return v
    v_f = float(v)
    if check_date(v_f):
        return NUM
    date1904 = ctx.date1904 if ctx else False
    p = serial_to_parts(v_f, date1904)
    try:
        dt = datetime.date(p["y"], p["m"], p["d"])
        return dt.isocalendar()[1]
    except Exception:
        return NUM


def parse_date_str(s: str, date1904: bool = False) -> float | ExcelError:
    # Try ISO YYYY-MM-DD or MM/DD/YYYY or DD-MM-YYYY
    import re

    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s.strip())
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        res = date_to_serial(y, mo, d, date1904)
        if not is_error(res):
            return float(res)
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", s.strip())
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 30 else 1900
        res = date_to_serial(y, mo, d, date1904)
        if not is_error(res):
            return float(res)
    return VALUE


@register_core("DATEVALUE")
def fn_datevalue(date_text: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    date1904 = ctx.date1904 if ctx else False
    return parse_date_str(str(date_text), date1904)


@register_core("TIMEVALUE")
def fn_timevalue(time_text: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    import re

    s = str(time_text).strip()
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?", s, re.IGNORECASE)
    if not m:
        return VALUE
    h = int(m.group(1))
    minute = int(m.group(2))
    sec = int(m.group(3)) if m.group(3) else 0
    ampm = m.group(4).lower() if m.group(4) else ""
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    return (h * 3600 + minute * 60 + sec) / 86400.0


def weekend_mask(w: Any) -> list[int] | ExcelError:
    if w is None or w == "":
        return [0, 0, 0, 0, 0, 1, 1]  # Mon..Sun (Sat & Sun weekend)
    if isinstance(w, str):
        s = w.strip()
        if len(s) == 7 and all(c in "01" for c in s) and s != "1111111":
            return [int(c) for c in s]
        return VALUE
    try:
        n = int(float(w))
    except Exception:
        return VALUE
    mapping = {
        1: [5, 6],
        2: [6, 0],
        3: [0, 1],
        4: [1, 2],
        5: [2, 3],
        6: [3, 4],
        7: [4, 5],
        11: [6],
        12: [0],
        13: [1],
        14: [2],
        15: [3],
        16: [4],
        17: [5],
    }
    if n not in mapping:
        return NUM
    m = [0] * 7
    for idx in mapping[n]:
        m[idx] = 1
    return m


def extract_holidays(holidays_arg: Any, ctx: EvalContext | None = None) -> set[int]:
    if holidays_arg is None or holidays_arg == "":
        return set()
    flat = flatten_values([holidays_arg], ctx)
    res: set[int] = set()
    for item in flat:
        v = to_float(item)
        if not is_error(v):
            res.add(int(math.floor(float(v))))
    return res


@register_core("NETWORKDAYS")
def fn_networkdays(
    start_date: Any, end_date: Any, holidays: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    return fn_networkdays_intl(start_date, end_date, 1, holidays, ctx=ctx)


@register_core("NETWORKDAYS.INTL")
def fn_networkdays_intl(
    start_date: Any,
    end_date: Any,
    weekend: Any = None,
    holidays: Any = None,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    s = to_float(start_date)
    e = to_float(end_date)
    for v in (s, e):
        if is_error(v):
            return v
    s_f, e_f = float(s), float(e)
    if check_date(s_f) or check_date(e_f):
        return NUM
    mask = weekend_mask(weekend)
    if is_error(mask):
        return mask
    assert isinstance(mask, list)

    s_int = int(math.floor(s_f))
    e_int = int(math.floor(e_f))
    step = 1 if s_int <= e_int else -1
    hols = extract_holidays(holidays, ctx)
    date1904 = ctx.date1904 if ctx else False

    workdays = 0
    cur = s_int
    while True:
        p = serial_to_parts(cur, date1904)
        # wd: 0=Sunday, 1=Monday ... 6=Saturday -> convert to Mon=0..Sun=6
        mon_wd = (p["wd"] + 6) % 7
        if mask[mon_wd] == 0 and cur not in hols:
            workdays += 1
        if cur == e_int:
            break
        cur += step

    return workdays * step


@register_core("WORKDAY")
def fn_workday(
    start_date: Any, days_count: Any, holidays: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    return fn_workday_intl(start_date, days_count, 1, holidays, ctx=ctx)


@register_core("WORKDAY.INTL")
def fn_workday_intl(
    start_date: Any,
    days_count: Any,
    weekend: Any = None,
    holidays: Any = None,
    ctx: EvalContext | None = None,
) -> int | ExcelError:
    s = to_float(start_date)
    d = to_float(days_count)
    for v in (s, d):
        if is_error(v):
            return v
    s_f = float(s)
    d_int = int(float(d))
    if check_date(s_f):
        return NUM
    mask = weekend_mask(weekend)
    if is_error(mask):
        return mask
    assert isinstance(mask, list)

    cur = int(math.floor(s_f))
    if d_int == 0:
        return cur
    step = 1 if d_int > 0 else -1
    remaining = abs(d_int)
    hols = extract_holidays(holidays, ctx)
    date1904 = ctx.date1904 if ctx else False

    while remaining > 0:
        cur += step
        p = serial_to_parts(cur, date1904)
        mon_wd = (p["wd"] + 6) % 7
        if mask[mon_wd] == 0 and cur not in hols:
            remaining -= 1

    return cur
