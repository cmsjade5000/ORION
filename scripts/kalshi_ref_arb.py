#!/usr/bin/env python3

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# When executed as `python3 scripts/kalshi_ref_arb.py`, sys.path[0] is the scripts/
# directory and the repo root may not be importable as a package. Fix up path.
try:
    from scripts.arb.exchanges import ref_spot_btc_usd, ref_spot_eth_usd  # type: ignore
    from scripts.arb.kalshi import KalshiClient, KalshiMarket, KalshiOrder  # type: ignore
    from scripts.arb.prob import prob_lognormal_greater, prob_lognormal_less  # type: ignore
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, kill_switch_tripped  # type: ignore
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.exchanges import ref_spot_btc_usd, ref_spot_eth_usd  # type: ignore
    from scripts.arb.kalshi import KalshiClient, KalshiMarket, KalshiOrder  # type: ignore
    from scripts.arb.prob import prob_lognormal_greater, prob_lognormal_less  # type: ignore
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, kill_switch_tripped  # type: ignore


@dataclass(frozen=True)
class Signal:
    ticker: str
    strike_type: str
    strike: float
    expected_expiration_time: str
    spot_ref: float
    t_years: float
    sigma_annual: float
    p_yes: float
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    no_bid: Optional[float]
    no_ask: Optional[float]
    edge_bps_buy_yes: Optional[float]
    edge_bps_buy_no: Optional[float]
    recommended: Optional[Dict[str, Any]]
    filters: Optional[Dict[str, Any]]
    rejected_reasons: Optional[List[str]]


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _parse_iso_z(ts: str) -> Optional[float]:
    # Minimal parser for "YYYY-MM-DDTHH:MM:SSZ"
    if not ts or not ts.endswith("Z"):
        return None
    try:
        # Use time.strptime which handles UTC Z with a literal.
        t = time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        return float(time.mktime(t))  # local time; we'll correct by using gmtime conversion below
    except Exception:
        return None


def _utc_epoch(ts: str) -> Optional[int]:
    if not ts or not ts.endswith("Z"):
        return None
    try:
        t = time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        return int(calendar.timegm(t))
    except Exception:
        return None


def _t_years_until(exp_iso_z: str, now_unix: Optional[int] = None) -> Optional[float]:
    exp = _utc_epoch(exp_iso_z)
    if exp is None:
        return None
    now = int(now_unix if now_unix is not None else time.time())
    dt = max(0, exp - now)
    return dt / (365.0 * 24.0 * 3600.0)


def _ref_spot_for_series(series: str) -> Optional[float]:
    s = (series or "").upper()
    if "BTC" in s or s.startswith("KXBTC") or s.startswith("BTC"):
        return ref_spot_btc_usd()
    if "ETH" in s or s.startswith("KXETH") or s.startswith("ETH"):
        return ref_spot_eth_usd()
    return None


