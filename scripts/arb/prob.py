from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


def _norm_cdf(x: float) -> float:
    # Standard normal CDF via erf.
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def prob_lognormal_greater(
    *,
    spot: float,
    strike: float,
    t_years: float,
    sigma_annual: float,
) -> Optional[float]:
    """Approximate P(S_T > K) under lognormal with zero drift and volatility sigma_annual.

    Returns None if inputs are invalid.
    """
    if spot <= 0 or strike <= 0:
        return None
    if t_years <= 0:
        return 1.0 if spot > strike else 0.0
    if sigma_annual <= 0:
        return 1.0 if spot > strike else 0.0

    sig = float(sigma_annual)
    t = float(t_years)
    denom = sig * math.sqrt(t)
    if denom <= 0:
        return 1.0 if spot > strike else 0.0

    d2 = (math.log(spot / strike) - 0.5 * sig * sig * t) / denom
    p = _norm_cdf(d2)
    # Clamp for numeric safety.
    return max(0.0, min(1.0, p))


def prob_lognormal_less(
    *,
    spot: float,
    strike: float,
    t_years: float,
    sigma_annual: float,
) -> Optional[float]:
    p = prob_lognormal_greater(spot=spot, strike=strike, t_years=t_years, sigma_annual=sigma_annual)
    if p is None:
        return None
    return 1.0 - p


def prob_lognormal_between(
    *,
    spot: float,
    lower: float,
    upper: float,
    t_years: float,
    sigma_annual: float,
) -> Optional[float]:
    """Approximate P(lower <= S_T <= upper) under lognormal with zero drift."""
    if lower <= 0 or upper <= 0:
        return None
    lo = float(min(lower, upper))
    hi = float(max(lower, upper))
    if hi <= lo:
        return 0.0
    p_hi = prob_lognormal_less(spot=spot, strike=hi, t_years=t_years, sigma_annual=sigma_annual)
    p_lo = prob_lognormal_less(spot=spot, strike=lo, t_years=t_years, sigma_annual=sigma_annual)
    if p_hi is None or p_lo is None:
        return None
    # P(lo <= X <= hi) = P(X <= hi) - P(X < lo). We use <= for both; difference is negligible.
    p = float(p_hi) - float(p_lo)
    return max(0.0, min(1.0, p))


@dataclass(frozen=True)
class KalshiFair:
    p_yes: float
    p_no: float


def clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.0


def beta_posterior_mean(*, p_prior: float, k_prior: float, p_obs: float, k_obs: float) -> float:
    """Return posterior mean of a Beta distribution updated with a fractional observation.

    We treat:
    - prior as Beta(alpha0, beta0) with concentration k_prior.
    - observation as a pseudo-count update of size k_obs at rate p_obs.
    """
    p0 = clamp01(float(p_prior))
    po = clamp01(float(p_obs))
    kp = max(0.0, float(k_prior))
    ko = max(0.0, float(k_obs))
    # Avoid alpha/beta==0 edge cases for p=0 or p=1.
    eps = 1e-6
    a0 = max(eps, p0 * kp)
    b0 = max(eps, (1.0 - p0) * kp)
    a1 = a0 + po * ko
    b1 = b0 + (1.0 - po) * ko
    den = a1 + b1
    if den <= 0:
        return p0
    return clamp01(a1 / den)


def kelly_fraction_binary(*, p_win: float, price: float) -> float:
    """Full-Kelly stake fraction for a $1 payout contract bought for `price`.

    If you pay `price` now:
    - Win (prob p): + (1 - price)
    - Lose: - price

    The full-Kelly stake fraction (in dollars staked / bankroll) is:
      f* = (p - price) / (1 - price)
    """
    p = clamp01(float(p_win))
    a = clamp01(float(price))
    if a >= 0.999999:
        return 0.0
    f = (p - a) / max(1e-9, (1.0 - a))
    return max(0.0, min(1.0, float(f)))
