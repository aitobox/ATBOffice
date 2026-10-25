"""Shared utilities and definitions for worksheet financial functions."""

from __future__ import annotations

import math
from typing import Any, Callable

from atboffice.modules.spreadsheet.calc.coercion import (
    date_to_serial,
    days360,
    days_in_month,
    is_leap_year,
    serial_to_parts,
    to_bool,
    to_num,
    to_str,
    yearfrac,
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

FINANCIAL_FUNCTIONS: dict[str, Callable[..., Any]] = {}


def register_fin(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a financial function by name."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        FINANCIAL_FUNCTIONS[name.upper()] = fn
        return fn

    return decorator


def opt(val: Any, default: Any) -> Any:
    """Return default if val is None, empty string or NA."""
    if val is None or val == "":
        return default
    return val


def to_float(val: Any) -> float | ExcelError:
    """Coerce value to float or return ExcelError."""
    if is_error(val):
        return val
    num = to_num(val)
    if is_error(num):
        return num
    try:
        return float(num)
    except Exception:
        return VALUE


def flatten_values(args: tuple[Any, ...] | list[Any], ctx: EvalContext | None = None) -> list[Any]:
    """Recursively flatten Ref, Arr, list, tuple into a flat list of values."""
    res: list[Any] = []
    for arg in args:
        if isinstance(arg, Ref):
            for r in range(arg.r1, arg.r2 + 1):
                for c in range(arg.c1, arg.c2 + 1):
                    res.append(arg.cell_value(r, c))
        elif isinstance(arg, Arr):
            for row in arg.data:
                for item in row:
                    res.append(item)
        elif isinstance(arg, (list, tuple)):
            res.extend(flatten_values(arg, ctx))
        else:
            res.append(arg)
    return res
