from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


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


def _hash_obj(x: Any) -> str:
    try:
        raw = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        raw = repr(x)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class PortfolioSummary:
    cash_usd: Optional[float]
    portfolio_value_usd: Optional[float]
    open_market_positions: int
    open_event_positions: int
    fills_count: int
    settlements_count: int
    tickers_with_fills: List[str]
    tickers_with_settlements: List[str]


def summarize_post_snapshot(post: Dict[str, Any]) -> PortfolioSummary:
    bal = _as_dict(post.get("balance"))
    cash_usd = None
    pv_usd = None
    if bal:
        b = _safe_float(bal.get("balance"))
        pv = _safe_float(bal.get("portfolio_value"))
        cash_usd = (b / 100.0) if b is not None else None
        pv_usd = (pv / 100.0) if pv is not None else None

    pos = _as_dict(post.get("positions"))
    open_market = len(_as_list(pos.get("market_positions")))
    open_event = len(_as_list(pos.get("event_positions")))

    fills = _as_dict(post.get("fills"))
    fills_list = _as_list(fills.get("fills"))
    fill_tickers: List[str] = []
    for f in fills_list:
        d = _as_dict(f)
        t = d.get("ticker") or d.get("market_ticker")
        if isinstance(t, str) and t and t not in fill_tickers:
            fill_tickers.append(t)
        if len(fill_tickers) >= 5:
            break

    settlements = _as_dict(post.get("settlements"))
    settlements_list = _as_list(settlements.get("settlements"))
    settlement_tickers: List[str] = []
    for s in settlements_list:
        d = _as_dict(s)
        t = d.get("ticker") or d.get("market_ticker")
        if isinstance(t, str) and t and t not in settlement_tickers:
            settlement_tickers.append(t)
        if len(settlement_tickers) >= 5:
            break

    return PortfolioSummary(
        cash_usd=cash_usd,
        portfolio_value_usd=pv_usd,
        open_market_positions=open_market,
        open_event_positions=open_event,
        fills_count=len(fills_list),
        settlements_count=len(settlements_list),
        tickers_with_fills=fill_tickers,
        tickers_with_settlements=settlement_tickers,
    )