def _signal_for_market(
    m: KalshiMarket,
    *,
    series: str,
    sigma_annual: float,
    min_edge_bps: float,
    uncertainty_bps: float,
    min_liquidity_usd: float,
    max_spread: float,
    min_seconds_to_expiry: int,
    min_price: float,
    max_price: float,
) -> Optional[Signal]:
    if m.strike_type not in ("greater", "less"):
        return None
    if m.floor_strike is None:
        return None
    if not m.expected_expiration_time:
        return None

    spot = _ref_spot_for_series(series)
    if spot is None:
        return None

    base_rejected: List[str] = []

    t_years = _t_years_until(m.expected_expiration_time)
    if t_years is None:
        return None
    tte_s = float(t_years) * 365.0 * 24.0 * 3600.0
    # Avoid trading extremely near expiry; spreads widen and fills get random.
    if tte_s < float(min_seconds_to_expiry):
        base_rejected.append("too_close_to_expiry")

    # Prefer more liquid markets; thin books are mostly noise.
    if (m.liquidity_dollars is not None) and (float(m.liquidity_dollars) < float(min_liquidity_usd)):
        base_rejected.append("liquidity_below_min")

    if m.strike_type == "greater":
        p_yes = prob_lognormal_greater(spot=spot, strike=m.floor_strike, t_years=t_years, sigma_annual=sigma_annual)
    else:
        p_yes = prob_lognormal_less(spot=spot, strike=m.floor_strike, t_years=t_years, sigma_annual=sigma_annual)

    if p_yes is None:
        return None

    p_no = 1.0 - p_yes

    yes_ask = m.yes_ask
    no_ask = m.no_ask

    # Market-quality filters: avoid extreme prices and wide spreads (slippage).
    # Note: we only filter on the side we might trade once we compute edges below.
    yes_spread = None
    no_spread = None
    if (m.yes_bid is not None) and (m.yes_ask is not None):
        yes_spread = float(m.yes_ask) - float(m.yes_bid)
    if (m.no_bid is not None) and (m.no_ask is not None):
        no_spread = float(m.no_ask) - float(m.no_bid)

    edge_yes = None
    if yes_ask is not None:
        edge_yes = (p_yes - yes_ask) * 10_000.0

    edge_no = None
    if no_ask is not None:
        edge_no = (p_no - no_ask) * 10_000.0

    recommended = None
    rejected: List[str] = []
    # Recommend buy at ask if edge clears threshold.
    if edge_yes is not None and edge_yes >= min_edge_bps:
        reasons = list(base_rejected)
        eff = float(edge_yes) - float(uncertainty_bps)
        if not (yes_ask is not None and (yes_ask >= min_price) and (yes_ask <= max_price)):
            reasons.append("yes_price_out_of_bounds")
        if (yes_spread is not None) and (yes_spread > max_spread):
            reasons.append("yes_spread_too_wide")
        if eff < float(min_edge_bps):
            reasons.append("yes_effective_edge_below_min")
        if not reasons:
            if eff >= float(min_edge_bps):
                recommended = {
                    "action": "buy",
                    "side": "yes",
                    "limit_price": f"{yes_ask:.4f}",
                    "edge_bps": edge_yes,
                    "effective_edge_bps": eff,
                    "uncertainty_bps": float(uncertainty_bps),
                }
        else:
            rejected.extend(reasons)
    if edge_no is not None and edge_no >= min_edge_bps:
        reasons = list(base_rejected)
        eff = float(edge_no) - float(uncertainty_bps)
        if not (no_ask is not None and (no_ask >= min_price) and (no_ask <= max_price)):
            reasons.append("no_price_out_of_bounds")
        if (no_spread is not None) and (no_spread > max_spread):
            reasons.append("no_spread_too_wide")
        if eff < float(min_edge_bps):
            reasons.append("no_effective_edge_below_min")
        if not reasons:
            rec2 = {"action": "buy", "side": "no", "limit_price": f"{no_ask:.4f}", "edge_bps": edge_no}
            rec2["effective_edge_bps"] = eff
            rec2["uncertainty_bps"] = float(uncertainty_bps)
            # Prefer larger edge.
            if eff >= float(min_edge_bps):
                if recommended is None or float(rec2["effective_edge_bps"]) > float(recommended.get("effective_edge_bps") or -1e9):
                    recommended = rec2
        else:
            rejected.extend(reasons)

    return Signal(
        ticker=m.ticker,
        strike_type=m.strike_type,
        strike=float(m.floor_strike),
        expected_expiration_time=m.expected_expiration_time,
        spot_ref=float(spot),
        t_years=float(t_years),
        sigma_annual=float(sigma_annual),
        p_yes=float(p_yes),
        yes_bid=m.yes_bid,
        yes_ask=m.yes_ask,
        no_bid=m.no_bid,
        no_ask=m.no_ask,
        edge_bps_buy_yes=edge_yes,
        edge_bps_buy_no=edge_no,
        recommended=recommended,
        filters={
            "min_liquidity_usd": float(min_liquidity_usd),
            "max_spread": float(max_spread),
            "min_seconds_to_expiry": int(min_seconds_to_expiry),
            "min_price": float(min_price),
            "max_price": float(max_price),
            "liquidity_dollars": m.liquidity_dollars,
            "yes_spread": yes_spread,
            "no_spread": no_spread,
        },
        rejected_reasons=sorted(list(dict.fromkeys(rejected))) if rejected else [],
    )


