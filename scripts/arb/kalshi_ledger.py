from __future__ import annotations

import calendar
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .kalshi_analytics import match_fills_for_order, settlement_cash_delta_usd


def _utc_epoch(ts: str) -> Optional[int]:
    if not isinstance(ts, str) or not ts.endswith("Z"):
        return None
    try:
        t = time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        return int(calendar.timegm(t))
    except Exception:
        return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _sha1(x: Any) -> str:
    try:
        raw = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        raw = repr(x)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def ledger_path(repo_root: str) -> str:
    return os.path.join(repo_root, "tmp", "kalshi_ref_arb", "closed_loop_ledger.json")


def load_ledger(repo_root: str) -> Dict[str, Any]:
    p = ledger_path(repo_root)
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            obj.setdefault("version", 1)
            obj.setdefault("orders", {})
            obj.setdefault("unmatched_settlements", [])
            obj.setdefault("settlement_hashes", [])
            return obj
    except Exception:
        pass
    return {"version": 1, "orders": {}, "unmatched_settlements": [], "settlement_hashes": []}


def save_ledger(repo_root: str, ledger: Dict[str, Any]) -> None:
    p = ledger_path(repo_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)
        f.write("\n")


def _order_key(order_id: str) -> str:
    return str(order_id)


def _record_order(ledger: Dict[str, Any], order_id: str, payload: Dict[str, Any]) -> None:
    orders = ledger.setdefault("orders", {})
    if not isinstance(orders, dict):
        orders = {}
        ledger["orders"] = orders
    k = _order_key(order_id)
    cur = orders.get(k)
    if not isinstance(cur, dict):
        cur = {}
    # Merge (new keys win only when absent).
    for kk, vv in payload.items():
        if kk not in cur or cur.get(kk) in (None, "", [], {}):
            cur[kk] = vv
    orders[k] = cur