def extract_market_position_counts(post: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Best-effort extraction of market position quantities by ticker and side.

    Returns: { "<ticker>": {"yes": int, "no": int} }
    """
    pos = _as_dict(post.get("positions"))
    items = _as_list(pos.get("market_positions"))
    out: Dict[str, Dict[str, int]] = {}
    for it in items:
        d = _as_dict(it)
        t = d.get("ticker") or d.get("market_ticker")
        if not isinstance(t, str) or not t:
            continue

        yes = 0
        no = 0

        # Common patterns we might see.
        if isinstance(d.get("position"), dict):
            p = _as_dict(d.get("position"))
            yes = int(_safe_int(p.get("yes")) or 0)
            no = int(_safe_int(p.get("no")) or 0)
        else:
            # Flat side/count
            side = d.get("side")
            cnt = _safe_int(d.get("count")) or _safe_int(d.get("quantity")) or _safe_int(d.get("position")) or 0
            if side == "yes":
                yes = int(cnt)
            elif side == "no":
                no = int(cnt)
            # Explicit yes/no fields
            yes = max(yes, int(_safe_int(d.get("yes_count")) or _safe_int(d.get("yes_position")) or 0))
            no = max(no, int(_safe_int(d.get("no_count")) or _safe_int(d.get("no_position")) or 0))

        if t not in out:
            out[t] = {"yes": 0, "no": 0}
        out[t]["yes"] += int(yes)
        out[t]["no"] += int(no)
    return out


def match_fills_for_order(post: Dict[str, Any], order_id: str) -> Dict[str, Any]:
    """Aggregate fills in a post snapshot for a given order_id."""
    fills = _as_dict(post.get("fills"))
    lst = _as_list(fills.get("fills"))
    total = 0
    notional = 0.0
    tickers: List[str] = []
    for f in lst:
        d = _as_dict(f)
        oid = d.get("order_id") or d.get("id")
        if not isinstance(oid, str) or oid != order_id:
            continue
        cnt = int(_safe_int(d.get("count")) or _safe_int(d.get("quantity")) or 0)
        px = (
            _safe_float(d.get("price_dollars"))
            or _safe_float(d.get("yes_price_dollars"))
            or _safe_float(d.get("no_price_dollars"))
            or _safe_float(d.get("price"))
        )
        t = d.get("ticker") or d.get("market_ticker")
        if isinstance(t, str) and t and t not in tickers:
            tickers.append(t)
        if cnt > 0:
            total += cnt
            if px is not None:
                notional += float(px) * float(cnt)
    avg = (notional / float(total)) if total > 0 else None
    return {"fills_count": total, "avg_price_dollars": avg, "tickers": tickers}


def dedupe_settlements(settlements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for s in settlements:
        h = _hash_obj(s)
        if h in seen:
            continue
        seen.add(h)
        out.append(s)
    return out


def _extract_cash_delta_usd_from_settlement(s: Dict[str, Any]) -> Optional[float]:
    # We intentionally keep this heuristic and label it "cash delta" in output.
    # Prefer explicit dollar fields; fallback to cent-like ints when obvious.
    candidates = [
        "cash_delta_dollars",
        "profit_dollars",
        "payout_dollars",
        "amount_dollars",
        "net_dollars",
        "cashDeltaDollars",
        "profitDollars",
        "payoutDollars",
        "amountDollars",
        "netDollars",
        "cash_delta_usd",
        "profit_usd",
        "payout_usd",
        "amount_usd",
        "net_usd",
        "cash_delta",
        "profit",
        "payout",
        "amount",
        "net",
        "cashDelta",
        "profitUsd",
        "payoutUsd",
        "amountUsd",
        "netUsd",
        # Cent-denominated common variants.
        "cash_delta_cents",
        "profit_cents",
        "payout_cents",
        "amount_cents",
        "net_cents",
        "cashDeltaCents",
        "profitCents",
        "payoutCents",
        "amountCents",
        "netCents",
    ]
    for k in candidates:
        v = s.get(k)
        if v is None:
            continue
        # Some schemas nest the amount as {"amount": ...}.
        if isinstance(v, dict):
            for kk in ("amount", "value", "dollars", "cents"):
                if kk in v:
                    v = v.get(kk)
                    break
        # Strings like "1.23"
        if isinstance(v, str):
            vv = v.strip().replace("$", "").replace(",", "")
            v = vv
        fx = _safe_float(v)
        if fx is None:
            continue
        if isinstance(v, int):
            # Likely cents if large, or explicitly a *_cents key.
            if k.endswith("_cents") or k.endswith("Cents") or abs(int(v)) >= 100:
                return float(v) / 100.0
            return float(v)
        # If it's a float but looks like cents (e.g. 1234.0), handle conservatively.
        if k.endswith("_cents") or k.endswith("Cents"):
            return float(fx) / 100.0
        if abs(float(fx)) >= 100.0 and abs(float(fx)) <= 1_000_000.0:
            # Many settlement payloads use integer cents but serialized as float.
            if float(fx).is_integer():
                return float(fx) / 100.0
        return float(fx)
    return None


def settlement_cash_delta_usd(post: Dict[str, Any]) -> Dict[str, Any]:
    """Sum settlement cash deltas in a post snapshot (best-effort)."""
    settlements = _as_dict(post.get("settlements"))
    lst = _as_list(settlements.get("settlements"))
    total = 0.0
    found_any = False
    tickers: List[str] = []
    for raw in lst:
        d = _as_dict(raw)
        v = _extract_cash_delta_usd_from_settlement(d)
        if v is None:
            continue
        found_any = True
        total += float(v)
        t = d.get("ticker") or d.get("market_ticker")
        if isinstance(t, str) and t and t not in tickers:
            tickers.append(t)
        if len(tickers) >= 5:
            # Keep it short for digests.
            pass
    return {"cash_delta_usd": (total if found_any else None), "tickers": tickers, "count": len(lst)}
