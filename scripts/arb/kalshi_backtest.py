from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .kalshi_ledger import load_ledger


def _safe_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _iter_orders(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    orders = ledger.get("orders")
    if not isinstance(orders, dict):
        return out
    for oid, v in orders.items():
        if not isinstance(oid, str) or not isinstance(v, dict):
            continue
        row = dict(v)
        row["order_id"] = oid
        out.append(row)
    out.sort(key=lambda r: int(r.get("ts_unix") or 0))
    return out


def _resolved_pnl(order: Dict[str, Any]) -> Optional[float]:
    st = order.get("settlement") if isinstance(order.get("settlement"), dict) else {}
    parsed = st.get("parsed") if isinstance(st.get("parsed"), dict) else {}
    cd = _safe_float(parsed.get("cash_delta_usd"))
    if cd is not None:
        return float(cd)

    fills = order.get("fills") if isinstance(order.get("fills"), dict) else {}
    fc = _safe_int(fills.get("count"))
    avg = _safe_float(fills.get("avg_price_dollars"))
    if fc <= 0 or avg is None:
        return None
    out_yes = parsed.get("outcome_yes")
    side = str(order.get("side") or "").lower()
    if not isinstance(out_yes, bool) or side not in ("yes", "no"):
        return None
    won = bool(out_yes) if side == "yes" else (not bool(out_yes))
    payout = float(fc) if won else 0.0
    cost = float(avg) * float(fc)
    return float(payout - cost)


def settled_rows(
    repo_root: str,
    *,
    window_hours: float,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> List[Dict[str, Any]]:
    now = int(time.time())
    start = now - int(max(60.0, float(window_hours) * 3600.0))
    ledger = load_ledger(repo_root)
    out: List[Dict[str, Any]] = []
    for o in _iter_orders(ledger):
        st = o.get("settlement") if isinstance(o.get("settlement"), dict) else None
        if not isinstance(st, dict):
            continue
        ts = int(o.get("ts_unix") or 0)
        if ts < start:
            continue
        pnl_raw = _resolved_pnl(o)
        if pnl_raw is None:
            continue
        fills = o.get("fills") if isinstance(o.get("fills"), dict) else {}
        fc = _safe_int(fills.get("count"))
        avg = _safe_float(fills.get("avg_price_dollars"))
        notional = float(fc) * float(avg) if (fc > 0 and isinstance(avg, (int, float))) else 0.0
        fee_cost = float(notional) * (float(fee_bps) / 10_000.0)
        slip_cost = float(notional) * (float(slippage_bps) / 10_000.0)
        pnl_adj = float(pnl_raw) - float(fee_cost) - float(slip_cost)
        out.append(
            {
                "ts_unix": ts,
                "order_id": o.get("order_id"),
                "ticker": o.get("ticker"),
                "series": (str(o.get("ticker") or "").split("-", 1)[0] if isinstance(o.get("ticker"), str) and "-" in str(o.get("ticker")) else None),
                "side": o.get("side"),
                "fill_count": fc,
                "avg_fill_price": avg,
                "notional_usd": float(notional),
                "pnl_raw_usd": float(pnl_raw),
                "fee_cost_usd": float(fee_cost),
                "slippage_cost_usd": float(slip_cost),
                "pnl_adj_usd": float(pnl_adj),
                "effective_edge_bps": _safe_float(o.get("effective_edge_bps") if o.get("effective_edge_bps") is not None else o.get("edge_bps")),
                "edge_threshold_bps": _safe_float(o.get("edge_threshold_bps") or (o.get("recommended") or {}).get("edge_threshold_bps")),
                "regime_bucket": (
                    str(o.get("regime_bucket"))
                    if isinstance(o.get("regime_bucket"), str)
                    else (str((o.get("filters") or {}).get("regime_bucket")) if isinstance((o.get("filters") or {}).get("regime_bucket"), str) else None)
                ),
                "t_years": _safe_float(o.get("t_years")),
            }
        )
    return out


def _max_drawdown_pct(rows: List[Dict[str, Any]]) -> Optional[float]:
    if not rows:
        return None
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rows:
        eq += float(r.get("pnl_adj_usd") or 0.0)
        if eq > peak:
            peak = eq
        if peak > 0.0:
            max_dd = max(max_dd, ((peak - eq) / peak) * 100.0)
    return float(max_dd)


def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "count": 0,
            "win_rate": None,
            "avg_pnl_raw_usd": None,
            "avg_pnl_adj_usd": None,
            "sum_pnl_raw_usd": 0.0,
            "sum_pnl_adj_usd": 0.0,
            "max_drawdown_pct": None,
        }
    wins = 0
    raw_sum = 0.0
    adj_sum = 0.0
    for r in rows:
        pr = float(r.get("pnl_raw_usd") or 0.0)
        pa = float(r.get("pnl_adj_usd") or 0.0)
        raw_sum += pr
        adj_sum += pa
        if pa > 0.0:
            wins += 1
    return {
        "count": int(n),
        "win_rate": float(wins) / float(n),
        "avg_pnl_raw_usd": float(raw_sum) / float(n),
        "avg_pnl_adj_usd": float(adj_sum) / float(n),
        "sum_pnl_raw_usd": float(raw_sum),
        "sum_pnl_adj_usd": float(adj_sum),
        "max_drawdown_pct": _max_drawdown_pct(rows),
    }


def summarize_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        v = r.get(key)
        k = str(v) if v not in (None, "", "None") else "unknown"
        arr = groups.get(k)
        if arr is None:
            arr = []
            groups[k] = arr
        arr.append(r)
    out: Dict[str, Any] = {}
    for k, arr in groups.items():
        out[k] = summarize_rows(arr)
    return out


def summarize_by_tte_bucket(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _bucket(t_years: Any) -> str:
        ty = _safe_float(t_years)
        if ty is None:
            return "unknown"
        mins = float(ty) * 365.0 * 24.0 * 60.0
        if mins < 60.0:
            return "<60m"
        if mins < 6 * 60.0:
            return "1h-6h"
        if mins < 24 * 60.0:
            return "6h-24h"
        return ">=24h"

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        b = _bucket(r.get("t_years"))
        arr = groups.get(b)
        if arr is None:
            arr = []
            groups[b] = arr
        arr.append(r)
    out: Dict[str, Any] = {}
    for k, arr in groups.items():
        out[k] = summarize_rows(arr)
    return out


def walk_forward(rows: List[Dict[str, Any]], *, folds: int = 4) -> List[Dict[str, Any]]:
    n = len(rows)
    k = max(2, int(folds))
    if n < k:
        return []
    chunk = max(1, n // k)
    out: List[Dict[str, Any]] = []
    for i in range(1, k):
        train = rows[: i * chunk]
        test = rows[i * chunk : (i + 1) * chunk] if i < (k - 1) else rows[i * chunk :]
        if not train or not test:
            continue
        out.append(
            {
                "fold": int(i),
                "train": summarize_rows(train),
                "test": summarize_rows(test),
            }
        )
    return out
