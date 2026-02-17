from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class InternalArbOpportunity:
    market_slug: str
    outcome_a: str
    outcome_b: str
    token_a: str
    token_b: str
    ask_a: float
    ask_b: float
    sum_asks: float
    fee_bps: float
    min_edge_bps: float
    edge_bps: float
    est_profit_per_dollar: float


def calc_internal_buy_both_arb(
    *,
    ask_a: float,
    ask_b: float,
    fee_bps: float,
    min_edge_bps: float,
) -> Tuple[bool, float, float]:
    """Return (ok, edge_bps, est_profit_per_dollar).

    Interpretation:
    - You buy both complementary outcomes (A and B) at their best asks.
    - At settlement, exactly one pays out $1.
    - If the total cost including assumed fees is < $1, this is a lock-in profit.

    fee_bps is modeled as a simple additive cost on notional for conservative screening.
    """
    if ask_a <= 0 or ask_b <= 0:
        return (False, 0.0, 0.0)
    if ask_a >= 1 or ask_b >= 1:
        return (False, 0.0, 0.0)

    sum_asks = ask_a + ask_b
    fee = (fee_bps / 10_000.0)
    total_cost = sum_asks * (1.0 + fee)
    profit = 1.0 - total_cost
    edge_bps = profit * 10_000.0

    ok = edge_bps >= float(min_edge_bps)
    return (ok, edge_bps, profit)


def build_internal_opportunity(
    *,
    market_slug: str,
    outcome_a: str,
    outcome_b: str,
    token_a: str,
    token_b: str,
    ask_a: float,
    ask_b: float,
    fee_bps: float,
    min_edge_bps: float,
) -> Optional[InternalArbOpportunity]:
    ok, edge_bps, profit = calc_internal_buy_both_arb(
        ask_a=ask_a, ask_b=ask_b, fee_bps=fee_bps, min_edge_bps=min_edge_bps
    )
    if not ok:
        return None

    return InternalArbOpportunity(
        market_slug=market_slug,
        outcome_a=outcome_a,
        outcome_b=outcome_b,
        token_a=token_a,
        token_b=token_b,
        ask_a=float(ask_a),
        ask_b=float(ask_b),
        sum_asks=float(ask_a + ask_b),
        fee_bps=float(fee_bps),
        min_edge_bps=float(min_edge_bps),
        edge_bps=float(edge_bps),
        est_profit_per_dollar=float(profit),
    )

