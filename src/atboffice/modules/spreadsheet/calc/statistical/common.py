"""Shared numerical and statistical functions for Ledger calculation engine."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import to_num
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    NUM,
    VALUE,
    ExcelError,
    is_error,
)

STATISTICAL_FUNCTIONS: dict[str, Callable[..., Any]] = {}


def register_stat(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a statistical function by name."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        STATISTICAL_FUNCTIONS[name.upper()] = fn
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


# --- Special functions for distributions ---
TINY = 1e-300


def cont_frac(
    b0: float, terms: Callable[[int], tuple[float, float]], max_iter: int = 3000
) -> float:
    f = b0 or TINY
    c = f
    d = 0.0
    for j in range(1, max_iter + 1):
        aj, bj = terms(j)
        d = bj + aj * d
        d = (1.0 / TINY) if d == 0.0 else (1.0 / d)
        c = bj + aj / c
        if c == 0.0:
            c = TINY
        step = c * d
        f *= step
        if abs(step - 1.0) < 1e-16:
            break
    return f


def gamma_p(a: float, x: float) -> float:
    if x <= 0:
        return 0.0
    front = math.exp(a * math.log(x) - x - math.lgamma(a))
    if x < a + 1.0:
        term = 1.0 / a
        total = term
        for n in range(1, 1000):
            term *= x / (a + n)
            total += term
            if abs(term) < abs(total) * 1e-16:
                break
        return total * front
    else:

        def terms(j: int) -> tuple[float, float]:
            if j == 1:
                return (1.0, x + 1.0 - a)
            k = j - 1
            return (-k * (k - a), x + 2.0 * j - 1.0 - a)

        frac = front * cont_frac(0.0, terms)
        return 1.0 - frac


def gamma_q(a: float, x: float) -> float:
    return 1.0 - gamma_p(a, x)


def beta_i(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - beta_i(1.0 - x, b, a)

    front = (
        math.exp(
            a * math.log(x)
            + b * math.log(1.0 - x)
            + math.lgamma(a + b)
            - math.lgamma(a)
            - math.lgamma(b)
        )
        / a
    )

    def terms(j: int) -> tuple[float, float]:
        if j == 1:
            return (1.0, 1.0)
        k = j - 1
        m = k >> 1
        if k % 2 == 1:
            num = -((a + m) * (a + b + m) * x) / ((a + 2.0 * m) * (a + 2.0 * m + 1.0))
        else:
            num = (m * (b - m) * x) / ((a + 2.0 * m - 1.0) * (a + 2.0 * m))
        return (num, 1.0)

    return front * cont_frac(0.0, terms)


def invert_cdf(cdf: Callable[[float], float], p: float, lo: float, hi: float) -> float | ExcelError:
    flo = cdf(lo) - p
    fhi = cdf(hi) - p
    guard = 0
    while flo * fhi > 0 and guard < 200:
        hi = hi * 2.0 + 1.0
        fhi = cdf(hi) - p
        guard += 1
    if flo * fhi > 0:
        return NUM

    for _ in range(300):
        mid = (lo + hi) / 2.0
        f = cdf(mid) - p
        if f == 0.0 or abs(f) < 1e-15 * min(p, 1.0) or (hi - lo) <= 1e-15 * max(1.0, abs(mid)):
            return mid
        if (f < 0.0) == (flo < 0.0):
            lo, flo = mid, f
        else:
            hi = mid
    return (lo + hi) / 2.0


def norm_cdf(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def norm_inv(p: float) -> float:
    if not (0.0 < p < 1.0):
        return float("nan")
    if p == 0.5:
        return 0.0
    q = min(p, 1.0 - p)
    t = math.sqrt(-2.0 * math.log(q))
    x = t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / (
        1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t
    )
    for _ in range(8):
        err = 0.5 * math.erfc(x / math.sqrt(2.0)) - q
        phi = math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
        u = err / phi
        step = u / (1.0 - 0.5 * x * u)
        x += step
        if abs(step) <= 1e-16 * abs(x):
            break
    return -x if p < 0.5 else x


def collect_stat_numbers(
    args: tuple[Any, ...] | list[Any],
    ctx: EvalContext | None = None,
    include_text_bool: bool = False,
) -> list[float] | ExcelError:
    """Collect numbers from args according to Excel statistical rules."""
    out: list[float] = []

    def process(item: Any, is_direct: bool) -> ExcelError | None:
        if is_error(item):
            return item
        if isinstance(item, Ref):
            for r in range(item.r1, item.r2 + 1):
                for c in range(item.c1, item.c2 + 1):
                    err = process(item.cell_value(r, c), False)
                    if err:
                        return err
            return None
        if isinstance(item, Arr):
            for row in item.data:
                for v in row:
                    err = process(v, False)
                    if err:
                        return err
            return None
        if isinstance(item, (list, tuple)):
            for v in item:
                err = process(v, is_direct)
                if err:
                    return err
            return None

        if isinstance(item, bool):
            if is_direct or include_text_bool:
                out.append(1.0 if item else 0.0)
            return None
        if isinstance(item, (int, float)):
            out.append(float(item))
            return None
        if isinstance(item, str):
            if is_direct:
                v = to_float(item)
                if is_error(v):
                    return v
                out.append(float(v))
            elif include_text_bool:
                out.append(0.0)
            return None
        return None

    for a in args:
        err = process(a, True)
        if err:
            return err
    return out


def mean(data: list[float]) -> float:
    return sum(data) / len(data)


def devsq(data: list[float]) -> float:
    m = mean(data)
    return sum((x - m) ** 2 for x in data)
