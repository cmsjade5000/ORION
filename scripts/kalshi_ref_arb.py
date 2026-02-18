#!/usr/bin/env python3

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# When executed as `python3 scripts/kalshi_ref_arb.py`, sys.path[0] is the scripts/
# directory and the repo root may not be importable as a package. Fix up path.
try:
    from scripts.arb.exchanges import ref_spot_btc_usd, ref_spot_doge_usd, ref_spot_eth_usd, ref_spot_xrp_usd  # type: ignore
    from scripts.arb.kalshi import KalshiClient, KalshiMarket, KalshiNoFillError, KalshiOrder  # type: ignore
    from scripts.arb.live_spot import live_spot  # type: ignore
    from scripts.arb.momentum import momentum_pct, update_ref_spot_history  # type: ignore
    from scripts.arb.prob import (  # type: ignore
        beta_posterior_mean,
        kelly_fraction_binary,
        prob_lognormal_between,
        prob_lognormal_greater,
        prob_lognormal_less,
    )
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, kill_switch_tripped  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.exchanges import ref_spot_btc_usd, ref_spot_doge_usd, ref_spot_eth_usd, ref_spot_xrp_usd  # type: ignore
    from scripts.arb.kalshi import KalshiClient, KalshiMarket, KalshiNoFillError, KalshiOrder  # type: ignore
    from scripts.arb.live_spot import live_spot  # type: ignore
    from scripts.arb.momentum import momentum_pct, update_ref_spot_history  # type: ignore
    from scripts.arb.prob import (  # type: ignore
        beta_posterior_mean,
        kelly_fraction_binary,
        prob_lognormal_between,
        prob_lognormal_greater,
        prob_lognormal_less,
    )
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, kill_switch_tripped  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore


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
    strike_high: Optional[float] = None
    # Best-effort confidence signals:
    p_yes_posterior: Optional[float] = None
    posterior_k_obs: Optional[float] = None
    vol_anomaly_ratio: Optional[float] = None
    momentum_15m_pct: Optional[float] = None
    momentum_60m_pct: Optional[float] = None


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


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


def _model_p_yes(
    *,
    strike_type: str,
    strike: float,
    strike_high: Optional[float],
    spot: float,
    t_years: float,
    sigma_annual: float,
) -> Optional[float]:
    st = str(strike_type or "").strip().lower()
    if spot <= 0.0 or t_years < 0.0 or sigma_annual <= 0.0:
        return None
    if st == "greater":
        return prob_lognormal_greater(spot=float(spot), strike=float(strike), t_years=float(t_years), sigma_annual=float(sigma_annual))
    if st == "less":
        return prob_lognormal_less(spot=float(spot), strike=float(strike), t_years=float(t_years), sigma_annual=float(sigma_annual))
    if st == "between":
        if strike_high is None:
            return None
        return prob_lognormal_between(
            spot=float(spot),
            lower=float(strike),
            upper=float(strike_high),
            t_years=float(t_years),
            sigma_annual=float(sigma_annual),
        )
    return None


def _ref_spot_for_series(series: str) -> Optional[float]:
    s = (series or "").upper()
    if "BTC" in s or s.startswith("KXBTC") or s.startswith("BTC"):
        return ref_spot_btc_usd()
    if "ETH" in s or s.startswith("KXETH") or s.startswith("ETH"):
        return ref_spot_eth_usd()
    if "XRP" in s or s.startswith("KXXRP") or s.startswith("XRP"):
        return ref_spot_xrp_usd()
    if "DOGE" in s or s.startswith("KXDOGE") or s.startswith("DOGE"):
        return ref_spot_doge_usd()
    return None


