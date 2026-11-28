"""Worksheet interest rate conversion, schedule, and formatting functions."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import to_bool, to_num, to_str
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import DIV0, NA, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.financial.common import (
    flatten_values,
    register_fin,
    to_float,
)

# Official EU fixed irrevocable euro conversion rates: code -> (units per 1 EUR, standard decimals)
_EURO_RATES: dict[str, tuple[str, int]] = {
    "EUR": ("1", 2),
    "ATS": ("13.7603", 2),
    "BEF": ("40.3399", 0),
    "CYP": ("0.585274", 2),
    "DEM": ("1.95583", 2),
    "EEK": ("15.6466", 2),
    "ESP": ("166.386", 0),
    "FIM": ("5.94573", 2),
    "FRF": ("6.55957", 2),
    "GRD": ("340.750", 0),
    "HRK": ("7.53450", 2),
    "IEP": ("0.787564", 2),
    "ITL": ("1936.27", 0),
    "LTL": ("3.45280", 2),
    "LUF": ("40.3399", 0),
    "LVL": ("0.702804", 2),
    "MTL": ("0.429300", 2),
    "NLG": ("2.20371", 2),
    "PTE": ("200.482", 0),
    "SIT": ("239.640", 2),
    "SKK": ("30.1260", 2),
}


def _unwrap_scalar(val: Any) -> Any:
    if isinstance(val, Ref):
        return val.cell_value(val.r1, val.c1)
    if isinstance(val, Arr):
        return val.data[0][0] if val.data and val.data[0] else ""
    return val


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
def fn_euroconvert(*args: Any, ctx: EvalContext | None = None) -> float | int | ExcelError:
    """Convert a number between euros and official EU member currencies."""
    if not (3 <= len(args) <= 5):
        return VALUE

    raw_num = _unwrap_scalar(args[0])
    if is_error(raw_num):
        return raw_num
    num_val = to_num(raw_num, ctx)
    if is_error(num_val):
        return num_val

    raw_src = _unwrap_scalar(args[1])
    if is_error(raw_src):
        return raw_src
    src_code = to_str(raw_src).strip().upper()

    raw_tgt = _unwrap_scalar(args[2])
    if is_error(raw_tgt):
        return raw_tgt
    tgt_code = to_str(raw_tgt).strip().upper()

    if src_code not in _EURO_RATES or tgt_code not in _EURO_RATES:
        return VALUE

    full_prec = False
    if len(args) >= 4 and args[3] is not None:
        raw_fp = _unwrap_scalar(args[3])
        if is_error(raw_fp):
            return raw_fp
        fp_bool = to_bool(raw_fp)
        if is_error(fp_bool):
            return fp_bool
        full_prec = bool(fp_bool)

    tri_prec: int | None = None
    if len(args) >= 5 and args[4] is not None:
        raw_tp = _unwrap_scalar(args[4])
        if is_error(raw_tp):
            return raw_tp
        tp_num = to_num(raw_tp, ctx)
        if is_error(tp_num):
            return tp_num
        tri_prec = math.trunc(float(tp_num))
        if tri_prec < 3:
            return VALUE

    src_rate_str, _ = _EURO_RATES[src_code]
    tgt_rate_str, tgt_decimals = _EURO_RATES[tgt_code]

    amt = Decimal(str(num_val))
    if src_code == tgt_code:
        result_dec = amt
    else:
        src_rate = Decimal(src_rate_str)
        tgt_rate = Decimal(tgt_rate_str)
        eur_amt = amt if src_code == "EUR" else (amt / src_rate)
        if src_code != "EUR" and tgt_code != "EUR" and tri_prec is not None:
            q_tri = Decimal("1").scaleb(-tri_prec)
            eur_amt = eur_amt.quantize(q_tri, rounding=ROUND_HALF_UP)
        result_dec = eur_amt if tgt_code == "EUR" else (eur_amt * tgt_rate)

    if not full_prec:
        q_out = Decimal("1").scaleb(-tgt_decimals)
        result_dec = result_dec.quantize(q_out, rounding=ROUND_HALF_UP)
        if tgt_decimals == 0:
            return int(result_dec)
    return float(result_dec)


@register_fin("STOCKHISTORY")
def fn_stockhistory(*args: Any, ctx: EvalContext | None = None) -> ExcelError:
    return NA
