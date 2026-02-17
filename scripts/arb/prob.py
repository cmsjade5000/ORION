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
