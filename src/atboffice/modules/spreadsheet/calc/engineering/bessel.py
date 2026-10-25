"""Worksheet Bessel calculation functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.engineering.common import (
    register_eng,
    to_float,
)
from atboffice.modules.spreadsheet.calc.errors import NUM, ExcelError, is_error


def bessel_j(x: float, n: int) -> float:
    if x == 0:
        return 1.0 if n == 0 else 0.0
    if (x * x) / 4.0 <= 4.0 * (n + 1.0):
        try:
            term = ((abs(x) / 2.0) ** n) / math.factorial(n)
        except OverflowError:
            term = 0.0
        s = 0.0
        for k in range(300):
            s += term
            term *= -(x * x) / 4.0 / ((k + 1) * (k + 1 + n))
            if abs(term) < 1e-17 * abs(s):
                break
        return -s if x < 0 and n % 2 else s
    n_pts = min(40000, 2 * math.ceil(abs(x) + n) + 96)
    s = sum(
        math.cos(n * (2.0 * math.pi * k / n_pts) - x * math.sin(2.0 * math.pi * k / n_pts))
        for k in range(n_pts)
    )
    return s / n_pts


def bessel_i(x: float, n: int) -> float:
    if x == 0:
        return 1.0 if n == 0 else 0.0
    ax = abs(x)
    if ax <= 60.0:
        try:
            term = ((ax / 2.0) ** n) / math.factorial(n)
        except OverflowError:
            term = 0.0
        s = 0.0
        for k in range(1000):
            s += term
            term *= (ax * ax) / 4.0 / ((k + 1) * (k + 1 + n))
            if term < 1e-17 * s:
                break
        r = s
    else:
        n_pts = min(40000, 2 * math.ceil(ax + n) + 96)
        s = sum(
            math.exp(ax * (math.cos(2.0 * math.pi * k / n_pts) - 1.0))
            * math.cos(n * (2.0 * math.pi * k / n_pts))
            for k in range(n_pts)
        )
        r = (s / n_pts) * math.exp(ax)
    return -r if x < 0 and n % 2 else r


def k_int(x: float, nu: int) -> float:
    h = 0.05
    s = 0.5 * math.exp(-x)
    for k in range(1, 10000):
        t = k * h
        try:
            cosh_t = math.cosh(t)
            v = math.exp(-x * cosh_t + nu * t) * 0.5 * (1.0 + math.exp(-2.0 * nu * t))
            s += v
            if v < 1e-18 * s and x * cosh_t > nu * t:
                break
        except OverflowError:
            break
    return s * h


def bessel_k(x: float, n: int) -> float:
    k0 = k_int(x, 0)
    if n == 0:
        return k0
    k1 = k_int(x, 1)
    if n == 1:
        return k1
    bkm = k0
    bk = k1
    for j in range(1, n):
        bkp = bkm + ((2.0 * j) / x) * bk
        bkm = bk
        bk = bkp
    return bk


def simpson_integrate(f, a: float, b: float, panels: int = 100) -> float:
    h = (b - a) / panels
    s = f(a) + f(b)
    for i in range(1, panels):
        w = 4.0 if i % 2 == 1 else 2.0
        s += w * f(a + i * h)
    return s * h / 3.0


def y_n01(x: float, nu: int) -> float:
    a = simpson_integrate(
        lambda th: math.sin(x * math.sin(th) - nu * th), 0.0, math.pi, math.ceil(x / 2.0) + 16
    )
    t_end = math.asinh(45.0 / x) + 2.0
    sgn = -1.0 if nu % 2 else 1.0
    b = simpson_integrate(
        lambda t: (math.exp(nu * t) + sgn * math.exp(-nu * t)) * math.exp(-x * math.sinh(t)),
        0.0,
        t_end,
        48,
    )
    return (a - b) / math.pi


def bessel_y(x: float, n: int) -> float:
    y0 = y_n01(x, 0)
    if n == 0:
        return y0
    y1 = y_n01(x, 1)
    if n == 1:
        return y1
    bym = y0
    by = y1
    for j in range(1, n):
        byp = ((2.0 * j) / x) * by - bym
        bym = by
        by = byp
    return by


@register_eng("BESSELJ")
def fn_besselj(x: Any, n: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    n_val = to_float(n)
    for v in (x_val, n_val):
        if is_error(v):
            return v
    n_int = int(float(n_val))
    if n_int < 0:
        return NUM
    try:
        return bessel_j(float(x_val), n_int)
    except Exception:
        return NUM


@register_eng("BESSELI")
def fn_besseli(x: Any, n: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    n_val = to_float(n)
    for v in (x_val, n_val):
        if is_error(v):
            return v
    n_int = int(float(n_val))
    if n_int < 0:
        return NUM
    try:
        return bessel_i(float(x_val), n_int)
    except Exception:
        return NUM


@register_eng("BESSELK")
def fn_besselk(x: Any, n: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    n_val = to_float(n)
    for v in (x_val, n_val):
        if is_error(v):
            return v
    x_f = float(x_val)
    n_int = int(float(n_val))
    if n_int < 0 or x_f <= 0:
        return NUM
    try:
        return bessel_k(x_f, n_int)
    except Exception:
        return NUM


@register_eng("BESSELY")
def fn_bessely(x: Any, n: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    n_val = to_float(n)
    for v in (x_val, n_val):
        if is_error(v):
            return v
    x_f = float(x_val)
    n_int = int(float(n_val))
    if n_int < 0 or x_f <= 0:
        return NUM
    try:
        return bessel_y(x_f, n_int)
    except Exception:
        return NUM