def update_from_run(repo_root: str, *, ts_unix: int, trade: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
    """Update persistent ledger with fills + settlements seen in a single cycle."""
    ledger = load_ledger(repo_root)
    placed = trade.get("placed") if isinstance(trade, dict) else None
    if isinstance(placed, list):
        for p in placed:
            if not isinstance(p, dict) or p.get("mode") != "live":
                continue
            oid = p.get("order_id")
            if not isinstance(oid, str) or not oid:
                continue
            order = p.get("order") if isinstance(p.get("order"), dict) else {}
            _record_order(
                ledger,
                oid,
                {
                    "ts_unix": int(ts_unix),
                    "ticker": order.get("ticker"),
                    "side": order.get("side"),
                    "action": order.get("action"),
                    "limit_price_dollars": order.get("price_dollars"),
                    "requested_count": order.get("count"),
                    "edge_bps": p.get("edge_bps"),
                    "effective_edge_bps": (p.get("effective_edge_bps") or (p.get("recommended") or {}).get("effective_edge_bps")),
                    "uncertainty_bps": (p.get("uncertainty_bps") or (p.get("recommended") or {}).get("uncertainty_bps")),
                    "p_yes": p.get("p_yes"),
                    "p_no": p.get("p_no"),
                    "spot_ref": p.get("spot_ref"),
                    "sigma_annual": p.get("sigma_annual"),
                    "t_years": p.get("t_years"),
                    "strike": p.get("strike"),
                    "strike_type": p.get("strike_type"),
                    "expected_expiration_time": p.get("expected_expiration_time"),
                    "filters": p.get("filters"),
                    "market": p.get("market"),
                    "status": p.get("status"),
                },
            )
            # Fills match.
            try:
                m = match_fills_for_order(post, oid)
                if int(m.get("fills_count") or 0) > 0:
                    avg = m.get("avg_price_dollars")
                    avg_f = float(avg) if isinstance(avg, (int, float)) else None
                    _record_order(
                        ledger,
                        oid,
                        {
                            "fills": {
                                "count": int(m.get("fills_count") or 0),
                                "avg_price_dollars": avg_f,
                                "ts_seen": int(ts_unix),
                            }
                        },
                    )
            except Exception:
                pass

    # Settlements: best-effort attribute to filled orders by ticker (we only buy; no sells).
    settlements = ((post.get("settlements") or {}) if isinstance(post, dict) else {})
    s_list = settlements.get("settlements") if isinstance(settlements, dict) else None
    if isinstance(s_list, list) and s_list:
        hashes = ledger.setdefault("settlement_hashes", [])
        if not isinstance(hashes, list):
            hashes = []
            ledger["settlement_hashes"] = hashes
        seen = set(str(x) for x in hashes)
        for s in s_list:
            if not isinstance(s, dict):
                continue
            # Kalshi occasionally includes "settlement" rows with no associated position
            # (yes_count=no_count=0 and/or count=0). These are not actionable and should
            # not pollute unmatched-settlement stats.
            try:
                yc = int(s.get("yes_count") or 0)
                nc = int(s.get("no_count") or 0)
                c = int(s.get("count") or 0)
                if (yc + nc) <= 0 and c <= 0:
                    continue
            except Exception:
                pass
            h = _sha1(s)
            if h in seen:
                continue
            seen.add(h)
            hashes.append(h)
            if len(hashes) > 2000:
                del hashes[: len(hashes) - 2000]
            attributed = _attribute_settlement(ledger, s, ts_unix=ts_unix)
            parsed = _parse_settlement_outcome(s)
            if not attributed:
                um = ledger.setdefault("unmatched_settlements", [])
                if not isinstance(um, list):
                    um = []
                    ledger["unmatched_settlements"] = um
                um.append({"ts_unix": int(ts_unix), "settlement": s})
                if len(um) > 500:
                    del um[: len(um) - 500]
                _capture_settlement_sample(repo_root, ts_unix=ts_unix, settlement=s, parsed=parsed, reason="unattributed")
            else:
                # Even if attributed, keep a small sample of "weird" settlements for schema tuning.
                if parsed.get("outcome_yes") is None and parsed.get("cash_delta_usd") is None:
                    _capture_settlement_sample(repo_root, ts_unix=ts_unix, settlement=s, parsed=parsed, reason="parsed_incomplete")

    save_ledger(repo_root, ledger)
    return ledger


def _capture_settlement_sample(
    repo_root: str,
    *,
    ts_unix: int,
    settlement: Dict[str, Any],
    parsed: Dict[str, Any],
    reason: str,
) -> None:
    """Persist a small rotating jsonl sample of settlement schemas for later parser improvements."""
    try:
        day = time.strftime("%Y%m%d", time.gmtime(int(ts_unix)))
        d = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "settlement_samples")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{day}.jsonl")
        rec = {
            "ts_unix": int(ts_unix),
            "reason": str(reason),
            "parsed": parsed,
            "settlement": settlement,
        }
        # Append-only, daily-rotated.
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")
    except Exception:
        return


