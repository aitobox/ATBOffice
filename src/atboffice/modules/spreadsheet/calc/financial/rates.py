"""Worksheet interest rate conversion, schedule, and formatting functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import (
    flatten_values,
    register_fin,
    to_float,
)


@register_fin("EFFECT")
def fn_effect(nominal_rate: Any, npery: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    nr_val = to_float(nominal_rate)
    n_val = to_float(npery)
    for val in (nr_val, n_val):
        if is_error(val):
            return val
    nr_f = float(nr_val)
    n_f = int(float(n_val))
    if nr_f <= 0 or n_f < 1:
        return NUM
    try:
        return (1.0 + nr_f / n_f) ** n_f - 1.0
    except Exception:
        return NUM


@register_fin("NOMINAL")
def fn_nominal(effect_rate: Any, npery: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    ef_val = to_float(effect_rate)
    n_val = to_float(npery)
    for val in (ef_val, n_val):
        if is_error(val):
            return val
    ef_f = float(ef_val)
    n_f = int(float(n_val))
    if ef_f <= 0 or n_f < 1:
        return NUM
    try:
        return n_f * ((1.0 + ef_f) ** (1.0 / n_f) - 1.0)
    except Exception:
        return NUM


@register_fin("PDURATION")
def fn_pduration(rate: Any, pv: Any, fv: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    r_val = to_float(rate)
    a_val = to_float(pv)
    b_val = to_float(fv)
    for val in (r_val, a_val, b_val):
        if is_error(val):
            return val
    r_f, a_f, b_f = float(r_val), float(a_val), float(b_val)
    if r_f <= 0 or a_f <= 0 or b_f <= 0:
        return NUM
    try:
        return (math.log(b_f) - math.log(a_f)) / math.log(1.0 + r_f)
    except Exception:
        return NUM


@register_fin("RRI")
def fn_rri(nper: Any, pv: Any, fv: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    n_val = to_float(nper)
    a_val = to_float(pv)
    b_val = to_float(fv)
    for val in (n_val, a_val, b_val):
        if is_error(val):
            return val
    n_f, a_f, b_f = float(n_val), float(a_val), float(b_val)
    if n_f <= 0 or a_f == 0 or (b_f / a_f) < 0:
        return NUM
    try:
        return (b_f / a_f) ** (1.0 / n_f) - 1.0
    except Exception:
        return NUM


@register_fin("FVSCHEDULE")
def fn_fvschedule(
    principal: Any, schedule: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(principal)
    if is_error(p_val):
        return p_val
    v = float(p_val)
    flat = flatten_values([schedule], ctx)
    for item in flat:
        if item is None or item == "":
            continue
        r_val = to_float(item)
        if is_error(r_val):
            return r_val
        v *= 1.0 + float(r_val)
    return v


@register_fin("DOLLARDE")
def fn_dollarde(
    fractional_dollar: Any, fraction: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    d_val = to_float(fractional_dollar)
    f_val = to_float(fraction)
    for val in (d_val, f_val):
        if is_error(val):
            return val
    d_f = float(d_val)
    f_f = int(float(f_val))
    if f_f < 0:
        return NUM
    if f_f == 0:
        return DIV0
    i = int(d_f)
    digits = math.ceil(math.log10(f_f))
    return i + ((d_f - i) * (10.0**digits)) / f_f


@register_fin("DOLLARFR")
def fn_dollarfr(
    decimal_dollar: Any, fraction: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    d_val = to_float(decimal_dollar)
    f_val = to_float(fraction)
    for val in (d_val, f_val):
        if is_error(val):
            return val
    d_f = float(d_val)
    f_f = int(float(f_val))
    if f_f < 0:
        return NUM
    if f_f == 0:
        return DIV0
    i = int(d_f)
    digits = math.ceil(math.log10(f_f))
    return i + ((d_f - i) * f_f) / (10.0**digits)


@register_fin("EUROCONVERT")
def fn_euroconvert(
    number: Any,
    source: Any,
    target: Any,
    full_precision: Any = None,
    triangulation_precision: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    num_val = to_float(number)
    if is_error(num_val):
        return num_val
    # Fixed rates for euro conversion
    rates = {
        "EUR": 1.0,
        "DEM": 1.95583,
        "ESP": 166.386,
        "FRF": 6.55957,
        "IEP": 0.787564,
        "ITL": 1936.27,
        "NLG": 2.20371,
        "ATS": 13.7603,
        "PTE": 200.482,
        "FIM": 5.94573,
        "BEF": 40.3399,
        "LUF": 40.3399,
        "GRD": 340.75,
    }
    src = str(source).strip().upper()
    tgt = str(target).strip().upper()
    if src not in rates or tgt not in rates:
        return NA
    # Convert src -> EUR -> tgt
    eur = float(num_val) / rates[src]
    res = eur * rates[tgt]
    return res


@register_fin("STOCKHISTORY")
def fn_stockhistory(*args: Any, ctx: EvalContext | None = None) -> ExcelError:
    return NA
