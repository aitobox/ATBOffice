"""Worksheet Information and Logical functions."""

from __future__ import annotations

from typing import Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.core_fns.common import (
    register_core,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import (
    NA,
    VALUE,
    ExcelError,
    is_error,
)
from atboffice.modules.spreadsheet.calc.financial.common import flatten_values


@register_core("ISBLANK")
def fn_isblank(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        v = value.cell_value(value.r1, value.c1)
        return v is None or v == ""
    return value is None or value == ""


@register_core("ISERR")
def fn_iserr(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return is_error(value) and str(value) != "#N/A"


@register_core("ISERROR")
def fn_iserror(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return is_error(value)


@register_core("ISNA")
def fn_isna(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return is_error(value) and str(value) == "#N/A"


@register_core("ISLOGICAL")
def fn_islogical(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return isinstance(value, bool)


@register_core("ISNUMBER")
def fn_isnumber(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@register_core("ISTEXT")
def fn_istext(value: Any, ctx: EvalContext | None = None) -> bool:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    return isinstance(value, str)


@register_core("ISNONTEXT")
def fn_isnontext(value: Any, ctx: EvalContext | None = None) -> bool:
    return not fn_istext(value, ctx)


@register_core("ISEVEN")
def fn_iseven(number: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return int(float(v)) % 2 == 0


@register_core("ISODD")
def fn_isodd(number: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    v = to_float(number)
    if is_error(v):
        return v
    return int(float(v)) % 2 == 1


@register_core("ISREF")
def fn_isref(value: Any, ctx: EvalContext | None = None) -> bool:
    return isinstance(value, Ref)


@register_core("ISFORMULA")
def fn_isformula(reference: Any, ctx: EvalContext | None = None) -> bool:
    if not isinstance(reference, Ref):
        return False
    # If the sheet cell contains formula string or f != None
    if reference.sheet:
        try:
            cell = reference.sheet.get_cell(reference.r1, reference.c1)
            return cell.formula is not None and cell.formula != ""
        except Exception:
            pass
    return False


@register_core("ISOMITTED")
def fn_isomitted(argument: Any = None, ctx: EvalContext | None = None) -> bool:
    return argument is None or argument == ""


@register_core("TYPE")
def fn_type(value: Any, ctx: EvalContext | None = None) -> int:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    if isinstance(value, Arr):
        return 64
    if is_error(value):
        return 16
    if isinstance(value, bool):
        return 4
    if isinstance(value, str):
        return 2
    if isinstance(value, (int, float)):
        return 1
    return 1


@register_core("ERROR.TYPE")
def fn_error_type(error_val: Any, ctx: EvalContext | None = None) -> int | ExcelError:
    if isinstance(error_val, Ref):
        error_val = error_val.cell_value(error_val.r1, error_val.c1)
    if not is_error(error_val):
        return NA
    err_str = str(error_val).upper()
    mapping = {
        "#NULL!": 1,
        "#DIV/0!": 2,
        "#VALUE!": 3,
        "#REF!": 4,
        "#NAME?": 5,
        "#NUM!": 6,
        "#N/A": 7,
    }
    return mapping.get(err_str, 7)


@register_core("N")
def fn_n(value: Any, ctx: EvalContext | None = None) -> Any:
    if isinstance(value, Ref):
        value = value.cell_value(value.r1, value.c1)
    if is_error(value):
        return value
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    return 0


@register_core("NA")
def fn_na(ctx: EvalContext | None = None) -> ExcelError:
    return NA


@register_core("CELL")
def fn_cell(info_type: Any, reference: Any = None, ctx: EvalContext | None = None) -> Any:
    t = str(info_type).lower().strip()
    if t == "address":
        if isinstance(reference, Ref):
            return f"${chr(65 + reference.c1)}${reference.r1 + 1}"
        return "$A$1"
    if t == "row":
        return reference.r1 + 1 if isinstance(reference, Ref) else 1
    if t == "col":
        return reference.c1 + 1 if isinstance(reference, Ref) else 1
    if t == "contents":
        if isinstance(reference, Ref):
            return reference.cell_value(reference.r1, reference.c1)
        return reference
    if t == "type":
        if isinstance(reference, Ref):
            v = reference.cell_value(reference.r1, reference.c1)
            if v is None or v == "":
                return "b"
            if isinstance(v, str):
                return "l"
            return "v"
        return "b"
    return ""


@register_core("INFO")
def fn_info(type_text: Any, ctx: EvalContext | None = None) -> str | ExcelError:
    t = str(type_text).lower().strip()
    mapping = {
        "directory": "/",
        "numfile": 1,
        "origin": "$A:$A$1",
        "osversion": "macOS",
        "recalc": "Automatic",
        "release": "16.0",
        "system": "mac",
    }
    return mapping.get(t, VALUE)


@register_core("SHEET")
def fn_sheet(value: Any = None, ctx: EvalContext | None = None) -> int:
    return 1


@register_core("SHEETS")
def fn_sheets(value: Any = None, ctx: EvalContext | None = None) -> int:
    return 1


@register_core("TRUE")
def fn_true(ctx: EvalContext | None = None) -> bool:
    return True


@register_core("FALSE")
def fn_false(ctx: EvalContext | None = None) -> bool:
    return False


@register_core("XOR")
def fn_xor(*args: Any, ctx: EvalContext | None = None) -> bool | ExcelError:
    flat = flatten_values(list(args), ctx)
    cnt = 0
    total = 0
    for item in flat:
        if is_error(item):
            return item
        if isinstance(item, bool):
            total += 1
            if item:
                cnt += 1
        elif isinstance(item, (int, float)):
            total += 1
            if item != 0:
                cnt += 1
    if total == 0:
        return VALUE
    return cnt % 2 == 1