def _signal_for_market(
    m: KalshiMarket,
    *,
    series: str,
    spot: Optional[float] = None,
    sigma_annual: float,
    min_edge_bps: float,
    uncertainty_bps: float,
    min_liquidity_usd: float,
    max_spread: float,
    min_seconds_to_expiry: int,
    min_price: float,
    max_price: float,
    min_notional_usd: float,
    min_notional_bypass_edge_bps: float,
    bayes_prior_k: float = 20.0,
    bayes_obs_k_max: float = 30.0,
    vol_anomaly_ratio: Optional[float] = None,
    momentum_15m_pct: Optional[float] = None,
    momentum_60m_pct: Optional[float] = None,
) -> Optional[Signal]:
    if m.strike_type not in ("greater", "less", "between"):
        return None
    if not m.expected_expiration_time:
        return None

    spot_ref = float(spot) if isinstance(spot, (int, float)) else _ref_spot_for_series(series)
    if spot_ref is None:
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

    strike = None
    strike_high = None
    if m.strike_type == "greater":
        if m.floor_strike is None:
            return None
        strike = float(m.floor_strike)
        p_yes = _model_p_yes(strike_type="greater", strike=strike, strike_high=None, spot=float(spot_ref), t_years=t_years, sigma_annual=sigma_annual)
    elif m.strike_type == "less":
        # Kalshi uses cap_strike for "or below" markets.
        if m.cap_strike is None:
            return None
        strike = float(m.cap_strike)
        p_yes = _model_p_yes(strike_type="less", strike=strike, strike_high=None, spot=float(spot_ref), t_years=t_years, sigma_annual=sigma_annual)
    else:
        # between: floor_strike is lower, cap_strike is upper.
        if m.floor_strike is None or m.cap_strike is None:
            return None
        strike = float(m.floor_strike)
        strike_high = float(m.cap_strike)
        p_yes = _model_p_yes(
            strike_type="between",
            strike=float(m.floor_strike),
            strike_high=float(m.cap_strike),
            spot=float(spot_ref),
            t_years=t_years,
            sigma_annual=sigma_annual,
        )

    if p_yes is None:
        return None

    # Bayesian posterior (best-effort): treat the market mid as a noisy observation of probability.
    # We keep p_yes (model) for edge detection; use posterior for sizing/confidence.
    p_yes_model = float(p_yes)
    p_yes_post: Optional[float] = None
    k_obs: Optional[float] = None

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

    try:
        yes_mid = None
        if (m.yes_bid is not None) and (m.yes_ask is not None):
            yes_mid = 0.5 * (float(m.yes_bid) + float(m.yes_ask))
        # Observation strength: scales with liquidity and tighter spreads, capped.
        if yes_mid is not None and m.liquidity_dollars is not None and yes_spread is not None:
            liq = max(0.0, float(m.liquidity_dollars))
            spread = max(0.0, float(yes_spread))
            tight = max(0.0, min(1.0, 1.0 - (spread / max(1e-9, float(max_spread)))))
            ko = min(float(bayes_obs_k_max), (liq / 750.0) * 5.0 * tight)
            # Vol regime penalty: if vol spikes vs baseline, treat observation as noisier.
            if isinstance(vol_anomaly_ratio, (int, float)) and float(vol_anomaly_ratio) > 1.0:
                ko = ko / float(min(3.0, max(1.0, float(vol_anomaly_ratio))))
            if ko > 0.0:
                p_yes_post = beta_posterior_mean(
                    p_prior=p_yes_model,
                    k_prior=float(bayes_prior_k),
                    p_obs=float(yes_mid),
                    k_obs=float(ko),
                )
                k_obs = float(ko)
    except Exception:
        p_yes_post = None
        k_obs = None

    p_no = 1.0 - p_yes_model
    p_no_post = 1.0 - float(p_yes_post) if isinstance(p_yes_post, (int, float)) else None

    edge_yes = None
    if yes_ask is not None:
        edge_yes = (p_yes_model - yes_ask) * 10_000.0

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
        # Fee-aware gate: very low-notional orders are dominated by fees. Allow only if edge is huge.
        if float(min_notional_usd) > 0.0 and yes_ask is not None:
            notional_1x = float(yes_ask)
            if notional_1x < float(min_notional_usd) and eff < float(min_notional_bypass_edge_bps):
                reasons.append("yes_notional_below_min")
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
                    "p_yes_model": float(p_yes_model),
                    "p_yes_posterior": float(p_yes_post) if isinstance(p_yes_post, (int, float)) else None,
                    "posterior_k_obs": float(k_obs) if isinstance(k_obs, (int, float)) else None,
                }
        else:
            rejected.extend(reasons)
    if edge_no is not None and edge_no >= min_edge_bps:
        reasons = list(base_rejected)
        eff = float(edge_no) - float(uncertainty_bps)
        if not (no_ask is not None and (no_ask >= min_price) and (no_ask <= max_price)):
            reasons.append("no_price_out_of_bounds")
        # Fee-aware gate: very low-notional orders are dominated by fees. Allow only if edge is huge.
        if float(min_notional_usd) > 0.0 and no_ask is not None:
            notional_1x = float(no_ask)
            if notional_1x < float(min_notional_usd) and eff < float(min_notional_bypass_edge_bps):
                reasons.append("no_notional_below_min")
        if (no_spread is not None) and (no_spread > max_spread):
            reasons.append("no_spread_too_wide")
        if eff < float(min_edge_bps):
            reasons.append("no_effective_edge_below_min")
        if not reasons:
            rec2 = {"action": "buy", "side": "no", "limit_price": f"{no_ask:.4f}", "edge_bps": edge_no}
            rec2["effective_edge_bps"] = eff
            rec2["uncertainty_bps"] = float(uncertainty_bps)
            rec2["p_no_model"] = float(p_no)
            rec2["p_no_posterior"] = float(p_no_post) if isinstance(p_no_post, (int, float)) else None
            rec2["posterior_k_obs"] = float(k_obs) if isinstance(k_obs, (int, float)) else None
            # Prefer larger edge.
            if eff >= float(min_edge_bps):
                if recommended is None or float(rec2["effective_edge_bps"]) > float(recommended.get("effective_edge_bps") or -1e9):
                    recommended = rec2
        else:
            rejected.extend(reasons)

    return Signal(
        ticker=m.ticker,
        strike_type=m.strike_type,
        strike=float(strike),
        strike_high=float(strike_high) if strike_high is not None else None,
        expected_expiration_time=m.expected_expiration_time,
        spot_ref=float(spot_ref),
        t_years=float(t_years),
        sigma_annual=float(sigma_annual),
        p_yes=float(p_yes_model),
        p_yes_posterior=float(p_yes_post) if isinstance(p_yes_post, (int, float)) else None,
        posterior_k_obs=float(k_obs) if isinstance(k_obs, (int, float)) else None,
        vol_anomaly_ratio=float(vol_anomaly_ratio) if isinstance(vol_anomaly_ratio, (int, float)) else None,
        momentum_15m_pct=float(momentum_15m_pct) if isinstance(momentum_15m_pct, (int, float)) else None,
        momentum_60m_pct=float(momentum_60m_pct) if isinstance(momentum_60m_pct, (int, float)) else None,
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
            "min_notional_usd": float(min_notional_usd),
            "min_notional_bypass_edge_bps": float(min_notional_bypass_edge_bps),
            "liquidity_dollars": m.liquidity_dollars,
            "yes_spread": yes_spread,
            "no_spread": no_spread,
            "strike_high": float(strike_high) if strike_high is not None else None,
        },
        rejected_reasons=sorted(list(dict.fromkeys(rejected))) if rejected else [],
    )


