"""Data validation models and verification engine for ATBOffice Ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.calc.references import parse_range

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


class ValidationType(str, Enum):
    """Permitted data validation criteria types."""

    ANY = "any"
    WHOLE = "whole"
    DECIMAL = "decimal"
    LIST = "list"
    DATE = "date"
    TIME = "time"
    TEXT_LENGTH = "textLength"
    CUSTOM = "custom"


class ValidationOp(str, Enum):
    """Comparison operators for data validation."""

    BETWEEN = "between"
    NOT_BETWEEN = "notBetween"
    EQUAL = "equal"
    NOT_EQUAL = "notEqual"
    GREATER_THAN = "greaterThan"
    LESS_THAN = "lessThan"
    GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"
    LESS_THAN_OR_EQUAL = "lessThanOrEqual"


class AlertStyle(str, Enum):
    """Visual style and severity of the validation error dialog."""

    STOP = "stop"
    WARNING = "warning"
    INFORMATION = "information"


@dataclass
class DataValidation:
    """Specification of data entry constraints for one or more cell ranges."""

    type: str = ValidationType.ANY.value
    operator: str = ValidationOp.BETWEEN.value
    allow_blank: bool = True
    show_dropdown: bool = True

    # Prompt message displayed when cell is activated
    show_input_message: bool = False
    input_title: str = ""
    input_message: str = ""

    # Alert displayed when invalid data is entered
    show_error_alert: bool = True
    error_style: str = AlertStyle.STOP.value
    error_title: str = ""
    error_message: str = ""

    # Formulas / operands (e.g. min, max, list source, custom formula)
    formula1: str | None = None
    formula2: str | None = None

    # Target ranges
    sqref: str = ""
    ranges: list[tuple[int, int, int, int]] = field(default_factory=list)


def get_validation_for_cell(
    sheet: SheetDataModel, r: int, c: int
) -> DataValidation | None:
    """Return the applicable DataValidation rule for cell (r, c) or None."""
    dvs: list[DataValidation] = getattr(sheet, "data_validations", [])
    for dv in reversed(dvs):
        for r1, c1, r2, c2 in dv.ranges:
            if r1 <= r <= r2 and c1 <= c <= c2:
                return dv
    return None


def get_list_items(
    sheet: SheetDataModel, dv: DataValidation, r: int = 0, c: int = 0
) -> list[str]:
    """Extract list validation choices from literal or sheet range formula."""
    f = (dv.formula1 or "").strip()
    if not f:
        return []

    # 1. Comma-separated literal: e.g. "Item1, Item2, Item3" or '"Item1, Item2"'
    if f.startswith('"') and f.endswith('"'):
        content = f[1:-1]
        return [item.strip() for item in content.split(",") if item.strip()]

    if "," in f and not f.startswith("="):
        return [item.strip() for item in f.split(",") if item.strip()]

    # 2. Cell Range reference: e.g. "=$A$1:$A$5" or "A1:A5"
    ref_str = f.lstrip("=").replace("$", "")
    try:
        rg = parse_range(ref_str)
        if isinstance(rg, dict):
            r1, c1, r2, c2 = rg["r1"], rg["c1"], rg["r2"], rg["c2"]
        else:
            r1, c1, r2, c2 = rg[0], rg[1], rg[2], rg[3]
        items: list[str] = []
        for row in range(r1, r2 + 1):
            for col in range(c1, c2 + 1):
                val = sheet.get_cell_value(row, col)
                if val is not None and val != "":
                    items.append(str(val))
        return items
    except Exception:
        # Fall back to single cell reference or comma split
        if "," in f:
            return [item.strip() for item in f.split(",") if item.strip()]
        val = sheet.get_cell_value(r, c)
        return [str(val)] if val is not None else []


def _eval_operand(sheet: SheetDataModel, formula: str | None, r: int, c: int) -> float | None:
    """Evaluate numeric threshold operand."""
    if formula is None:
        return None
    f = formula.strip().lstrip("=").replace("$", "")
    try:
        return float(f)
    except ValueError:
        pass
    # Try cell reference
    try:
        rg = parse_range(f)
        r1 = rg["r1"] if isinstance(rg, dict) else rg[0]
        c1 = rg["c1"] if isinstance(rg, dict) else rg[1]
        val = sheet.get_cell_value(r1, c1)
        return float(val) if val is not None else None
    except Exception:
        return None


def validate_cell_value(
    sheet: SheetDataModel, r: int, c: int, val: Any
) -> tuple[bool, DataValidation | None]:
    """Validate candidate cell value against any active data validation rule.

    Returns:
        (is_valid, matched_rule_or_none)
    """
    dv = get_validation_for_cell(sheet, r, c)
    if dv is None or dv.type in (ValidationType.ANY.value, "none"):
        return True, None

    # Handle blank values
    if val is None or val == "":
        return (True, None) if dv.allow_blank else (False, dv)

    v_type = dv.type

    # 1. List validation
    if v_type == ValidationType.LIST.value:
        items = get_list_items(sheet, dv, r, c)
        s_val = str(val).strip().lower()
        ok = any(item.strip().lower() == s_val for item in items)
        return (True, None) if ok else (False, dv)

    # 2. Whole number (integer) validation
    if v_type == ValidationType.WHOLE.value:
        try:
            f_val = float(val)
            if not f_val.is_integer():
                return False, dv
            target_num = int(f_val)
        except (ValueError, TypeError):
            return False, dv

        a = _eval_operand(sheet, dv.formula1, r, c)
        b = _eval_operand(sheet, dv.formula2, r, c)
        op = dv.operator or ValidationOp.BETWEEN.value

        ok = _check_numeric_op(target_num, a, b, op)
        return (True, None) if ok else (False, dv)

    # 3. Decimal validation
    if v_type == ValidationType.DECIMAL.value:
        try:
            f_val = float(val)
        except (ValueError, TypeError):
            return False, dv

        a = _eval_operand(sheet, dv.formula1, r, c)
        b = _eval_operand(sheet, dv.formula2, r, c)
        op = dv.operator or ValidationOp.BETWEEN.value

        ok = _check_numeric_op(f_val, a, b, op)
        return (True, None) if ok else (False, dv)

    # 4. Text Length validation
    if v_type == ValidationType.TEXT_LENGTH.value:
        length = len(str(val))
        a = _eval_operand(sheet, dv.formula1, r, c)
        b = _eval_operand(sheet, dv.formula2, r, c)
        op = dv.operator or ValidationOp.BETWEEN.value

        ok = _check_numeric_op(length, a, b, op)
        return (True, None) if ok else (False, dv)

    # 5. Custom formula validation
    if v_type == ValidationType.CUSTOM.value:
        # If formula evaluation is supported, check result
        f = (dv.formula1 or "").strip().lstrip("=")
        if f.lower() in ("true", "1"):
            return True, None
        elif f.lower() in ("false", "0"):
            return False, dv
        return True, None

    return True, None


def _check_numeric_op(
    x: float, a: float | None, b: float | None, op: str
) -> bool:
    """Check number x against operand a and optional operand b using operator op."""
    if a is None:
        return True

    if op in (ValidationOp.BETWEEN.value, ValidationOp.NOT_BETWEEN.value):
        if b is None:
            return True
        lo, hi = min(a, b), max(a, b)
        inside = lo <= x <= hi
        return inside if op == ValidationOp.BETWEEN.value else not inside

    if op == ValidationOp.EQUAL.value:
        return x == a
    elif op == ValidationOp.NOT_EQUAL.value:
        return x != a
    elif op == ValidationOp.GREATER_THAN.value:
        return x > a
    elif op == ValidationOp.LESS_THAN.value:
        return x < a
    elif op == ValidationOp.GREATER_THAN_OR_EQUAL.value:
        return x >= a
    elif op == ValidationOp.LESS_THAN_OR_EQUAL.value:
        return x <= a

    return True
