"""Shared utilities for engineering worksheet calculation functions."""

from __future__ import annotations

import math
from typing import Any, Callable

from atboffice.modules.spreadsheet.calc.coercion import to_bool, to_num, to_str
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

ENGINEERING_FUNCTIONS: dict[str, Callable[..., Any]] = {}


def register_eng(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register an engineering function by name."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        ENGINEERING_FUNCTIONS[name.upper()] = fn
        return fn

    return decorator


def opt(val: Any, default: Any) -> Any:
    if val is None or val == "":
        return default
    return val


def to_float(val: Any) -> float | ExcelError:
    if is_error(val):
        return val
    num = to_num(val)
    if is_error(num):
        return num
    try:
        return float(num)
    except Exception:
        return VALUE
