"""Probability distribution and quantile worksheet functions."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.errors import DIV0, NUM, VALUE, ExcelError, is_error
from atboffice.modules.spreadsheet.calc.statistical.common import (
    beta_i,
    gamma_p,
    gamma_q,
    invert_cdf,
    norm_cdf,
    norm_inv,
    opt,
    register_stat,
    to_float,
)


# Normal distributions
@register_stat("NORMSDIST")
@register_stat("NORM.S.DIST")
def fn_norm_s_dist(
    z: Any, cumulative: Any = True, ctx: EvalContext | None = None
) -> float | ExcelError:
    z_val = to_float(z)
    if is_error(z_val):
        return z_val
    z_f = float(z_val)
    cum = bool(cumulative)
    if cum:
        return norm_cdf(z_f)
    return math.exp(-0.5 * z_f * z_f) / math.sqrt(2.0 * math.pi)


@register_stat("NORMDIST")
@register_stat("NORM.DIST")
def fn_norm_dist(
    x: Any, mean_val: Any, stdev: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    m_val = to_float(mean_val)
    s_val = to_float(stdev)
    for v in (x_val, m_val, s_val):
        if is_error(v):
            return v
    s_f = float(s_val)
    if s_f <= 0:
        return NUM
    z = (float(x_val) - float(m_val)) / s_f
    if bool(cumulative):
        return norm_cdf(z)
    return (math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)) / s_f


@register_stat("NORMSINV")
@register_stat("NORM.S.INV")
def fn_norm_s_inv(probability: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    p_val = to_float(probability)
    if is_error(p_val):
        return p_val
    p = float(p_val)
    if p <= 0 or p >= 1:
        return NUM
    return norm_inv(p)


@register_stat("NORMINV")
@register_stat("NORM.INV")
def fn_norm_inv(
    probability: Any, mean_val: Any, stdev: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    m_val = to_float(mean_val)
    s_val = to_float(stdev)
    for v in (p_val, m_val, s_val):
        if is_error(v):
            return v
    p, m, s = float(p_val), float(m_val), float(s_val)
    if p <= 0 or p >= 1 or s <= 0:
        return NUM
    return m + s * norm_inv(p)


@register_stat("STANDARDIZE")
def fn_standardize(
    x: Any, mean_val: Any, stdev: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    m_val = to_float(mean_val)
    s_val = to_float(stdev)
    for v in (x_val, m_val, s_val):
        if is_error(v):
            return v
    s = float(s_val)
    if s <= 0:
        return NUM
    return (float(x_val) - float(m_val)) / s


@register_stat("GAUSS")
def fn_gauss(z: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    z_val = to_float(z)
    if is_error(z_val):
        return z_val
    return norm_cdf(float(z_val)) - 0.5


@register_stat("PHI")
def fn_phi(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    z = float(x_val)
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


# Confidence intervals
@register_stat("CONFIDENCE")
@register_stat("CONFIDENCE.NORM")
def fn_confidence_norm(
    alpha: Any, stdev: Any, size: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    a_val = to_float(alpha)
    s_val = to_float(stdev)
    n_val = to_float(size)
    for v in (a_val, s_val, n_val):
        if is_error(v):
            return v
    a, s, n = float(a_val), float(s_val), int(float(n_val))
    if a <= 0 or a >= 1 or s <= 0 or n < 1:
        return NUM
    return norm_inv(1.0 - a / 2.0) * s / math.sqrt(n)


@register_stat("CONFIDENCE.T")
def fn_confidence_t(
    alpha: Any, stdev: Any, size: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    a_val = to_float(alpha)
    s_val = to_float(stdev)
    n_val = to_float(size)
    for v in (a_val, s_val, n_val):
        if is_error(v):
            return v
    a, s, n = float(a_val), float(s_val), int(float(n_val))
    if a <= 0 or a >= 1 or s <= 0 or n < 2:
        return NUM
    df = n - 1

    def t_cdf(t: float) -> float:
        x = df / (df + t * t)
        tail = 0.5 * beta_i(x, df / 2.0, 0.5)
        return 1.0 - tail if t > 0 else tail

    crit = invert_cdf(t_cdf, 1.0 - a / 2.0, 0.0, 100.0)
    if is_error(crit):
        return crit
    assert isinstance(crit, float)
    return crit * s / math.sqrt(n)


# Poisson
@register_stat("POISSON")
@register_stat("POISSON.DIST")
def fn_poisson(
    x: Any, mean_val: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    m_val = to_float(mean_val)
    for v in (x_val, m_val):
        if is_error(v):
            return v
    k = int(float(x_val))
    lam = float(m_val)
    if k < 0 or lam <= 0:
        return NUM
    if bool(cumulative):
        return sum((lam**i) * math.exp(-lam) / math.factorial(i) for i in range(k + 1))
    return (lam**k) * math.exp(-lam) / math.factorial(k)


# Binomial
def binom_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


@register_stat("BINOMDIST")
@register_stat("BINOM.DIST")
def fn_binom_dist(
    number_s: Any,
    trials: Any,
    probability_s: Any,
    cumulative: Any,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    k_val = to_float(number_s)
    n_val = to_float(trials)
    p_val = to_float(probability_s)
    for v in (k_val, n_val, p_val):
        if is_error(v):
            return v
    k, n, p = int(float(k_val)), int(float(n_val)), float(p_val)
    if k < 0 or n < 0 or k > n or p < 0 or p > 1:
        return NUM
    if bool(cumulative):
        return sum(binom_pmf(i, n, p) for i in range(k + 1))
    return binom_pmf(k, n, p)


@register_stat("BINOM.DIST.RANGE")
def fn_binom_dist_range(
    trials: Any,
    probability_s: Any,
    number_s: Any,
    number_s2: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    n_val = to_float(trials)
    p_val = to_float(probability_s)
    k1_val = to_float(number_s)
    for v in (n_val, p_val, k1_val):
        if is_error(v):
            return v
    n, p, k1 = int(float(n_val)), float(p_val), int(float(k1_val))
    k2 = k1 if number_s2 is None or number_s2 == "" else int(float(to_float(number_s2)))
    if n < 0 or p < 0 or p > 1 or k1 < 0 or k1 > n or k2 < k1 or k2 > n:
        return NUM
    return sum(binom_pmf(i, n, p) for i in range(k1, k2 + 1))


@register_stat("CRITBINOM")
@register_stat("BINOM.INV")
def fn_binom_inv(
    trials: Any, probability_s: Any, alpha: Any, ctx: EvalContext | None = None
) -> int | ExcelError:
    n_val = to_float(trials)
    p_val = to_float(probability_s)
    a_val = to_float(alpha)
    for v in (n_val, p_val, a_val):
        if is_error(v):
            return v
    n, p, a = int(float(n_val)), float(p_val), float(a_val)
    if n < 0 or p < 0 or p > 1 or a <= 0 or a >= 1:
        return NUM
    cum = 0.0
    for k in range(n + 1):
        cum += binom_pmf(k, n, p)
        if cum >= a:
            return k
    return n


@register_stat("NEGBINOMDIST")
@register_stat("NEGBINOM.DIST")
def fn_negbinom_dist(
    number_f: Any,
    number_s: Any,
    probability_s: Any,
    cumulative: Any = False,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    f_val = to_float(number_f)
    s_val = to_float(number_s)
    p_val = to_float(probability_s)
    for v in (f_val, s_val, p_val):
        if is_error(v):
            return v
    f, s, p = int(float(f_val)), int(float(s_val)), float(p_val)
    if f < 0 or s < 1 or p <= 0 or p >= 1:
        return NUM

    def pmf(x: int) -> float:
        return math.comb(x + s - 1, s - 1) * (p**s) * ((1.0 - p) ** x)

    if bool(cumulative):
        return sum(pmf(i) for i in range(f + 1))
    return pmf(f)


# Exponential
@register_stat("EXPONDIST")
@register_stat("EXPON.DIST")
def fn_expon_dist(
    x: Any, lambda_val: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    l_val = to_float(lambda_val)
    for v in (x_val, l_val):
        if is_error(v):
            return v
    x_f, lam = float(x_val), float(l_val)
    if x_f < 0 or lam <= 0:
        return NUM
    if bool(cumulative):
        return 1.0 - math.exp(-lam * x_f)
    return lam * math.exp(-lam * x_f)


# Gamma
@register_stat("GAMMA")
def fn_gamma(number: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    n_val = to_float(number)
    if is_error(n_val):
        return n_val
    n = float(n_val)
    if n <= 0 and n.is_integer():
        return NUM
    try:
        return math.gamma(n)
    except Exception:
        return NUM


@register_stat("GAMMALN")
@register_stat("GAMMALN.PRECISE")
def fn_gammaln(x: Any, ctx: EvalContext | None = None) -> float | ExcelError:
    x_val = to_float(x)
    if is_error(x_val):
        return x_val
    x_f = float(x_val)
    if x_f <= 0:
        return NUM
    try:
        return math.lgamma(x_f)
    except Exception:
        return NUM


@register_stat("GAMMADIST")
@register_stat("GAMMA.DIST")
def fn_gamma_dist(
    x: Any, alpha: Any, beta: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    a_val = to_float(alpha)
    b_val = to_float(beta)
    for v in (x_val, a_val, b_val):
        if is_error(v):
            return v
    x_f, a, b = float(x_val), float(a_val), float(b_val)
    if x_f < 0 or a <= 0 or b <= 0:
        return NUM
    if bool(cumulative):
        return gamma_p(a, x_f / b)
    return (1.0 / (b**a * math.gamma(a))) * (x_f ** (a - 1.0)) * math.exp(-x_f / b)


@register_stat("GAMMAINV")
@register_stat("GAMMA.INV")
def fn_gamma_inv(
    probability: Any, alpha: Any, beta: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    a_val = to_float(alpha)
    b_val = to_float(beta)
    for v in (p_val, a_val, b_val):
        if is_error(v):
            return v
    p, a, b = float(p_val), float(a_val), float(b_val)
    if p <= 0 or p >= 1 or a <= 0 or b <= 0:
        return NUM
    res = invert_cdf(lambda y: gamma_p(a, y), p, 0.0, 1000.0)
    if is_error(res):
        return res
    assert isinstance(res, float)
    return res * b


# Beta
@register_stat("BETADIST")
@register_stat("BETA.DIST")
def fn_beta_dist(
    x: Any,
    alpha: Any,
    beta: Any,
    cumulative: Any = True,
    A: Any = None,
    B: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    x_val = to_float(x)
    a_val = to_float(alpha)
    b_val = to_float(beta)
    low_val = to_float(opt(A, 0.0))
    high_val = to_float(opt(B, 1.0))
    for v in (x_val, a_val, b_val, low_val, high_val):
        if is_error(v):
            return v
    x_f, a, b, low, high = (
        float(x_val),
        float(a_val),
        float(b_val),
        float(low_val),
        float(high_val),
    )
    if a <= 0 or b <= 0 or x_f < low or x_f > high or low >= high:
        return NUM
    norm_x = (x_f - low) / (high - low)
    if bool(cumulative):
        return beta_i(norm_x, a, b)
    front = math.exp(
        (a - 1.0) * math.log(norm_x)
        + (b - 1.0) * math.log(1.0 - norm_x)
        + math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
    )
    return front / (high - low)


@register_stat("BETAINV")
@register_stat("BETA.INV")
def fn_beta_inv(
    probability: Any,
    alpha: Any,
    beta: Any,
    A: Any = None,
    B: Any = None,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    p_val = to_float(probability)
    a_val = to_float(alpha)
    b_val = to_float(beta)
    low_val = to_float(opt(A, 0.0))
    high_val = to_float(opt(B, 1.0))
    for v in (p_val, a_val, b_val, low_val, high_val):
        if is_error(v):
            return v
    p, a, b, low, high = (
        float(p_val),
        float(a_val),
        float(b_val),
        float(low_val),
        float(high_val),
    )
    if p <= 0 or p >= 1 or a <= 0 or b <= 0 or low >= high:
        return NUM
    norm_res = invert_cdf(lambda y: beta_i(y, a, b), p, 0.0, 1.0)
    if is_error(norm_res):
        return norm_res
    assert isinstance(norm_res, float)
    return low + norm_res * (high - low)


# Weibull
@register_stat("WEIBULL")
@register_stat("WEIBULL.DIST")
def fn_weibull_dist(
    x: Any, alpha: Any, beta: Any, cumulative: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    x_val = to_float(x)
    a_val = to_float(alpha)
    b_val = to_float(beta)
    for v in (x_val, a_val, b_val):
        if is_error(v):
            return v
    x_f, a, b = float(x_val), float(a_val), float(b_val)
    if x_f < 0 or a <= 0 or b <= 0:
        return NUM
    if bool(cumulative):
        return 1.0 - math.exp(-((x_f / b) ** a))
    return (a / (b**a)) * (x_f ** (a - 1.0)) * math.exp(-((x_f / b) ** a))


# Hypergeometric
@register_stat("HYPGEOMDIST")
@register_stat("HYPGEOM.DIST")
def fn_hypgeom_dist(
    sample_s: Any,
    number_sample: Any,
    population_s: Any,
    number_pop: Any,
    cumulative: Any = False,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    x_val = to_float(sample_s)
    n_val = to_float(number_sample)
    M_val = to_float(population_s)
    N_val = to_float(number_pop)
    for v in (x_val, n_val, M_val, N_val):
        if is_error(v):
            return v
    x, n, M, N = (
        int(float(x_val)),
        int(float(n_val)),
        int(float(M_val)),
        int(float(N_val)),
    )
    if x < 0 or n < 0 or M < 0 or N < 0 or n > N or M > N or x > n or x > M:
        return NUM

    def pmf(k: int) -> float:
        if k < max(0, n - (N - M)) or k > min(n, M):
            return 0.0
        return float(math.comb(M, k) * math.comb(N - M, n - k)) / float(math.comb(N, n))

    if bool(cumulative):
        return sum(pmf(i) for i in range(x + 1))
    return pmf(x)


# Lognormal
@register_stat("LOGNORMDIST")
@register_stat("LOGNORM.DIST")
def fn_lognorm_dist(
    x: Any,
    mean_val: Any,
    stdev: Any,
    cumulative: Any = True,
    ctx: EvalContext | None = None,
) -> float | ExcelError:
    x_val = to_float(x)
    m_val = to_float(mean_val)
    s_val = to_float(stdev)
    for v in (x_val, m_val, s_val):
        if is_error(v):
            return v
    x_f, m, s = float(x_val), float(m_val), float(s_val)
    if x_f <= 0 or s <= 0:
        return NUM
    z = (math.log(x_f) - m) / s
    if bool(cumulative):
        return norm_cdf(z)
    return (math.exp(-0.5 * z * z) / (x_f * s * math.sqrt(2.0 * math.pi)))


@register_stat("LOGINV")
@register_stat("LOGNORM.INV")
def fn_lognorm_inv(
    probability: Any, mean_val: Any, stdev: Any, ctx: EvalContext | None = None
) -> float | ExcelError:
    p_val = to_float(probability)
    m_val = to_float(mean_val)
    s_val = to_float(stdev)
    for v in (p_val, m_val, s_val):
        if is_error(v):
            return v
    p, m, s = float(p_val), float(m_val), float(s_val)
    if p <= 0 or p >= 1 or s <= 0:
        return NUM
    return math.exp(m + s * norm_inv(p))
