#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.arb.kalshi import KalshiClient  # type: ignore
    from scripts.arb.kalshi_analytics import (  # type: ignore
        dedupe_settlements,
        extract_market_position_counts,
        match_fills_for_order,
        settlement_cash_delta_usd,
        summarize_post_snapshot,
    )
    from scripts.arb.kalshi_ledger import closed_loop_report, load_ledger  # type: ignore
except ModuleNotFoundError:
    # Allow running from repo root without package install.
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi import KalshiClient  # type: ignore
    from scripts.arb.kalshi_analytics import (  # type: ignore
        dedupe_settlements,
        extract_market_position_counts,
        match_fills_for_order,
        settlement_cash_delta_usd,
        summarize_post_snapshot,
    )
    from scripts.arb.kalshi_ledger import closed_loop_report, load_ledger  # type: ignore


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _param_recommendations(cl: Dict[str, Any], current_inputs: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Produce conservative, non-auto-applied parameter recommendations from closed-loop stats."""

    def _num(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            return float(x)
        except Exception:
            return None

    def _int(x: Any) -> Optional[int]:
        try:
            if x is None:
                return None
            return int(x)
        except Exception:
            return None

    settled = _int(cl.get("settled_orders")) or 0
    if settled < 5:
        return []

    cur_unc = _num((current_inputs or {}).get("uncertainty_bps"))
    cur_edge = _num((current_inputs or {}).get("min_edge_bps"))
    cur_pers = _int((current_inputs or {}).get("persistence_cycles"))

    wr = _num(cl.get("win_rate"))
    ap = _num(cl.get("avg_implied_win_prob_settled"))
    brier = _num(cl.get("brier_score_settled"))
    pnl = _num(cl.get("realized_pnl_usd_approx"))

    recs: List[Dict[str, Any]] = []

    # If we underperform implied probability or calibration is bad, increase conservatism.
    if wr is not None and ap is not None and wr + 0.05 < ap:
        target = 75.0 if cur_unc is None else min(200.0, float(cur_unc) + 25.0)
        recs.append(
            {
                "env": "KALSHI_ARB_UNCERTAINTY_BPS",
                "value": str(int(round(target))),
                "why": "Win-rate is materially below implied probability; add buffer to reduce false positives.",
            }
        )

    if brier is not None and brier > 0.25:
        target = 100.0 if cur_unc is None else min(250.0, float(cur_unc) + 25.0)
        recs.append(
            {
                "env": "KALSHI_ARB_UNCERTAINTY_BPS",
                "value": str(int(round(target))),
                "why": "Poor calibration (high Brier); add uncertainty buffer and keep sigma=auto.",
            }
        )

    if pnl is not None and pnl < 0.0:
        # Trade less frequently by requiring persistence.
        target = 2 if cur_pers is None else min(4, int(cur_pers) + 1)
        recs.append(
            {
                "env": "KALSHI_ARB_PERSISTENCE_CYCLES",
                "value": str(int(target)),
                "why": "Negative realized P/L; require edge persistence across more cycles before entering.",
            }
        )

    if cur_edge is not None and pnl is not None and pnl < 0.0:
        target = min(400.0, float(cur_edge) + 20.0)
        recs.append(
            {
                "env": "KALSHI_ARB_MIN_EDGE_BPS",
                "value": str(int(round(target))),
                "why": "Negative realized P/L; tighten min-edge to trade less and only take clearer mispricings.",
            }
        )

    # Deduplicate by env; keep first (most relevant).
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in recs:
        e = r.get("env")
        if not isinstance(e, str) or not e:
            continue
        if e in seen:
            continue
        seen.add(e)
        out.append(r)
    return out


def _read_openclaw_telegram_chat_id() -> Optional[int]:
    p = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return None

    chan = ((obj.get("channels") or {}).get("telegram") or {})
    allow = chan.get("allowFrom") or chan.get("dm", {}).get("allowFrom") or []
    try:
        if isinstance(allow, list) and allow:
            return int(allow[0])
    except Exception:
        return None
    return None


def _telegram_chat_id() -> Optional[int]:
    raw = os.environ.get("ORION_TELEGRAM_CHAT_ID") or ""
    if raw.strip():
        try:
            return int(raw.strip())
        except Exception:
            return None
    return _read_openclaw_telegram_chat_id()


def _send_telegram(chat_id: int, text: str, *, cwd: str) -> bool:
    # Use the repo helper to avoid token handling here.
    cmd = f"scripts/telegram_send_message.sh {chat_id} {json.dumps(text)}"
    rc = os.system(f"cd {json.dumps(cwd)} && bash -lc {json.dumps(cmd)} >/dev/null 2>/dev/null")
    return rc == 0


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return dict(default)


def _list_run_files(runs_dir: str) -> List[str]:
    try:
        names = [n for n in os.listdir(runs_dir) if n.endswith(".json")]
    except Exception:
        return []
    out: List[str] = []
    for n in names:
        p = os.path.join(runs_dir, n)
        if os.path.isfile(p):
            out.append(p)
    out.sort()
    return out


@dataclass(frozen=True)
class DigestStats:
    from_ts: int
    to_ts: int
    cycles: int
    live_orders: int
    live_notional_usd: float
    errors: int
    order_failed: int
    kill_switch_seen: int


def _extract_stats(run_objs: List[Dict[str, Any]]) -> DigestStats:
    if not run_objs:
        now = int(time.time())
        return DigestStats(
            from_ts=now,
            to_ts=now,
            cycles=0,
            live_orders=0,
            live_notional_usd=0.0,
            errors=0,
            order_failed=0,
            kill_switch_seen=0,
        )

    from_ts = int(min(int(o.get("ts_unix") or 0) for o in run_objs))
    to_ts = int(max(int(o.get("ts_unix") or 0) for o in run_objs))
    cycles = len(run_objs)

    live_orders = 0
    live_notional = 0.0
    errors = 0
    order_failed = 0
    kill_seen = 0

    for o in run_objs:
        bal_rc = int(o.get("balance_rc") or 0)
        trade_rc = int(o.get("trade_rc") or 0)
        trade = o.get("trade") if isinstance(o.get("trade"), dict) else {}

        if bal_rc != 0:
            errors += 1
        kill_refused = bool(trade.get("status") == "refused" and trade.get("reason") == "kill_switch")
        if kill_refused:
            kill_seen += 1
        if (trade_rc != 0) and (not kill_refused):
            errors += 1

        placed = trade.get("placed") or []
        if isinstance(placed, list):
            for p in placed:
                if not isinstance(p, dict):
                    continue
                if p.get("mode") == "live":
                    live_orders += 1
                    try:
                        live_notional += float(p.get("notional_usd") or 0.0)
                    except Exception:
                        pass

        skipped = trade.get("skipped") or []
        if isinstance(skipped, list):
            for s in skipped:
                if isinstance(s, dict) and s.get("reason") == "order_failed":
                    order_failed += 1

    return DigestStats(
        from_ts=from_ts,
        to_ts=to_ts,
        cycles=cycles,
        live_orders=live_orders,
        live_notional_usd=live_notional,
        errors=errors,
        order_failed=order_failed,
        kill_switch_seen=kill_seen,
    )


def _format_usd(x: float) -> str:
    return f"${x:.2f}"


def _load_risk_state_summary(state_path: str) -> Dict[str, Any]:
    try:
        obj = json.load(open(state_path, "r", encoding="utf-8"))
    except Exception:
        return {"markets": 0, "deployed_notional_usd": None}
    markets = obj.get("markets") or {}
    if not isinstance(markets, dict):
        return {"markets": 0, "deployed_notional_usd": None}
    total = 0.0
    n = 0
    for _, v in markets.items():
        if not isinstance(v, dict):
            continue
        try:
            total += float(v.get("notional_usd") or 0.0)
            n += 1
        except Exception:
            continue
    return {"markets": n, "deployed_notional_usd": float(total)}


def _sigma_summary(run_objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    sigmas: List[float] = []
    modes: List[str] = []
    for o in run_objs:
        ci = o.get("cycle_inputs")
        if not isinstance(ci, dict):
            continue
        sarg = ci.get("sigma_arg")
        smode = ci.get("sigma")
        try:
            if sarg is not None:
                sigmas.append(float(sarg))
        except Exception:
            pass
        if isinstance(smode, str) and smode:
            modes.append(smode)
    avg = (sum(sigmas) / float(len(sigmas))) if sigmas else None
    mode = None
    if modes:
        # If any run was "auto", call it auto; otherwise last explicit.
        mode = "auto" if any(m == "auto" for m in modes) else modes[-1]
    return {"avg_sigma_arg": avg, "mode": mode, "samples": len(sigmas)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a Telegram digest for Kalshi ref-arb bot runs.")
    ap.add_argument("--window-hours", type=float, default=8.0)
    ap.add_argument("--send", action="store_true", help="Actually send Telegram; otherwise prints digest JSON.")
    args = ap.parse_args()

    root = _repo_root()
    runs_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "runs")
    state_path = os.path.join(root, "tmp", "kalshi_ref_arb", "state.json")
    kill_path = os.path.join(root, "tmp", "kalshi_ref_arb.KILL")

    now = int(time.time())
    window_s = int(max(60, float(args.window_hours) * 3600.0))
    start = now - window_s

    run_files = _list_run_files(runs_dir)
    run_objs: List[Dict[str, Any]] = []
    for p in run_files:
        try:
            obj = json.load(open(p, "r", encoding="utf-8"))
            if isinstance(obj, dict) and int(obj.get("ts_unix") or 0) >= start:
                run_objs.append(obj)
        except Exception:
            continue

    stats = _extract_stats(run_objs)
    sigma_s = _sigma_summary(run_objs)
    # For visibility, we report cash / portfolio_value from the most recent post-trade snapshot if present.
    latest_bal = None
    latest_post = None
    for o in reversed(run_objs):
        post = o.get("post")
        if isinstance(post, dict) and isinstance(post.get("balance"), dict):
            latest_post = post
            latest_bal = post.get("balance")
            break
    if latest_bal is None:
        for o in reversed(run_objs):
            bal = o.get("balance")
            if isinstance(bal, dict) and "balance" in bal:
                latest_bal = bal
                break
    avail_usd = None
    port_usd = None
    try:
        if isinstance(latest_bal, dict):
            avail_usd = float(latest_bal.get("balance") or 0.0) / 100.0
            port_usd = float(latest_bal.get("portfolio_value") or 0.0) / 100.0
    except Exception:
        avail_usd = None
        port_usd = None
    kill_on = os.path.exists(kill_path)
    # Include whether an auto-pause might have triggered (best-effort).
    notify_state = _load_json(os.path.join(root, "tmp", "kalshi_ref_arb", "notify_state.json"), default={})

    msg_lines = []
    msg_lines.append(f"Kalshi arb digest ({int(args.window_hours)}h)")
    msg_lines.append(f"Cycles: {stats.cycles}")
    msg_lines.append(f"Live orders: {stats.live_orders} (notional { _format_usd(stats.live_notional_usd) })")
    if isinstance(sigma_s.get("avg_sigma_arg"), (int, float)):
        mode = sigma_s.get("mode") or ""
        suffix = f" ({mode})" if isinstance(mode, str) and mode else ""
        msg_lines.append(f"Sigma used (avg): {float(sigma_s['avg_sigma_arg']):.4f}{suffix}")
    if stats.errors:
        msg_lines.append(f"Errors: {stats.errors} (order_failed {stats.order_failed})")
    if stats.kill_switch_seen or kill_on:
        msg_lines.append(f"Kill switch: {'ON' if kill_on else 'OFF'} (seen {stats.kill_switch_seen} cycles refused)")
    if avail_usd is not None:
        msg_lines.append(f"Cash (approx): {_format_usd(avail_usd)}")
    if port_usd is not None:
        msg_lines.append(f"Portfolio value (approx): {_format_usd(port_usd)}")
    if isinstance(latest_post, dict):
        try:
            s = summarize_post_snapshot(latest_post)
            msg_lines.append(f"Open market positions: {s.open_market_positions}")
            msg_lines.append(f"Open event positions: {s.open_event_positions}")
            if s.fills_count:
                tail = f" ({', '.join(s.tickers_with_fills)})" if s.tickers_with_fills else ""
                msg_lines.append(f"Recent fills (window): {s.fills_count}{tail}")
            if s.settlements_count:
                tail = f" ({', '.join(s.tickers_with_settlements)})" if s.tickers_with_settlements else ""
                msg_lines.append(f"Recent settlements (window): {s.settlements_count}{tail}")
        except Exception:
            pass

    # If we didn't place trades, explain why (from latest cycle diagnostics).
    try:
        if stats.live_orders == 0:
            latest_trade = None
            latest_run = None
            for o in reversed(run_objs):
                t = o.get("trade")
                if isinstance(t, dict) and t.get("mode") == "trade":
                    latest_trade = t
                    latest_run = o
                    break
            if isinstance(latest_trade, dict):
                # If the cycle is evaluating multiple series, surface which one was selected.
                try:
                    tbs = None
                    if isinstance(latest_run, dict) and isinstance(latest_run.get("trades_by_series"), dict):
                        tbs = latest_run.get("trades_by_series")
                    elif isinstance(latest_trade.get("trades_by_series"), dict):
                        tbs = latest_trade.get("trades_by_series")
                    if isinstance(tbs, dict) and tbs:
                        sel = None
                        # The selected series is the one with allow_write=true in its inputs.
                        for s, it in tbs.items():
                            tr = (it or {}).get("trade") if isinstance(it, dict) else None
                            inp = tr.get("inputs") if isinstance(tr, dict) else None
                            if isinstance(inp, dict) and bool(inp.get("allow_write")):
                                sel = s
                                break
                        if isinstance(sel, str) and sel:
                            msg_lines.append(f"Series selected: {sel}")
                except Exception:
                    pass
                diag = latest_trade.get("diagnostics")
                if isinstance(diag, dict):
                    best_pass = diag.get("best_effective_edge_pass_filters") if isinstance(diag.get("best_effective_edge_pass_filters"), dict) else None
                    best_bounds = diag.get("best_effective_edge_in_bounds") if isinstance(diag.get("best_effective_edge_in_bounds"), dict) else None
                    best_any = (
                        diag.get("best_effective_edge_any_quote")
                        if isinstance(diag.get("best_effective_edge_any_quote"), dict)
                        else (diag.get("best_effective_edge") if isinstance(diag.get("best_effective_edge"), dict) else None)
                    )
                    best = best_pass or best_bounds or best_any
                    if isinstance(best, dict) and best.get("ticker"):
                        prefix = "No trades:"
                        if best_pass is None and best_bounds is None and best_any is not None:
                            prefix = "No trades (no quotes in bounds):"
                        try:
                            msg_lines.append(
                                f"{prefix} best eff edge {float(best.get('effective_edge_bps')):.0f} bps on {best.get('ticker')} {best.get('side')} @ {float(best.get('ask')):.4f}"
                            )
                        except Exception:
                            pass
                    tb = diag.get("top_blockers")
                    if isinstance(tb, list) and tb:
                        parts = []
                        for it in tb[:5]:
                            if not isinstance(it, dict):
                                continue
                            r = it.get("reason")
                            c = it.get("count")
                            if isinstance(r, str) and isinstance(c, int):
                                parts.append(f"{r}={c}")
                        if parts:
                            msg_lines.append(f"Blockers: {', '.join(parts)}")
                    totals = diag.get("totals")
                    if isinstance(totals, dict):
                        try:
                            qp = int(totals.get("quotes_present") or 0)
                            pn = int(totals.get("pass_non_edge_filters") or 0)
                            msg_lines.append(f"Diag: quotes {qp}, pass-non-edge {pn}")
                        except Exception:
                            pass
    except Exception:
        pass

    # Closed-loop learning (persistent): entry quality vs (eventual) realized outcomes.
    cl_report: Optional[Dict[str, Any]] = None
    try:
        cl = closed_loop_report(root, window_hours=float(args.window_hours))
        cl_report = cl if isinstance(cl, dict) else None
        if isinstance(cl.get("avg_effective_edge_bps"), (int, float)):
            msg_lines.append(f"Avg effective edge (window): {float(cl['avg_effective_edge_bps']):.0f} bps")
        if isinstance(cl.get("avg_implied_win_prob"), (int, float)):
            msg_lines.append(f"Avg implied win prob (window): {float(cl['avg_implied_win_prob']):.2f}")
        if isinstance(cl.get("settled_orders"), int) and int(cl["settled_orders"]) > 0:
            wr = cl.get("win_rate")
            if isinstance(wr, (int, float)):
                msg_lines.append(f"Settled win-rate (window): {float(wr):.2f}")
            ap = cl.get("avg_implied_win_prob_settled")
            if isinstance(ap, (int, float)):
                msg_lines.append(f"Avg implied win prob (settled): {float(ap):.2f}")
            bd = cl.get("breakdowns")
            if isinstance(bd, dict):
                by_tte = bd.get("by_tte")
                by_strike = bd.get("by_strike")
                if isinstance(by_tte, dict) and by_tte:
                    best = max(by_tte.items(), key=lambda kv: float((kv[1] or {}).get("pnl") or 0.0))
                    try:
                        msg_lines.append(f"Best TTE bucket: {best[0]} pnl {_format_usd(float(best[1]['pnl']))} (n {int(best[1]['n'])})")
                    except Exception:
                        pass
                if isinstance(by_strike, dict) and by_strike:
                    best = max(by_strike.items(), key=lambda kv: float((kv[1] or {}).get("pnl") or 0.0))
                    try:
                        msg_lines.append(f"Best strike bucket: {best[0]} pnl {_format_usd(float(best[1]['pnl']))} (n {int(best[1]['n'])})")
                    except Exception:
                        pass
            sugg = cl.get("suggestions")
            if isinstance(sugg, list) and sugg:
                # Only include one short suggestion in Telegram digest to avoid spam.
                s0 = sugg[0]
                if isinstance(s0, str) and s0.strip():
                    msg_lines.append(f"Note: {s0.strip()}")
        if isinstance(cl.get("realized_pnl_usd_approx"), (int, float)):
            msg_lines.append(f"Realized P/L (settled, approx): {_format_usd(float(cl['realized_pnl_usd_approx']))}")
        # Light breakdown hints.
        mt = cl.get("market_type_counts")
        if isinstance(mt, dict) and mt:
            parts = []
            for k, v in list(mt.items())[:3]:
                try:
                    parts.append(f"{k}:{int(v)}")
                except Exception:
                    continue
            if parts:
                msg_lines.append(f"Market mix (window): {', '.join(parts)}")
        if isinstance(cl.get("avg_time_to_expiry_min"), (int, float)):
            msg_lines.append(f"Avg time-to-expiry at entry: {float(cl['avg_time_to_expiry_min']):.0f} min")
        if isinstance(cl.get("avg_abs_strike_distance_pct"), (int, float)):
            msg_lines.append(f"Avg strike distance at entry: {float(cl['avg_abs_strike_distance_pct']):.2f}%")
    except Exception:
        pass

    # Ledger health: show whether we are seeing settlements we can't attribute/parse.
    try:
        led = load_ledger(root)
        um = led.get("unmatched_settlements") if isinstance(led, dict) else None
        if isinstance(um, list) and um:
            now = int(time.time())
            start = now - int(max(60.0, float(args.window_hours) * 3600.0))
            recent = 0
            for it in um:
                if isinstance(it, dict) and int(it.get("ts_unix") or 0) >= start:
                    recent += 1
            if recent:
                msg_lines.append(f"Unmatched settlements (window): {recent} (total {len(um)})")
    except Exception:
        pass

    # Conservative "parameter recs" (do not auto-apply; just persist and optionally surface one hint).
    param_recs: List[Dict[str, Any]] = []
    try:
        # Pull current params from the most recent trade artifact (if present).
        current_inputs = None
        for o in reversed(run_objs):
            t = o.get("trade")
            if isinstance(t, dict) and isinstance(t.get("inputs"), dict):
                current_inputs = t.get("inputs")
                break
        if isinstance(cl_report, dict):
            param_recs = _param_recommendations(cl_report, current_inputs=current_inputs)
            if param_recs:
                # Keep Telegram short: only 1 line.
                r0 = param_recs[0]
                if isinstance(r0, dict) and isinstance(r0.get("env"), str) and isinstance(r0.get("value"), str):
                    msg_lines.append(f"Param rec: set {r0['env']}={r0['value']}")
    except Exception:
        param_recs = []

    # Deployed downside risk (approx): sum of our tracked notional per market (cost basis), from local state.
    rs = _load_risk_state_summary(state_path)
    if rs.get("deployed_notional_usd") is not None:
        msg_lines.append(
            f"Deployed notional (approx downside): {_format_usd(float(rs['deployed_notional_usd']))} across {int(rs.get('markets') or 0)} markets"
        )

    # Realized cash delta from settlements observed in run artifacts (best-effort, deduped).
    all_settlements: List[Dict[str, Any]] = []
    for o in run_objs:
        post = o.get("post")
        if not isinstance(post, dict):
            continue
        st = post.get("settlements")
        if not isinstance(st, dict):
            continue
        lst = st.get("settlements")
        if isinstance(lst, list):
            for it in lst:
                if isinstance(it, dict):
                    all_settlements.append(it)
    if all_settlements:
        all_settlements = dedupe_settlements(all_settlements)
        ss = settlement_cash_delta_usd({"settlements": {"settlements": all_settlements}})
        cd = ss.get("cash_delta_usd")
        if isinstance(cd, (int, float)):
            tail = ""
            if isinstance(ss.get("tickers"), list) and ss["tickers"]:
                tail = f" ({', '.join([str(x) for x in ss['tickers'][:5]])})"
            msg_lines.append(f"Settlements cash delta (approx): {_format_usd(float(cd))}{tail}")

    # Entry-quality summary: edge-at-entry vs fill quality (from run artifacts).
    placed_live: List[Dict[str, Any]] = []
    for o in run_objs:
        trade = o.get("trade")
        if not isinstance(trade, dict):
            continue
        placed = trade.get("placed") or []
        if not isinstance(placed, list):
            continue
        post = o.get("post") if isinstance(o.get("post"), dict) else {}
        for p in placed:
            if not isinstance(p, dict) or p.get("mode") != "live":
                continue
            order = p.get("order") if isinstance(p.get("order"), dict) else {}
            order_id = p.get("order_id") if isinstance(p.get("order_id"), str) else ""
            edge_bps = p.get("edge_bps")
            try:
                edge_bps_f = float(edge_bps) if edge_bps is not None else None
            except Exception:
                edge_bps_f = None
            limit_px = None
            try:
                limit_px = float(order.get("price_dollars")) if isinstance(order.get("price_dollars"), str) else None
            except Exception:
                limit_px = None
            fills = match_fills_for_order(post, order_id) if (order_id and isinstance(post, dict)) else {}
            avg_fill = fills.get("avg_price_dollars")
            try:
                avg_fill_f = float(avg_fill) if isinstance(avg_fill, (int, float)) else None
            except Exception:
                avg_fill_f = None
            slippage_bps = None
            if (limit_px is not None) and (avg_fill_f is not None):
                slippage_bps = (avg_fill_f - limit_px) * 10_000.0
            placed_live.append(
                {
                    "ticker": order.get("ticker"),
                    "side": order.get("side"),
                    "count": order.get("count"),
                    "order_id": order_id,
                    "edge_bps": edge_bps_f,
                    "limit_price": limit_px,
                    "fills_count": int(fills.get("fills_count") or 0),
                    "avg_fill_price": avg_fill_f,
                    "slippage_bps": slippage_bps,
                    "t_years": p.get("t_years"),
                }
            )

    if placed_live:
        n = len(placed_live)
        filled_orders = sum(1 for x in placed_live if int(x.get("fills_count") or 0) > 0)
        filled_ct = sum(int(x.get("fills_count") or 0) for x in placed_live)
        msg_lines.append(f"Trades (window): placed {n}, filled {filled_orders} (contracts {filled_ct})")
        edges = [float(x["edge_bps"]) for x in placed_live if isinstance(x.get("edge_bps"), (int, float))]
        if edges:
            msg_lines.append(f"Avg edge at entry: {sum(edges)/float(len(edges)):.0f} bps")
        slips = [float(x["slippage_bps"]) for x in placed_live if isinstance(x.get("slippage_bps"), (int, float))]
        if slips:
            msg_lines.append(f"Avg fill slippage: {sum(slips)/float(len(slips)):.0f} bps (price-bps)")
        ttes = []
        for x in placed_live:
            try:
                t = float(x.get("t_years"))
                ttes.append(t * 365.0 * 24.0 * 60.0)
            except Exception:
                continue
        if ttes:
            msg_lines.append(f"Avg time-to-expiry: {sum(ttes)/float(len(ttes)):.0f} min")

    # Mark-to-market estimate from latest open positions (read-only public market quotes).
    if isinstance(latest_post, dict):
        try:
            base_url = "https://api.elections.kalshi.com"
            inp = latest_post.get("inputs")
            if isinstance(inp, dict) and isinstance(inp.get("kalshi_base_url"), str) and inp.get("kalshi_base_url"):
                base_url = str(inp.get("kalshi_base_url"))
            kc = KalshiClient(base_url=base_url)
            counts = extract_market_position_counts(latest_post)
            if counts:
                liq_value = 0.0
                for t, c in list(counts.items())[:20]:
                    m = kc.get_market(t)
                    if m is None:
                        continue
                    y = int((c or {}).get("yes") or 0)
                    n = int((c or {}).get("no") or 0)
                    if y > 0 and m.yes_bid is not None:
                        liq_value += float(m.yes_bid) * float(y)
                    if n > 0 and m.no_bid is not None:
                        liq_value += float(m.no_bid) * float(n)
                msg_lines.append(f"MTM liquidation value (est, bids): {_format_usd(liq_value)}")
        except Exception:
            pass

    payload = {
        "mode": "kalshi_digest",
        "timestamp_unix": now,
        "window_hours": float(args.window_hours),
        "stats": {
            "cycles": stats.cycles,
            "live_orders": stats.live_orders,
            "live_notional_usd": stats.live_notional_usd,
            "errors": stats.errors,
            "order_failed": stats.order_failed,
            "kill_switch_seen": stats.kill_switch_seen,
        },
        "cash_usd": avail_usd,
        "portfolio_value_usd": port_usd,
        "kill_switch_on": kill_on,
        "param_recommendations": param_recs,
        "message": "\n".join(msg_lines),
    }

    # Persist payload for audit/learning (gitignored tmp/).
    try:
        out_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "digests")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{now}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
    except Exception:
        pass

    # Persist param recs separately so we can trend them over time.
    try:
        if param_recs:
            out_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "recommendations")
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, f"{now}.json"), "w", encoding="utf-8") as f:
                json.dump({"timestamp_unix": now, "window_hours": float(args.window_hours), "recs": param_recs}, f, indent=2, sort_keys=True)
                f.write("\n")
    except Exception:
        pass

    if not args.send:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    chat_id = _telegram_chat_id()
    if chat_id is None:
        print("ERROR: could not determine Telegram chat id (set ORION_TELEGRAM_CHAT_ID).", file=os.sys.stderr)
        return 2

    ok = _send_telegram(int(chat_id), payload["message"], cwd=root)
    if not ok:
        print("ERROR: telegram send failed", file=os.sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
