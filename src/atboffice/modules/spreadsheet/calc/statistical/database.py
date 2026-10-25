"""Worksheet database calculation functions (DSUM, DAVERAGE, etc.)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import build_criteria_matcher, to_str
from atboffice.modules.spreadsheet.calc.context import EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.statistical.common import (
    devsq,
    register_stat,
)


def db_select(
    ctx: EvalContext | None, db: Any, field: Any, crit: Any
) -> dict[str, Any] | ExcelError:
    if not isinstance(db, Ref) or not isinstance(crit, Ref):
        return VALUE

    # Headers from row db.r1
    headers: list[str] = []
    for c in range(db.c1, db.c2 + 1):
        headers.append(to_str(db.cell_value(db.r1, c)).strip().lower())

    col_idx: int | None = None
    if field is not None and field != "":
        if isinstance(field, (int, float)) and not isinstance(field, bool):
            col_idx = int(field) - 1
            if col_idx < 0 or col_idx >= len(headers):
                return VALUE
        else:
            f_str = to_str(field).strip().lower()
            if f_str in headers:
                col_idx = headers.index(f_str)
            else:
                return VALUE

    # Criteria headers
    c_headers: list[str] = []
    for c in range(crit.c1, crit.c2 + 1):
        c_headers.append(to_str(crit.cell_value(crit.r1, c)).strip().lower())

    # Build criteria rules
    rules: list[list[tuple[int, Callable[[Any], bool]]]] = []
    date1904 = ctx.date1904 if ctx else False
    for r in range(crit.r1 + 1, crit.r2 + 1):
        row_rule: list[tuple[int, Callable[[Any], bool]]] = []
        for k, ch in enumerate(c_headers):
            cc = crit.c1 + k
            v = crit.cell_value(r, cc)
            if v is None or v == "":
                continue
            if ch not in headers:
                continue
            target_col = headers.index(ch)
            matcher = build_criteria_matcher(v, date1904)
            row_rule.append((target_col, matcher))
        if row_rule:
            rules.append(row_rule)

    # Filter rows
    matched_rows: list[int] = []
    for r in range(db.r1 + 1, db.r2 + 1):
        if not rules:
            matched_rows.append(r)
            continue
        # OR across rows of criteria, AND across columns in a row
        row_ok = any(
            all(matcher(db.cell_value(r, db.c1 + t_col)) for t_col, matcher in row_rule)
            for row_rule in rules
        )
        if row_ok:
            matched_rows.append(r)

    return {"rows": matched_rows, "col": col_idx, "db": db}


def get_db_numbers(sel: dict[str, Any]) -> list[float]:
    col = sel["col"]
    db = sel["db"]
    nums: list[float] = []
    if col is None:
        return nums
    for r in sel["rows"]:
        v = db.cell_value(r, db.c1 + col)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            nums.append(float(v))
    return nums


@register_stat("DSUM")
def fn_dsum(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    return sum(get_db_numbers(sel))


@register_stat("DAVERAGE")
def fn_daverage(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if not nums:
        return DIV0
    return sum(nums) / len(nums)


@register_stat("DCOUNT")
def fn_dcount(
    database: Any, field: Any = None, criteria: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    if criteria is None:
        return VALUE
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    return len(get_db_numbers(sel))


@register_stat("DCOUNTA")
def fn_dcounta(
    database: Any, field: Any = None, criteria: Any = None, ctx: EvalContext | None = None
) -> int | ExcelError:
    if criteria is None:
        return VALUE
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return len(sel["rows"])
    col = sel["col"]
    db = sel["db"]
    cnt = 0
    for r in sel["rows"]:
        v = db.cell_value(r, db.c1 + col)
        if v is not None and v != "":
            cnt += 1
    return cnt


@register_stat("DMAX")
def fn_dmax(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    return max(nums) if nums else 0.0


@register_stat("DMIN")
def fn_dmin(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    return min(nums) if nums else 0.0


@register_stat("DPRODUCT")
def fn_dproduct(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if not nums:
        return 0.0
    prod = 1.0
    for x in nums:
        prod *= x
    return prod


@register_stat("DGET")
def fn_dget(database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None) -> Any:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    rows = sel["rows"]
    if len(rows) == 0:
        return VALUE
    if len(rows) > 1:
        return NUM
    val = sel["db"].cell_value(rows[0], sel["db"].c1 + sel["col"])
    return 0.0 if val is None or val == "" else val


@register_stat("DSTDEV")
def fn_dstdev(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if len(nums) < 2:
        return DIV0
    return math.sqrt(devsq(nums) / (len(nums) - 1.0))


@register_stat("DSTDEVP")
def fn_dstdevp(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if len(nums) < 1:
        return DIV0
    return math.sqrt(devsq(nums) / len(nums))


@register_stat("DVAR")
def fn_dvar(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if len(nums) < 2:
        return DIV0
    return devsq(nums) / (len(nums) - 1.0)


@register_stat("DVARP")
def fn_dvarp(
    database: Any, field: Any, criteria: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    sel = db_select(ctx, database, field, criteria)
    if is_error(sel):
        return sel
    assert isinstance(sel, dict)
    if sel["col"] is None:
        return VALUE
    nums = get_db_numbers(sel)
    if len(nums) < 1:
        return DIV0
    return devsq(nums) / len(nums)


@register_stat("SQL.REQUEST")
def fn_sql_request(*args: Any, ctx: EvalContext | None = None) -> ExcelError:
    return NA