def cmd_scan(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    kc = KalshiClient(base_url=args.kalshi_base_url)
    markets = kc.list_markets(status=args.status, series_ticker=args.series, limit=args.limit)
    # Fetch spot once per scan. Previously this was done per-market, which is slow and can
    # trigger scan timeouts.
    spot = _ref_spot_for_series(args.series)
    if spot is not None:
        try:
            update_ref_spot_history(repo_root, series=args.series, spot_ref=float(spot), ts_unix=int(time.time()))
        except Exception:
            pass
    m15 = None
    m60 = None
    try:
        if spot is not None:
            m15 = momentum_pct(repo_root, series=args.series, lookback_s=15 * 60, spot_ref_now=float(spot))
            m60 = momentum_pct(repo_root, series=args.series, lookback_s=60 * 60, spot_ref_now=float(spot))
    except Exception:
        m15 = None
        m60 = None
    vol_ratio = None
    if bool(getattr(args, "vol_anomaly", False)):
        try:
            short = conservative_sigma_auto(args.series, window_hours=int(args.vol_anomaly_window_h))
        except Exception:
            short = None
        try:
            base = float(args.sigma_annual)
        except Exception:
            base = None
        if short is not None and base and base > 0:
            vol_ratio = float(short) / float(base)

    sigs: List[Dict[str, Any]] = []
    for m in markets:
        s = _signal_for_market(
            m,
            series=args.series,
            spot=spot,
            sigma_annual=args.sigma_annual,
            min_edge_bps=args.min_edge_bps,
            uncertainty_bps=args.uncertainty_bps,
            min_liquidity_usd=args.min_liquidity_usd,
            max_spread=args.max_spread,
            min_seconds_to_expiry=args.min_seconds_to_expiry,
            min_price=args.min_price,
            max_price=args.max_price,
            min_notional_usd=args.min_notional_usd,
            min_notional_bypass_edge_bps=args.min_notional_bypass_edge_bps,
            bayes_prior_k=float(getattr(args, "bayes_prior_k", 20.0) or 20.0),
            bayes_obs_k_max=float(getattr(args, "bayes_obs_k_max", 30.0) or 30.0),
            vol_anomaly_ratio=vol_ratio,
            momentum_15m_pct=m15,
            momentum_60m_pct=m60,
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
            "min_notional_usd": args.min_notional_usd,
            "min_notional_bypass_edge_bps": args.min_notional_bypass_edge_bps,
            "spot_ref": float(spot) if isinstance(spot, (int, float)) else None,
            "momentum_15m_pct": float(m15) if isinstance(m15, (int, float)) else None,
            "momentum_60m_pct": float(m60) if isinstance(m60, (int, float)) else None,
        },
        "signals": sigs,
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
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

    # Optional: cap stacking into the same ticker (avoid accidental averaging down).
    max_open_per_ticker = int(getattr(args, "max_open_contracts_per_ticker", 0) or 0)
    open_abs_pos: Dict[str, int] = {}
    positions_loaded = False

    def _ensure_positions_loaded() -> None:
        nonlocal positions_loaded, open_abs_pos
        if positions_loaded:
            return
        positions_loaded = True
        if (not args.allow_write) or max_open_per_ticker <= 0:
            return
        try:
            pos = kc.get_positions(limit=200)
            items = pos.get("market_positions") if isinstance(pos, dict) else None
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    t = it.get("ticker") or it.get("market_ticker")
                    if not isinstance(t, str) or not t:
                        continue
                    try:
                        p = int(it.get("position") or it.get("count") or 0)
                    except Exception:
                        p = 0
                    open_abs_pos[t] = max(open_abs_pos.get(t, 0), abs(int(p)))
        except Exception:
            open_abs_pos = {}
    markets = kc.list_markets(status=args.status, series_ticker=args.series, limit=args.limit)
    # Fetch spot once per run (instead of per-market).
    spot = _ref_spot_for_series(args.series)
    if spot is not None:
        try:
            update_ref_spot_history(repo_root, series=args.series, spot_ref=float(spot), ts_unix=int(time.time()))
        except Exception:
            pass
    m15 = None
    m60 = None
    try:
        if spot is not None:
            m15 = momentum_pct(repo_root, series=args.series, lookback_s=15 * 60, spot_ref_now=float(spot))
            m60 = momentum_pct(repo_root, series=args.series, lookback_s=60 * 60, spot_ref_now=float(spot))
    except Exception:
        m15 = None
        m60 = None
    vol_ratio = None
    if bool(getattr(args, "vol_anomaly", False)):
        try:
            short = conservative_sigma_auto(args.series, window_hours=int(args.vol_anomaly_window_h))
        except Exception:
            short = None
        try:
            base = float(args.sigma_annual)
        except Exception:
            base = None
        if short is not None and base and base > 0:
            vol_ratio = float(short) / float(base)

    all_signals: List[Signal] = []
    signals: List[Signal] = []
    for m in markets:
        s = _signal_for_market(
            m,
            series=args.series,
            spot=spot,
            sigma_annual=args.sigma_annual,
            min_edge_bps=args.min_edge_bps,
            uncertainty_bps=args.uncertainty_bps,
            min_liquidity_usd=args.min_liquidity_usd,
            max_spread=args.max_spread,
            min_seconds_to_expiry=args.min_seconds_to_expiry,
            min_price=args.min_price,
            max_price=args.max_price,
            min_notional_usd=args.min_notional_usd,
            min_notional_bypass_edge_bps=args.min_notional_bypass_edge_bps,
            bayes_prior_k=float(getattr(args, "bayes_prior_k", 20.0) or 20.0),
            bayes_obs_k_max=float(getattr(args, "bayes_obs_k_max", 30.0) or 30.0),
            vol_anomaly_ratio=vol_ratio,
            momentum_15m_pct=m15,
            momentum_60m_pct=m60,
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

    # Optional: diversify orders across time-to-expiry buckets so we don't only target the
    # nearest microstructure-heavy markets.
    #
    # Env format: "30-90,90-180,180-360" in minutes.
    def _parse_tte_buckets(raw: str) -> List[tuple[float, float]]:
        out: List[tuple[float, float]] = []
        for part in (raw or "").split(","):
            part = part.strip()
            if not part:
                continue
            if "-" not in part:
                continue
            a, b = part.split("-", 1)
            try:
                lo = float(a.strip())
                hi = float(b.strip())
            except Exception:
                continue
            if hi <= lo or lo < 0:
                continue
            out.append((lo, hi))
        return out

    raw_buckets = (os.environ.get("KALSHI_ARB_TTE_BUCKETS_MIN") or "").strip()
    buckets = _parse_tte_buckets(raw_buckets) if raw_buckets else []
    if buckets and len(signals) > 1:
        def _tte_min(s: Signal) -> float:
            try:
                return float(s.t_years) * 365.0 * 24.0 * 60.0
            except Exception:
                return 0.0

        best_per_bucket: List[Signal] = []
        used = set()
        # Pick one best signal per bucket in bucket order.
        for bi, (lo, hi) in enumerate(buckets):
            for s in signals:
                if s.ticker in used:
                    continue
                tte = _tte_min(s)
                if tte >= float(lo) and tte < float(hi):
                    best_per_bucket.append(s)
                    used.add(s.ticker)
                    break
        # Then append remaining by edge.
        if best_per_bucket:
            tail = [s for s in signals if s.ticker not in used]
            signals = best_per_bucket + tail

    placed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    total_notional = 0.0
    # Count order attempts (not only successful placements) so risk caps apply even
    # when the API rejects an order.
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

        if args.sizing_mode == "kelly" and settled_gate_ok:
            # Fractional Kelly sizing:
            # - Use Bayesian posterior prob if present, else model prob.
            # - Convert to stake fraction and cap hard by both budget and configured caps.
            try:
                if side == "yes":
                    p_win = float(rec.get("p_yes_posterior")) if rec.get("p_yes_posterior") is not None else float(rec.get("p_yes_model") or s.p_yes)
                else:
                    p_win = float(rec.get("p_no_posterior")) if rec.get("p_no_posterior") is not None else float(rec.get("p_no_model") or (1.0 - float(s.p_yes)))
            except Exception:
                p_win = float(1.0 - float(s.p_yes)) if side == "no" else float(s.p_yes)
            f_star = kelly_fraction_binary(p_win=float(p_win), price=float(price))
            kelly_frac = float(getattr(args, "kelly_fraction", 0.10) or 0.10)
            kelly_cap = float(getattr(args, "kelly_cap_fraction", 0.10) or 0.10)
            bankroll = float(cash_usd) if isinstance(cash_usd, (int, float)) and cash_usd > 0 else float(cfg.max_notional_per_run_usd)
            f = max(0.0, min(float(kelly_cap), float(f_star) * float(kelly_frac)))
            target_notional = min(float(budget), max(0.0, bankroll * f))
            # Keep at least a 1-contract probe if budget allows.
            k_count = int(target_notional / max(0.0001, price))
            k_count = max(1, k_count)
            count = min(int(cfg.max_contracts_per_order), int(max_count_budget), int(k_count))
            notional = price * float(count)

        # Cap stacking per ticker (based on current open position).
        if max_open_per_ticker > 0:
            _ensure_positions_loaded()
            existing = int(open_abs_pos.get(s.ticker) or 0)
            if existing >= max_open_per_ticker:
                skipped.append(
                    {
                        "ticker": s.ticker,
                        "reason": "position_cap_ticker",
                        "existing_open": existing,
                        "cap": int(max_open_per_ticker),
                        "requested_count": int(count),
                    }
                )
                continue
            if (existing + int(count)) > max_open_per_ticker:
                new_count = max(0, int(max_open_per_ticker) - existing)
                if new_count <= 0:
                    skipped.append(
                        {
                            "ticker": s.ticker,
                            "reason": "position_cap_ticker",
                            "existing_open": existing,
                            "cap": int(max_open_per_ticker),
                            "requested_count": int(count),
                        }
                    )
                    continue
                count = int(new_count)
                notional = price * float(count)

        # Must be unique even if the API rejects an order, otherwise retries can 4xx.
        client_order_id = f"orion-refarb-{int(time.time()*1000)}-{order_count}-{uuid.uuid4().hex[:8]}"
        order = KalshiOrder(
            ticker=s.ticker,
            side=side,
            action="buy",
            count=count,
            price_dollars=f"{price:.4f}",
            client_order_id=client_order_id,
        )

        # Enforce max_orders_per_run based on attempts, not only successful placements.
        order_count += 1

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
                    "strike_high": s.strike_high,
                    "strike_type": s.strike_type,
                    "expected_expiration_time": s.expected_expiration_time,
                    "filters": s.filters,
                }
            )
        else:
            try:
                live = None
                spot_live = None
                spot_live_err = ""
                # Optional: use a sub-second live ref spot (WS) to reprice p and edge right before ordering.
                try:
                    live = live_spot(args.series)
                except Exception:
                    live = None
                if live is not None and getattr(live, "ok", False):
                    try:
                        spot_live = float(getattr(live, "price"))
                    except Exception:
                        spot_live = None
                elif live is not None:
                    spot_live_err = str(getattr(live, "error", "") or "")

                # Freshness / recheck guard: refetch the market right before sending a live order
                # and ensure the edge + microstructure filters still hold.
                try:
                    m2 = kc.get_market(s.ticker)
                except Exception:
                    m2 = None
                if m2 is None:
                    skipped.append({"ticker": s.ticker, "reason": "recheck_failed", "detail": "market_fetch_none"})
                    continue

                # Use the freshest ask/bid for the side we plan to buy.
                ask2 = m2.yes_ask if side == "yes" else m2.no_ask
                bid2 = m2.yes_bid if side == "yes" else m2.no_bid
                if ask2 is None:
                    skipped.append({"ticker": s.ticker, "reason": "recheck_failed", "detail": "ask_missing", "side": side})
                    continue
                # Price bounds
                if float(ask2) < float(args.min_price) or float(ask2) > float(args.max_price):
                    skipped.append(
                        {
                            "ticker": s.ticker,
                            "reason": "recheck_failed",
                            "detail": "price_out_of_bounds",
                            "side": side,
                            "ask": float(ask2),
                        }
                    )
                    continue
                # Spread
                if bid2 is not None:
                    sp2 = float(ask2) - float(bid2)
                    if sp2 > float(args.max_spread):
                        skipped.append(
                            {
                                "ticker": s.ticker,
                                "reason": "recheck_failed",
                                "detail": "spread_too_wide",
                                "side": side,
                                "spread": float(sp2),
                            }
                        )
                        continue
                # Edge recompute:
                # - price from fresh quote
                # - probability repriced from live spot (if available) else original spot snapshot
                p_yes2 = None
                try:
                    px = float(spot_live) if isinstance(spot_live, (int, float)) and float(spot_live) > 0 else float(s.spot_ref)
                    p_yes2 = _model_p_yes(
                        strike_type=str(s.strike_type),
                        strike=float(s.strike),
                        strike_high=float(s.strike_high) if s.strike_high is not None else None,
                        spot=float(px),
                        t_years=float(s.t_years),
                        sigma_annual=float(s.sigma_annual),
                    )
                except Exception:
                    p_yes2 = None
                if p_yes2 is None:
                    p_yes2 = float(s.p_yes)

                p = float(p_yes2) if side == "yes" else (1.0 - float(p_yes2))
                edge2 = (p - float(ask2)) * 10_000.0
                eff2 = float(edge2) - float(args.uncertainty_bps)
                if eff2 < float(args.min_edge_bps):
                    skipped.append(
                        {
                            "ticker": s.ticker,
                            "reason": "recheck_failed",
                            "detail": "effective_edge_below_min",
                            "side": side,
                            "effective_edge_bps": float(eff2),
                            "ask": float(ask2),
                            "ref_spot_live": float(spot_live) if isinstance(spot_live, (int, float)) else None,
                            "ref_spot_live_err": spot_live_err[:120] if spot_live_err else "",
                        }
                    )
                    continue

                # If the market moved favorably (lower ask), use the better price.
                # If it moved unfavorably, we'd have skipped above.
                if float(ask2) < float(price):
                    price = float(ask2)
                    notional = price * float(count)
                    order = KalshiOrder(
                        ticker=s.ticker,
                        side=side,
                        action="buy",
                        count=count,
                        price_dollars=f"{price:.4f}",
                        client_order_id=client_order_id,
                    )

                try:
                    resp = kc.create_order(order)
                except KalshiNoFillError as e:
                    # FOK/IOC style no-fill is not a system error; it just means liquidity moved.
                    skipped.append({"ticker": s.ticker, "reason": "no_fill", "error": str(e), "order": asdict(order)})
                    continue
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
                        "ref_spot_live": float(spot_live) if isinstance(spot_live, (int, float)) else None,
                        "ref_spot_live_err": spot_live_err[:120] if spot_live_err else "",
                        "sigma_annual": s.sigma_annual,
                        "strike": s.strike,
                        "strike_high": s.strike_high,
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

                # Optional paired hedge (second leg) to improve worst-case payout when a cheap
                # monotonic ladder exists at the same expiry.
                #
                # This is best-effort and never increases risk if it doesn't fill: we only
                # attempt it after the primary order succeeds, and it's capped to 1 contract.
                try:
                    if str(os.environ.get("KALSHI_ARB_PAIRED_HEDGE", "0")).strip().lower() in ("1", "true", "yes", "y", "on"):
                        if order_count < cfg.max_orders_per_run:
                            min_profit_bps = float(os.environ.get("KALSHI_ARB_PAIRED_MIN_PROFIT_BPS", "50") or 50.0)

                            def _pick_pair() -> Optional[tuple[str, str, float]]:
                                # Return (ticker, side, ask_price) for hedge, or None.
                                st = str(s.strike_type or "")
                                exp = str(s.expected_expiration_time or "")
                                if st not in ("greater", "less") or not exp:
                                    return None

                                # Only hedge monotonic markets where the payoff dominance holds.
                                primary_side = str(side)
                                # Find candidates in the fetched market list.
                                candidates: List[KalshiMarket] = []
                                for m0 in markets:
                                    if not isinstance(m0, KalshiMarket):
                                        continue
                                    if str(m0.expected_expiration_time or "") != exp:
                                        continue
                                    if str(m0.strike_type or "") != st:
                                        continue
                                    candidates.append(m0)

                                if not candidates:
                                    return None

                                # For "greater": YES at lower strike + NO at higher strike guarantees >= $1 payout.
                                # For "less":    YES at higher cap   + NO at lower cap   guarantees >= $1 payout.
                                primary_strike = float(s.strike)
                                if st == "greater":
                                    if primary_side == "yes":
                                        # Need NO at a higher strike.
                                        higher = [m for m in candidates if m.floor_strike is not None and float(m.floor_strike) > primary_strike]
                                        higher.sort(key=lambda m: float(m.floor_strike or 0.0))
                                        for m in higher:
                                            if m.no_ask is None:
                                                continue
                                            return (m.ticker, "no", float(m.no_ask))
                                    else:
                                        # primary is NO; need YES at lower strike.
                                        lower = [m for m in candidates if m.floor_strike is not None and float(m.floor_strike) < primary_strike]
                                        lower.sort(key=lambda m: float(m.floor_strike or 0.0), reverse=True)
                                        for m in lower:
                                            if m.yes_ask is None:
                                                continue
                                            return (m.ticker, "yes", float(m.yes_ask))
                                else:  # less
                                    if primary_side == "yes":
                                        # Need NO at a lower cap.
                                        lower = [m for m in candidates if m.cap_strike is not None and float(m.cap_strike) < primary_strike]
                                        lower.sort(key=lambda m: float(m.cap_strike or 0.0), reverse=True)
                                        for m in lower:
                                            if m.no_ask is None:
                                                continue
                                            return (m.ticker, "no", float(m.no_ask))
                                    else:
                                        # primary is NO; need YES at higher cap.
                                        higher = [m for m in candidates if m.cap_strike is not None and float(m.cap_strike) > primary_strike]
                                        higher.sort(key=lambda m: float(m.cap_strike or 0.0))
                                        for m in higher:
                                            if m.yes_ask is None:
                                                continue
                                            return (m.ticker, "yes", float(m.yes_ask))
                                return None

                            pair = _pick_pair()
                            if pair is not None:
                                hedge_ticker, hedge_side, hedge_ask = pair
                                # Compute worst-case profit (ignoring fees): min payout = 1 if both legs exist.
                                combined_cost = float(price) + float(hedge_ask)
                                profit_bps = (1.0 - float(combined_cost)) * 10_000.0
                                if profit_bps >= float(min_profit_bps):
                                    # Recheck the hedge market right before placing (freshness guard).
                                    m3 = None
                                    try:
                                        m3 = kc.get_market(str(hedge_ticker))
                                    except Exception:
                                        m3 = None
                                    if m3 is not None:
                                        ask3 = m3.yes_ask if hedge_side == "yes" else m3.no_ask
                                        bid3 = m3.yes_bid if hedge_side == "yes" else m3.no_bid
                                        if ask3 is not None and float(args.min_price) <= float(ask3) <= float(args.max_price):
                                            if bid3 is None or (float(ask3) - float(bid3)) <= float(args.max_spread):
                                                # Ensure run/market caps allow the extra notional.
                                                hedge_notional = float(ask3) * 1.0
                                                if (total_notional + hedge_notional) <= float(cfg.max_notional_per_run_usd):
                                                    # New order id.
                                                    client_order_id2 = f"orion-refarb-{int(time.time()*1000)}-{order_count}-hedge-{uuid.uuid4().hex[:6]}"
                                                    order2 = KalshiOrder(
                                                        ticker=str(hedge_ticker),
                                                        side=str(hedge_side),
                                                        action="buy",
                                                        count=1,
                                                        price_dollars=f"{float(ask3):.4f}",
                                                        client_order_id=client_order_id2,
                                                    )
                                                    order_count += 1
                                                    try:
                                                        resp2 = kc.create_order(order2)
                                                        placed.append(
                                                            {
                                                                "mode": "live",
                                                                "paired_hedge": True,
                                                                "paired_profit_bps_worst_case": float(profit_bps),
                                                                "order": asdict(order2),
                                                                "notional_usd": hedge_notional,
                                                                "resp": resp2,
                                                            }
                                                        )
                                                        total_notional += hedge_notional
                                                    except KalshiNoFillError:
                                                        skipped.append({"ticker": str(hedge_ticker), "reason": "paired_no_fill", "side": hedge_side})
                                                    except Exception as e:
                                                        skipped.append({"ticker": str(hedge_ticker), "reason": "paired_order_failed", "error": str(e), "side": hedge_side})
                except Exception:
                    pass

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

    # Diagnostics: if no trades placed, explain why.
    diagnostics: Dict[str, Any] = _compute_trade_diagnostics(all_signals, args, markets_fetched=len(markets), candidates_recommended=len(signals))
    # Also include skip reasons from the decision loop (risk gates, persistence, stacking caps).
    try:
        sc: Dict[str, int] = {}
        for it in skipped:
            if not isinstance(it, dict):
                continue
            r = it.get("reason")
            if isinstance(r, str) and r:
                sc[r] = sc.get(r, 0) + 1
        if sc:
            top = sorted(sc.items(), key=lambda kv: kv[1], reverse=True)[:10]
            diagnostics["skipped_reasons"] = sc
            diagnostics["skipped_top"] = [{"reason": k, "count": int(v)} for k, v in top]
    except Exception:
        pass

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
            "min_notional_usd": args.min_notional_usd,
            "min_notional_bypass_edge_bps": args.min_notional_bypass_edge_bps,
            "allow_write": bool(args.allow_write),
            "risk": asdict(cfg),
        },
        "live_spot_enabled": str(os.environ.get("KALSHI_ARB_LIVE_SPOT", "")).strip().lower() in ("1", "true", "yes", "y", "on"),
        "ref_spot": float(spot) if isinstance(spot, (int, float)) else None,
        "momentum_15m_pct": float(m15) if isinstance(m15, (int, float)) else None,
        "momentum_60m_pct": float(m60) if isinstance(m60, (int, float)) else None,
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
        # Fee-aware gate: low-notional orders are fee-dominated unless edge is huge.
        edge = s.edge_bps_buy_yes if side == "yes" else s.edge_bps_buy_no
        min_notional = float(getattr(args, "min_notional_usd", 0.0) or 0.0)
        bypass = float(getattr(args, "min_notional_bypass_edge_bps", 0.0) or 0.0)
        if min_notional > 0.0 and edge is not None:
            eff = float(edge) - float(args.uncertainty_bps)
            if float(ask) < float(min_notional) and eff < float(bypass):
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
                # Fee-aware: low-notional orders (per 1 contract) require huge edge.
                eff = float(edge) - float(args.uncertainty_bps)
                min_notional = float(getattr(args, "min_notional_usd", 0.0) or 0.0)
                bypass = float(getattr(args, "min_notional_bypass_edge_bps", 0.0) or 0.0)
                if float(min_notional) > 0.0:
                    if float(ask) < float(min_notional) and eff < float(bypass):
                        reasons.append(f"{side}_notional_below_min")
                if _passes_non_edge_filters(s, side):
                    totals["pass_non_edge_filters"] += 1
                # Edge thresholds last (least "structural").
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
    scan.add_argument(
        "--min-notional-usd",
        type=float,
        default=0.20,
        help="Fee-aware gate: skip very low-notional 1x orders unless edge is huge. Set 0 to disable.",
    )
    scan.add_argument(
        "--min-notional-bypass-edge-bps",
        type=float,
        default=4000.0,
        help="If effective edge >= this, allow a low-notional order to pass the fee-aware gate.",
    )
    scan.add_argument("--bayes-prior-k", type=float, default=20.0, help="Bayesian prior concentration for p_yes (higher = trust model more).")
    scan.add_argument("--bayes-obs-k-max", type=float, default=30.0, help="Max observation strength (pseudo-count) from market mid/liquidity.")
    scan.add_argument("--vol-anomaly", action="store_true", help="Enable short-vs-baseline vol regime ratio for diagnostics/sizing.")
    scan.add_argument("--vol-anomaly-window-h", type=int, default=24, help="Window for short realized vol used by --vol-anomaly.")
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
    trade.add_argument("--min-notional-usd", type=float, default=0.20)
    trade.add_argument("--min-notional-bypass-edge-bps", type=float, default=4000.0)
    trade.add_argument("--persistence-cycles", type=int, default=1, help="Require edge to persist across N cycles before trading.")
    trade.add_argument("--persistence-window-min", type=float, default=30.0)
    trade.add_argument("--sizing-mode", default="fixed", choices=["fixed", "edge_tiers", "kelly"], help="Position sizing mode (default fixed=1 probe).")
    trade.add_argument("--min-settled-for-scaling", type=int, default=10, help="Require at least N settled orders before scaling >1 contract.")
    trade.add_argument("--edge-tier2-bps", type=float, default=200.0)
    trade.add_argument("--edge-tier3-bps", type=float, default=300.0)
    trade.add_argument("--edge-tier4-bps", type=float, default=450.0)
    trade.add_argument("--kelly-fraction", type=float, default=0.10, help="Fractional Kelly multiplier (e.g. 0.10 = 0.10 of full Kelly).")
    trade.add_argument("--kelly-cap-fraction", type=float, default=0.10, help="Hard cap on stake fraction of bankroll for Kelly sizing.")
    trade.add_argument("--bayes-prior-k", type=float, default=20.0, help="Bayesian prior concentration for p_yes (higher = trust model more).")
    trade.add_argument("--bayes-obs-k-max", type=float, default=30.0, help="Max observation strength (pseudo-count) from market mid/liquidity.")
    trade.add_argument("--vol-anomaly", action="store_true", help="Enable short-vs-baseline vol regime ratio for diagnostics/sizing.")
    trade.add_argument("--vol-anomaly-window-h", type=int, default=24, help="Window for short realized vol used by --vol-anomaly.")
    trade.add_argument("--allow-write", action="store_true", help="Enable live Kalshi order placement (requires env creds).")
    trade.add_argument("--max-orders-per-run", type=int, default=2)
    trade.add_argument("--max-contracts-per-order", type=int, default=10)
    trade.add_argument("--max-notional-per-run-usd", type=float, default=25.0)
    trade.add_argument("--max-notional-per-market-usd", type=float, default=25.0)
    trade.add_argument(
        "--max-open-contracts-per-ticker",
        type=int,
        default=2,
        help="Cap stacking into the same market ticker (abs open contracts). Set 0 to disable.",
    )
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