def cmd_scan(args: argparse.Namespace) -> int:
    kc = KalshiClient(base_url=args.kalshi_base_url)
    markets = kc.list_markets(status=args.status, series_ticker=args.series, limit=args.limit)

    sigs: List[Dict[str, Any]] = []
    for m in markets:
        s = _signal_for_market(
            m,
            series=args.series,
            sigma_annual=args.sigma_annual,
            min_edge_bps=args.min_edge_bps,
            uncertainty_bps=args.uncertainty_bps,
            min_liquidity_usd=args.min_liquidity_usd,
            max_spread=args.max_spread,
            min_seconds_to_expiry=args.min_seconds_to_expiry,
            min_price=args.min_price,
            max_price=args.max_price,
        )
        if s is None:
            continue
        sigs.append(asdict(s))

    sigs.sort(key=lambda x: max(float(x.get("edge_bps_buy_yes") or -1e9), float(x.get("edge_bps_buy_no") or -1e9)), reverse=True)

    out = {
        "mode": "scan",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "kalshi_base_url": args.kalshi_base_url,
            "series": args.series,
            "status": args.status,
            "limit": args.limit,
            "sigma_annual": args.sigma_annual,
            "min_edge_bps": args.min_edge_bps,
            "uncertainty_bps": args.uncertainty_bps,
            "min_liquidity_usd": args.min_liquidity_usd,
            "max_spread": args.max_spread,
            "min_seconds_to_expiry": args.min_seconds_to_expiry,
            "min_price": args.min_price,
            "max_price": args.max_price,
        },
        "signals": sigs,
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = RiskConfig(
        max_orders_per_run=args.max_orders_per_run,
        max_contracts_per_order=args.max_contracts_per_order,
        max_notional_per_run_usd=args.max_notional_per_run_usd,
        max_notional_per_market_usd=args.max_notional_per_market_usd,
        kill_switch_path=args.kill_switch_path,
    )

    state = RiskState(os.path.join(repo_root, "tmp", "kalshi_ref_arb", "state.json"))

    if kill_switch_tripped(cfg, repo_root):
        sys.stdout.write(_json({"mode": "trade", "status": "refused", "reason": "kill_switch"}) + "\n")
        return 2
    cd = cooldown_active(cfg, repo_root)
    if bool(cd.get("active")):
        sys.stdout.write(
            _json(
                {
                    "mode": "trade",
                    "status": "refused",
                    "reason": "cooldown",
                    "cooldown": cd,
                }
            )
            + "\n"
        )
        return 2

    kc = KalshiClient(base_url=args.kalshi_base_url)
    cash_usd = None
    if args.allow_write:
        try:
            bal = kc.get_balance()
            cash_usd = float(bal.get("balance") or 0.0) / 100.0
        except Exception:
            cash_usd = None
    markets = kc.list_markets(status=args.status, series_ticker=args.series, limit=args.limit)

    all_signals: List[Signal] = []
    signals: List[Signal] = []
    for m in markets:
        s = _signal_for_market(
            m,
            series=args.series,
            sigma_annual=args.sigma_annual,
            min_edge_bps=args.min_edge_bps,
            uncertainty_bps=args.uncertainty_bps,
            min_liquidity_usd=args.min_liquidity_usd,
            max_spread=args.max_spread,
            min_seconds_to_expiry=args.min_seconds_to_expiry,
            min_price=args.min_price,
            max_price=args.max_price,
        )
        if s is None:
            continue
        all_signals.append(s)
        if s.recommended:
            signals.append(s)

    # Observation recording for persistence gating (trade less, avoid one-off microstructure).
    now_ts = int(time.time())
    for s in signals:
        rec = s.recommended or {}
        side = rec.get("side")
        if side not in ("yes", "no"):
            continue
        try:
            eb = float(rec.get("effective_edge_bps") if rec.get("effective_edge_bps") is not None else rec.get("edge_bps"))
        except Exception:
            continue
        state.record_observation(f"{s.ticker}:{side}", edge_bps=eb, ts_unix=now_ts)

    # Highest edge first.
    signals.sort(
        key=lambda s: max(float(s.edge_bps_buy_yes or -1e9), float(s.edge_bps_buy_no or -1e9)), reverse=True
    )

    placed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    total_notional = 0.0
    order_count = 0

    # Optional: pro sizing modes (off by default).
    # We only allow scaling up when enough settlements exist (sample size gate).
    settled_gate_ok = True
    try:
        from scripts.arb.kalshi_ledger import load_ledger  # type: ignore

        led = load_ledger(repo_root)
        orders = led.get("orders") if isinstance(led, dict) else {}
        settled_n = 0
        if isinstance(orders, dict):
            for _, o in orders.items():
                if isinstance(o, dict) and isinstance(o.get("settlement"), dict):
                    settled_n += 1
        settled_gate_ok = settled_n >= int(args.min_settled_for_scaling)
    except Exception:
        settled_gate_ok = False if int(args.min_settled_for_scaling) > 0 else True

    for s in signals:
        if order_count >= cfg.max_orders_per_run:
            break

        rec = s.recommended or {}
        side = rec.get("side")
        price = float(rec.get("limit_price"))
        if side not in ("yes", "no"):
            continue
        # Persistence gate: require seeing the edge multiple cycles within a window.
        if args.persistence_cycles and int(args.persistence_cycles) > 1:
            min_ts = now_ts - int(float(args.persistence_window_min) * 60.0)
            nobs = state.count_observations(f"{s.ticker}:{side}", min_ts_unix=min_ts, min_edge_bps=float(args.min_edge_bps))
            if nobs < int(args.persistence_cycles):
                skipped.append({"ticker": s.ticker, "reason": "not_persistent", "side": side, "seen": nobs})
                continue

        # Risk: per-market cap.
        market_notional = state.market_notional_usd(s.ticker)
        remaining_market = max(0.0, cfg.max_notional_per_market_usd - market_notional)
        remaining_run = max(0.0, cfg.max_notional_per_run_usd - total_notional)
        if cash_usd is not None:
            remaining_run = min(remaining_run, max(0.0, cash_usd - total_notional))
        budget = min(remaining_market, remaining_run)
        if budget <= 0.0:
            skipped.append(
                {
                    "ticker": s.ticker,
                    "reason": "risk_cap",
                    "market_notional_usd": market_notional,
                }
            )
            continue

        # Contracts cost ~= price * count (payout $1).
        max_count_budget = int(budget / max(0.0001, price))
        count = min(cfg.max_contracts_per_order, max_count_budget)
        if count <= 0:
            skipped.append({"ticker": s.ticker, "reason": "budget_too_small", "budget_usd": budget})
            continue

        notional = price * float(count)

        if args.sizing_mode != "fixed" and not settled_gate_ok:
            # Force 1-contract probing until we have enough settled sample size.
            count = min(int(count), 1)
            notional = price * float(count)

        if args.sizing_mode == "edge_tiers" and settled_gate_ok:
            # Tier sizes by effective edge. Conservative defaults; still capped by cfg and budget.
            try:
                eff = float(rec.get("effective_edge_bps") if rec.get("effective_edge_bps") is not None else rec.get("edge_bps"))
            except Exception:
                eff = float(rec.get("edge_bps") or 0.0)
            tier = 1
            if eff >= float(args.edge_tier2_bps):
                tier = 2
            if eff >= float(args.edge_tier3_bps):
                tier = 3
            if eff >= float(args.edge_tier4_bps):
                tier = 4
            count = min(int(cfg.max_contracts_per_order), int(max_count_budget), int(tier))
            notional = price * float(count)

        client_order_id = f"orion-refarb-{int(time.time())}-{order_count}"
        order = KalshiOrder(
            ticker=s.ticker,
            side=side,
            action="buy",
            count=count,
            price_dollars=f"{price:.4f}",
            client_order_id=client_order_id,
        )

        if not args.allow_write:
            placed.append(
                {
                    "mode": "dry_run",
                    "order": asdict(order),
                    "notional_usd": notional,
                    "edge_bps": rec.get("edge_bps"),
                    "effective_edge_bps": rec.get("effective_edge_bps"),
                    "uncertainty_bps": rec.get("uncertainty_bps"),
                    "p_yes": s.p_yes,
                    "p_no": 1.0 - float(s.p_yes),
                    "t_years": s.t_years,
                    "spot_ref": s.spot_ref,
                    "sigma_annual": s.sigma_annual,
                    "strike": s.strike,
                    "strike_type": s.strike_type,
                    "expected_expiration_time": s.expected_expiration_time,
                    "filters": s.filters,
                }
            )
        else:
            try:
                resp = kc.create_order(order)
                order_id = None
                status = None
                if isinstance(resp, dict):
                    inner = resp.get("order") if isinstance(resp.get("order"), dict) else resp
                    if isinstance(inner, dict):
                        order_id = inner.get("order_id") or inner.get("id")
                        status = inner.get("status")
                placed.append(
                    {
                        "mode": "live",
                        "order": asdict(order),
                        "notional_usd": notional,
                        "edge_bps": rec.get("edge_bps"),
                        "effective_edge_bps": rec.get("effective_edge_bps"),
                        "uncertainty_bps": rec.get("uncertainty_bps"),
                        "p_yes": s.p_yes,
                        "p_no": 1.0 - float(s.p_yes),
                        "t_years": s.t_years,
                        "spot_ref": s.spot_ref,
                        "sigma_annual": s.sigma_annual,
                        "strike": s.strike,
                        "strike_type": s.strike_type,
                        "expected_expiration_time": s.expected_expiration_time,
                        "market": {
                            "yes_bid": s.yes_bid,
                            "yes_ask": s.yes_ask,
                            "no_bid": s.no_bid,
                            "no_ask": s.no_ask,
                        },
                        "filters": s.filters,
                        "order_id": order_id,
                        "status": status,
                        "resp": resp,
                    }
                )

                # Track persistent notional only when we can confirm a fill. FOK orders often cancel.
                filled_count = 0
                filled_notional = 0.0
                if isinstance(order_id, str) and order_id:
                    try:
                        fr = kc.get_fills(limit=50, order_id=order_id)
                        fills = fr.get("fills") if isinstance(fr, dict) else None
                        if isinstance(fills, list):
                            for f in fills:
                                if not isinstance(f, dict):
                                    continue
                                cnt = int(f.get("count") or f.get("quantity") or 0)
                                px = f.get("price_dollars") or f.get("yes_price_dollars") or f.get("no_price_dollars")
                                try:
                                    pxf = float(px) if px is not None else float(order.price_dollars)
                                except Exception:
                                    pxf = float(order.price_dollars)
                                if cnt > 0:
                                    filled_count += cnt
                                    filled_notional += pxf * float(cnt)
                    except Exception:
                        filled_count = 0
                        filled_notional = 0.0

                if filled_count > 0:
                    state.add_market_notional_usd(s.ticker, filled_notional)
                elif isinstance(status, str) and status.lower() in ("filled", "executed"):
                    # If the API says it filled but we couldn't fetch fills, track conservatively.
                    state.add_market_notional_usd(s.ticker, notional)
            except Exception as e:
                skipped.append({"ticker": s.ticker, "reason": "order_failed", "error": str(e), "order": asdict(order)})
                continue

        total_notional += notional
        order_count += 1

    # Diagnostics: if no trades placed, explain why.
    diagnostics: Dict[str, Any] = _compute_trade_diagnostics(all_signals, args, markets_fetched=len(markets), candidates_recommended=len(signals))

    state.append_run(
        {
            "series": args.series,
            "status": args.status,
            "sigma_annual": args.sigma_annual,
            "min_edge_bps": args.min_edge_bps,
            "allow_write": bool(args.allow_write),
            "placed": len(placed),
            "skipped": len(skipped),
            "total_notional_usd": total_notional,
        }
    )
    state.save()

    out = {
        "mode": "trade",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "kalshi_base_url": args.kalshi_base_url,
            "series": args.series,
            "status": args.status,
            "limit": args.limit,
            "sigma_annual": args.sigma_annual,
            "min_edge_bps": args.min_edge_bps,
            "uncertainty_bps": args.uncertainty_bps,
            "min_liquidity_usd": args.min_liquidity_usd,
            "max_spread": args.max_spread,
            "min_seconds_to_expiry": args.min_seconds_to_expiry,
            "min_price": args.min_price,
            "max_price": args.max_price,
            "allow_write": bool(args.allow_write),
            "risk": asdict(cfg),
        },
        "placed": placed,
        "skipped": skipped,
        "total_notional_usd": total_notional,
        "cash_usd": cash_usd,
        "diagnostics": diagnostics,
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def _compute_trade_diagnostics(
    all_signals: List[Signal],
    args: argparse.Namespace,
    *,
    markets_fetched: int,
    candidates_recommended: int,
) -> Dict[str, Any]:
    """Explain why a cycle did not trade.

    Goal: avoid misleading "best edge" candidates that are untradable due to basic filters
    (price bounds, spread, expiry, liquidity), and provide a clear reason histogram.
    """
    diagnostics: Dict[str, Any] = {
        "markets_fetched": int(markets_fetched),
        "signals_computed": len(all_signals),
        "candidates_recommended": int(candidates_recommended),
    }

    def _safe_float(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            return float(x)
        except Exception:
            return None

    def _cand_for(s: Signal, side: str) -> Optional[Dict[str, Any]]:
        ask = s.yes_ask if side == "yes" else s.no_ask
        edge = s.edge_bps_buy_yes if side == "yes" else s.edge_bps_buy_no
        if ask is None or edge is None:
            return None
        eff = float(edge) - float(args.uncertainty_bps)
        return {
            "ticker": s.ticker,
            "side": side,
            "ask": float(ask),
            "edge_bps": float(edge),
            "effective_edge_bps": float(eff),
            "tte_min": float(s.t_years) * 365.0 * 24.0 * 60.0,
            "liquidity_dollars": (s.filters or {}).get("liquidity_dollars"),
            "spread": (s.filters or {}).get("yes_spread" if side == "yes" else "no_spread"),
        }

    def _passes_non_edge_filters(s: Signal, side: str) -> bool:
        ask = s.yes_ask if side == "yes" else s.no_ask
        if ask is None:
            return False
        tte_s = float(s.t_years) * 365.0 * 24.0 * 3600.0
        if tte_s < float(args.min_seconds_to_expiry):
            return False
        liq = _safe_float((s.filters or {}).get("liquidity_dollars"))
        if liq is not None and liq < float(args.min_liquidity_usd):
            return False
        sp = _safe_float((s.filters or {}).get("yes_spread" if side == "yes" else "no_spread"))
        if sp is not None and sp > float(args.max_spread):
            return False
        if float(ask) < float(args.min_price) or float(ask) > float(args.max_price):
            return False
        return True

    # "Best" candidates.
    best_any_quote = None
    best_in_bounds = None
    best_passing_non_edge = None
    for s in all_signals:
        for side in ("yes", "no"):
            cand = _cand_for(s, side)
            if cand is None:
                continue
            if (best_any_quote is None) or (float(cand["effective_edge_bps"]) > float(best_any_quote["effective_edge_bps"])):
                best_any_quote = cand
            if float(cand["ask"]) >= float(args.min_price) and float(cand["ask"]) <= float(args.max_price):
                if (best_in_bounds is None) or (float(cand["effective_edge_bps"]) > float(best_in_bounds["effective_edge_bps"])):
                    best_in_bounds = cand
            if _passes_non_edge_filters(s, side):
                if (best_passing_non_edge is None) or (
                    float(cand["effective_edge_bps"]) > float(best_passing_non_edge["effective_edge_bps"])
                ):
                    best_passing_non_edge = cand

    diagnostics["best_effective_edge_any_quote"] = best_any_quote
    diagnostics["best_effective_edge_in_bounds"] = best_in_bounds
    diagnostics["best_effective_edge_pass_filters"] = best_passing_non_edge

    # Reason histogram.
    primary_counts: Dict[str, int] = {}
    all_reason_counts: Dict[str, int] = {}
    totals = {
        "sides_evaluated": 0,
        "quotes_present": 0,
        "pass_non_edge_filters": 0,
        "pass_all_filters": 0,
    }

    for s in all_signals:
        tte_s = float(s.t_years) * 365.0 * 24.0 * 3600.0
        liq_f = _safe_float((s.filters or {}).get("liquidity_dollars"))
        for side in ("yes", "no"):
            totals["sides_evaluated"] += 1
            ask = s.yes_ask if side == "yes" else s.no_ask
            edge = s.edge_bps_buy_yes if side == "yes" else s.edge_bps_buy_no
            spread = _safe_float((s.filters or {}).get("yes_spread" if side == "yes" else "no_spread"))

            reasons: List[str] = []
            if ask is None or edge is None:
                reasons.append(f"{side}_missing_quote")
            else:
                totals["quotes_present"] += 1
                if tte_s < float(args.min_seconds_to_expiry):
                    reasons.append("too_close_to_expiry")
                if liq_f is not None and liq_f < float(args.min_liquidity_usd):
                    reasons.append("liquidity_below_min")
                if spread is not None and spread > float(args.max_spread):
                    reasons.append(f"{side}_spread_too_wide")
                if float(ask) < float(args.min_price) or float(ask) > float(args.max_price):
                    reasons.append(f"{side}_price_out_of_bounds")
                if _passes_non_edge_filters(s, side):
                    totals["pass_non_edge_filters"] += 1
                # Edge thresholds last (least "structural").
                eff = float(edge) - float(args.uncertainty_bps)
                if float(edge) < float(args.min_edge_bps):
                    reasons.append(f"{side}_edge_below_min")
                if eff < float(args.min_edge_bps):
                    reasons.append(f"{side}_effective_edge_below_min")
                if not reasons:
                    totals["pass_all_filters"] += 1

            # Count primary + all reasons.
            primary = reasons[0] if reasons else "ok"
            primary_counts[primary] = primary_counts.get(primary, 0) + 1
            for r in reasons:
                all_reason_counts[r] = all_reason_counts.get(r, 0) + 1

    diagnostics["totals"] = totals
    diagnostics["blockers_primary"] = primary_counts
    diagnostics["blockers_all"] = all_reason_counts
    top = sorted(primary_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    diagnostics["top_blockers"] = [{"reason": k, "count": int(v)} for k, v in top]
    return diagnostics


def cmd_balance(args: argparse.Namespace) -> int:
    kc = KalshiClient(base_url=args.kalshi_base_url)
    out = {
        "mode": "balance",
        "timestamp_unix": int(time.time()),
        "inputs": {"kalshi_base_url": args.kalshi_base_url},
        "balance": kc.get_balance(),
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    kc = KalshiClient(base_url=args.kalshi_base_url)
    now = int(time.time())
    min_ts = None
    if args.hours > 0:
        min_ts = now - int(float(args.hours) * 3600.0)
    out = {
        "mode": "portfolio",
        "timestamp_unix": now,
        "inputs": {"kalshi_base_url": args.kalshi_base_url, "hours": args.hours, "limit": args.limit},
        "balance": kc.get_balance(),
        "positions": kc.get_positions(limit=args.limit),
        "orders": kc.get_orders(limit=args.limit, min_ts=min_ts),
        "fills": kc.get_fills(limit=args.limit, min_ts=min_ts),
        "settlements": kc.get_settlements(limit=args.limit, min_ts=min_ts),
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="kalshi_ref_arb.py", description="Kalshi crypto ref arb bot (scan + gated trade).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Read-only: scan Kalshi markets and emit signals.")
    scan.add_argument("--kalshi-base-url", default="https://api.elections.kalshi.com")
    scan.add_argument("--series", default="KXBTC", help="Series ticker, e.g. KXBTC")
    scan.add_argument("--status", default="open", help="Market status filter (default: open)")
    scan.add_argument("--limit", type=int, default=20)
    scan.add_argument("--sigma-annual", type=float, default=0.85, help="Annualized vol assumption (e.g. 0.85 for 85%%)")
    scan.add_argument("--min-edge-bps", type=float, default=50.0)
    scan.add_argument("--uncertainty-bps", type=float, default=0.0, help="Extra safety buffer subtracted from edge.")
    scan.add_argument("--min-liquidity-usd", type=float, default=200.0, help="Skip thin markets below this liquidity.")
    scan.add_argument("--max-spread", type=float, default=0.05, help="Max bid/ask spread allowed on trade side.")
    scan.add_argument("--min-seconds-to-expiry", type=int, default=900, help="Skip markets expiring too soon.")
    scan.add_argument("--min-price", type=float, default=0.05, help="Skip asks below this price (tail risk).")
    scan.add_argument("--max-price", type=float, default=0.95, help="Skip asks above this price (tail risk).")
    scan.set_defaults(func=cmd_scan)

    trade = sub.add_parser("trade", help="Trade mode (dry-run unless --allow-write).")
    trade.add_argument("--kalshi-base-url", default="https://api.elections.kalshi.com")
    trade.add_argument("--series", default="KXBTC")
    trade.add_argument("--status", default="open")
    trade.add_argument("--limit", type=int, default=20)
    trade.add_argument("--sigma-annual", type=float, default=0.85)
    trade.add_argument("--min-edge-bps", type=float, default=80.0)
    trade.add_argument("--uncertainty-bps", type=float, default=0.0)
    trade.add_argument("--min-liquidity-usd", type=float, default=200.0)
    trade.add_argument("--max-spread", type=float, default=0.05)
    trade.add_argument("--min-seconds-to-expiry", type=int, default=900)
    trade.add_argument("--min-price", type=float, default=0.05)
    trade.add_argument("--max-price", type=float, default=0.95)
    trade.add_argument("--persistence-cycles", type=int, default=1, help="Require edge to persist across N cycles before trading.")
    trade.add_argument("--persistence-window-min", type=float, default=30.0)
    trade.add_argument("--sizing-mode", default="fixed", choices=["fixed", "edge_tiers"], help="Position sizing mode (default fixed=1 probe).")
    trade.add_argument("--min-settled-for-scaling", type=int, default=10, help="Require at least N settled orders before scaling >1 contract.")
    trade.add_argument("--edge-tier2-bps", type=float, default=200.0)
    trade.add_argument("--edge-tier3-bps", type=float, default=300.0)
    trade.add_argument("--edge-tier4-bps", type=float, default=450.0)
    trade.add_argument("--allow-write", action="store_true", help="Enable live Kalshi order placement (requires env creds).")
    trade.add_argument("--max-orders-per-run", type=int, default=2)
    trade.add_argument("--max-contracts-per-order", type=int, default=10)
    trade.add_argument("--max-notional-per-run-usd", type=float, default=25.0)
    trade.add_argument("--max-notional-per-market-usd", type=float, default=25.0)
    trade.add_argument("--kill-switch-path", default="tmp/kalshi_ref_arb.KILL")
    trade.set_defaults(func=cmd_trade)

    bal = sub.add_parser("balance", help="Authenticated: fetch Kalshi portfolio balance (requires env creds).")
    bal.add_argument("--kalshi-base-url", default="https://api.elections.kalshi.com")
    bal.set_defaults(func=cmd_balance)

    port = sub.add_parser("portfolio", help="Authenticated: fetch balance + positions + recent orders/fills/settlements.")
    port.add_argument("--kalshi-base-url", default="https://api.elections.kalshi.com")
    port.add_argument("--hours", type=float, default=8.0, help="Lookback window for orders/fills/settlements.")
    port.add_argument("--limit", type=int, default=50)
    port.set_defaults(func=cmd_portfolio)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