def _iter_orders(ledger: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    orders = ledger.get("orders")
    if not isinstance(orders, dict):
        return []
    out: List[Tuple[str, Dict[str, Any]]] = []
    for k, v in orders.items():
        if isinstance(k, str) and isinstance(v, dict):
            out.append((k, v))
    out.sort(key=lambda kv: int(kv[1].get("ts_unix") or 0))
    return out


def _parse_settlement_outcome(s: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort parsing. Outcome is for YES (True means YES happened)."""
    def _iter_dict_candidates(root: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Try a few common nestings without exploding the search space.
        out: List[Dict[str, Any]] = [root]
        for k in (
            "settlement",
            "market",
            "position",
            "result",
            "outcome",
            "resolution",
            "details",
            "data",
        ):
            v = root.get(k)
            if isinstance(v, dict):
                out.append(v)
        return out

    cands = _iter_dict_candidates(s)

    ticker = ""
    for d in cands:
        t = d.get("ticker") or d.get("market_ticker") or d.get("marketTicker")
        if isinstance(t, str) and t:
            ticker = t
            break
        m = d.get("market")
        if isinstance(m, dict):
            t2 = m.get("ticker") or m.get("market_ticker") or m.get("marketTicker")
            if isinstance(t2, str) and t2:
                ticker = t2
                break

    side = ""
    for d in cands:
        v = d.get("side") or d.get("position_side") or d.get("contract_side") or d.get("contractSide")
        if isinstance(v, str):
            vv = v.strip().lower()
            if vv in ("yes", "no"):
                side = vv
                break

    count = None
    for d in cands:
        count = _safe_int(d.get("count") or d.get("quantity") or d.get("contracts") or d.get("contract_count") or d.get("num_contracts"))
        if isinstance(count, int) and count > 0:
            break
        # Sometimes flat yes/no positions.
        pos = d.get("position")
        if isinstance(pos, dict) and side in ("yes", "no"):
            cv = _safe_int(pos.get(side))
            if isinstance(cv, int) and cv > 0:
                count = cv
                break

    outcome_yes: Optional[bool] = None
    # Common keys for 0/1 settlement.
    for k in (
        "settlement_price_dollars",
        "settlement_price_cents",
        "settlement_value_cents",
        "settlement_price",
        "settlement_value",
        "result",
        "outcome",
        "final_outcome",
        "resolved",
    ):
        v = None
        for d in cands:
            if k in d:
                v = d.get(k)
                break
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.strip().lower()
            if vv in ("yes", "true", "y", "1", "settled_yes"):
                outcome_yes = True
                break
            if vv in ("no", "false", "n", "0", "settled_no"):
                outcome_yes = False
                break
        fv = _safe_float(v)
        if fv is None:
            continue
        # Support cents-like ints (0/100).
        if isinstance(v, int) and (0 <= int(v) <= 100):
            outcome_yes = bool(int(v) >= 50)
            break
        if fv > 1.0 and fv <= 100.0:
            # Looks like cents or percent, treat 50+ as YES.
            outcome_yes = bool(fv >= 50.0)
            break
        if 0.0 <= fv <= 1.0:
            outcome_yes = bool(fv >= 0.5)
            break

    payout = None
    for d in cands:
        payout = _safe_float(d.get("payout_dollars") or d.get("payout") or d.get("amount_dollars") or d.get("amount"))
        if payout is not None:
            break
    cash_delta = settlement_cash_delta_usd({"settlements": {"settlements": [s]}}).get("cash_delta_usd")
    cash_delta_f = float(cash_delta) if isinstance(cash_delta, (int, float)) else None
    return {
        "ticker": ticker,
        "side": side,
        "count": count,
        "outcome_yes": outcome_yes,
        "payout_dollars": payout,
        "cash_delta_usd": cash_delta_f,
    }


def _attribute_settlement(ledger: Dict[str, Any], s: Dict[str, Any], *, ts_unix: int) -> bool:
    parsed = _parse_settlement_outcome(s)
    t = parsed.get("ticker") or ""
    if not isinstance(t, str) or not t:
        return False

    orders = ledger.get("orders")
    if not isinstance(orders, dict):
        return False

    # Find orders in this ticker with fills and no settlement yet.
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for oid, o in orders.items():
        if not isinstance(oid, str) or not isinstance(o, dict):
            continue
        if str(o.get("ticker") or "") != t:
            continue
        if isinstance(o.get("settlement"), dict):
            continue
        f = o.get("fills") if isinstance(o.get("fills"), dict) else {}
        fc = int(f.get("count") or 0) if isinstance(f, dict) else 0
        if fc <= 0:
            continue
        # If settlement includes a side, only match orders with same side.
        s_side = parsed.get("side")
        if isinstance(s_side, str) and s_side in ("yes", "no"):
            if o.get("side") != s_side:
                continue
        candidates.append((oid, o))
    if not candidates:
        return False

    # If settlement count is available, attribute to that many contracts in FIFO order across orders.
    # Otherwise, attribute to all candidates (best-effort).
    candidates.sort(key=lambda kv: int(kv[1].get("ts_unix") or 0))
    remaining = parsed.get("count")
    remaining_i = int(remaining) if isinstance(remaining, int) and remaining > 0 else None

    any_attributed = False
    for oid, o in candidates:
        if remaining_i is not None and remaining_i <= 0:
            break
        f = o.get("fills") if isinstance(o.get("fills"), dict) else {}
        fc = int(f.get("count") or 0) if isinstance(f, dict) else 0
        take = fc if remaining_i is None else min(fc, remaining_i)
        if take <= 0:
            continue
        payload = {"ts_seen": int(ts_unix), "parsed": parsed, "raw": s, "settled_count": int(take)}
        _record_order(ledger, oid, {"settlement": payload})
        any_attributed = True
        if remaining_i is not None:
            remaining_i -= int(take)

    return any_attributed


def closed_loop_report(repo_root: str, *, window_hours: float = 8.0) -> Dict[str, Any]:
    """Compute closed-loop stats over a time window, using persistent ledger."""
    ledger = load_ledger(repo_root)
    now = int(time.time())
    start = now - int(max(60.0, float(window_hours) * 3600.0))

    orders = _iter_orders(ledger)
    window_orders = [(oid, o) for (oid, o) in orders if int(o.get("ts_unix") or 0) >= start]

    placed = len(window_orders)
    filled = 0
    contracts = 0
    edges: List[float] = []
    probs: List[float] = []
    tte_min: List[float] = []
    strike_dist_abs: List[float] = []
    market_type_counts: Dict[str, int] = {}

    for _, o in window_orders:
        f = o.get("fills") if isinstance(o.get("fills"), dict) else {}
        fc = int(f.get("count") or 0) if isinstance(f, dict) else 0
        if fc > 0:
            filled += 1
            contracts += fc
        eb = _safe_float(o.get("effective_edge_bps") if o.get("effective_edge_bps") is not None else o.get("edge_bps"))
        if eb is not None:
            edges.append(float(eb))
        side = o.get("side")
        p_yes = _safe_float(o.get("p_yes"))
        if p_yes is not None and side in ("yes", "no"):
            probs.append(float(p_yes if side == "yes" else (1.0 - p_yes)))

        stype = o.get("strike_type")
        if isinstance(stype, str) and stype:
            market_type_counts[stype] = int(market_type_counts.get(stype) or 0) + 1

        strike = _safe_float(o.get("strike"))
        spot = _safe_float(o.get("spot_ref"))
        if strike is not None and spot is not None and spot > 0:
            strike_dist_abs.append(abs(float(strike) - float(spot)) / float(spot))

        exp = o.get("expected_expiration_time")
        exp_ts = _utc_epoch(exp) if isinstance(exp, str) else None
        if exp_ts is not None:
            tte_min.append(max(0.0, float(exp_ts - int(o.get("ts_unix") or 0))) / 60.0)

    # Settled outcomes (best-effort) from attributed settlements.
    settled = 0
    wins = 0
    losses = 0
    realized_pnl = 0.0
    realized_any = False
    probs_settled: List[float] = []
    brier: List[float] = []

    # Breakdowns
    by_type: Dict[str, Dict[str, Any]] = {}
    by_tte: Dict[str, Dict[str, Any]] = {}
    by_strike: Dict[str, Dict[str, Any]] = {}

    def _bucket_tte(mins: Optional[float]) -> str:
        if mins is None:
            return "unknown"
        if mins < 60:
            return "<1h"
        if mins < 6 * 60:
            return "1-6h"
        if mins < 24 * 60:
            return "6-24h"
        return ">24h"

    def _bucket_strike(pct: Optional[float]) -> str:
        if pct is None:
            return "unknown"
        if pct < 0.25:
            return "<0.25%"
        if pct < 0.5:
            return "0.25-0.5%"
        if pct < 1.0:
            return "0.5-1%"
        if pct < 2.0:
            return "1-2%"
        return ">2%"

    def _bump(d: Dict[str, Dict[str, Any]], key: str, *, pnl: float, win: Optional[bool]) -> None:
        cur = d.get(key) or {"n": 0, "pnl": 0.0, "wins": 0, "losses": 0}
        cur["n"] = int(cur.get("n") or 0) + 1
        cur["pnl"] = float(cur.get("pnl") or 0.0) + float(pnl)
        if win is True:
            cur["wins"] = int(cur.get("wins") or 0) + 1
        elif win is False:
            cur["losses"] = int(cur.get("losses") or 0) + 1
        d[key] = cur

    for _, o in window_orders:
        st = o.get("settlement") if isinstance(o.get("settlement"), dict) else None
        if not isinstance(st, dict):
            continue
        if int(st.get("ts_seen") or 0) < start:
            continue
        settled += 1
        parsed = st.get("parsed") if isinstance(st.get("parsed"), dict) else {}
        outcome_yes = parsed.get("outcome_yes")
        side = o.get("side")
        p_yes = _safe_float(o.get("p_yes"))
        win: Optional[bool] = None
        if isinstance(outcome_yes, bool) and side in ("yes", "no"):
            win = bool(outcome_yes) if side == "yes" else (not bool(outcome_yes))

        # P/L
        pnl_i = None
        cd = parsed.get("cash_delta_usd")
        if isinstance(cd, (int, float)):
            pnl_i = float(cd)
        else:
            f = o.get("fills") if isinstance(o.get("fills"), dict) else {}
            fc = int(f.get("count") or 0) if isinstance(f, dict) else 0
            avg = _safe_float(f.get("avg_price_dollars")) if isinstance(f, dict) else None
            if fc > 0 and avg is not None and isinstance(outcome_yes, bool) and side in ("yes", "no"):
                payout = float(fc) * (1.0 if (bool(outcome_yes) if side == "yes" else (not bool(outcome_yes))) else 0.0)
                pnl_i = payout - (float(avg) * float(fc))
        if pnl_i is not None:
            realized_any = True
            realized_pnl += float(pnl_i)

        if win is True:
            wins += 1
        elif win is False:
            losses += 1

        if p_yes is not None and side in ("yes", "no") and isinstance(win, bool):
            p = float(p_yes if side == "yes" else (1.0 - p_yes))
            probs_settled.append(p)
            y = 1.0 if win else 0.0
            brier.append((p - y) ** 2)

        stype = o.get("strike_type")
        if isinstance(stype, str) and stype:
            _bump(by_type, stype, pnl=float(pnl_i or 0.0), win=win)

        exp = o.get("expected_expiration_time")
        exp_ts = _utc_epoch(exp) if isinstance(exp, str) else None
        mins = None
        if exp_ts is not None:
            mins = max(0.0, float(exp_ts - int(o.get("ts_unix") or 0))) / 60.0
        _bump(by_tte, _bucket_tte(mins), pnl=float(pnl_i or 0.0), win=win)

        strike = _safe_float(o.get("strike"))
        spot = _safe_float(o.get("spot_ref"))
        pct = None
        if strike is not None and spot is not None and spot > 0:
            pct = abs(float(strike) - float(spot)) / float(spot) * 100.0
        _bump(by_strike, _bucket_strike(pct), pnl=float(pnl_i or 0.0), win=win)

    pnl = float(realized_pnl) if realized_any else None

    suggestions: List[str] = []
    wr = (float(wins) / float(max(1, wins + losses))) if (wins + losses) > 0 else None
    ap_set = (sum(probs_settled) / float(len(probs_settled))) if probs_settled else None
    brier_s = (sum(brier) / float(len(brier))) if brier else None
    if isinstance(wr, float) and isinstance(ap_set, float) and (wins + losses) >= 5:
        # If we're materially underperforming the model, recommend being more conservative.
        if wr + 0.05 < ap_set:
            suggestions.append("Model underperforming: consider increasing uncertainty-bps and/or min-edge-bps.")
    if isinstance(pnl, float) and (wins + losses) >= 5 and pnl < 0:
        suggestions.append("Negative realized P/L: consider trading less (higher persistence-cycles) and/or stricter spread/liquidity filters.")
    if isinstance(brier_s, float) and (wins + losses) >= 5 and brier_s > 0.25:
        suggestions.append("Poor calibration (high brier): consider sigma=auto (realized vol) and a larger uncertainty-bps buffer.")

    def _avg(xs: List[float]) -> Optional[float]:
        return (sum(xs) / float(len(xs))) if xs else None

    report = {
        "window_hours": float(window_hours),
        "from_ts": start,
        "to_ts": now,
        "placed_orders": placed,
        "filled_orders": filled,
        "filled_contracts": contracts,
        "avg_effective_edge_bps": _avg(edges),
        "avg_implied_win_prob": _avg(probs),
        "avg_time_to_expiry_min": _avg(tte_min),
        "avg_abs_strike_distance_pct": (_avg(strike_dist_abs) * 100.0) if strike_dist_abs else None,
        "market_type_counts": market_type_counts,
        "settled_orders": settled,
        "wins": wins,
        "losses": losses,
        "win_rate": (float(wins) / float(max(1, wins + losses))) if (wins + losses) > 0 else None,
        "avg_implied_win_prob_settled": (sum(probs_settled) / float(len(probs_settled))) if probs_settled else None,
        "brier_score_settled": (sum(brier) / float(len(brier))) if brier else None,
        "realized_pnl_usd_approx": pnl,
        "breakdowns": {"by_type": by_type, "by_tte": by_tte, "by_strike": by_strike},
        "suggestions": suggestions,
    }
    return report
