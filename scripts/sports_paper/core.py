from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BookTop:
    bid_px: Optional[float]
    bid_qty: Optional[float]
    ask_px: Optional[float]
    ask_qty: Optional[float]


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _s(x: Any) -> str:
    return str(x or "").strip()


def _parse_outcomes(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            dec = json.loads(raw)
            if isinstance(dec, list):
                return [str(x) for x in dec]
        except Exception:
            return []
    return []


def is_binary_sports_market(market: Dict[str, Any]) -> bool:
    if not isinstance(market, dict):
        return False
    if str(market.get("category") or "").strip().lower() != "sports":
        return False
    if not bool(market.get("active")):
        return False
    if bool(market.get("closed")):
        return False
    outcomes = _parse_outcomes(market.get("outcomes"))
    sides = market.get("marketSides")
    if len(outcomes) != 2:
        return False
    if not isinstance(sides, list) or len(sides) != 2:
        return False
    side_ids = []
    for s in sides:
        if not isinstance(s, dict):
            return False
        sid = _s(s.get("id"))
        if not sid:
            return False
        side_ids.append(sid)
    if len(set(side_ids)) != 2:
        return False
    return True


def market_side_ids(market: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(market, dict):
        return (None, None)
    sides = market.get("marketSides")
    if not isinstance(sides, list) or len(sides) != 2:
        return (None, None)
    a = _s((sides[0] or {}).get("id")) if isinstance(sides[0], dict) else ""
    b = _s((sides[1] or {}).get("id")) if isinstance(sides[1], dict) else ""
    if not a or not b:
        return (None, None)
    return (a, b)


def _top_row(rows: Any, *, is_bid: bool) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(rows, list) or not rows:
        return (None, None)

    def row_px_qty(r: Any) -> tuple[Optional[float], Optional[float]]:
        if not isinstance(r, dict):
            return (None, None)
        px = None
        if isinstance(r.get("px"), dict):
            px = _f((r.get("px") or {}).get("value"))
        if px is None:
            px = _f(r.get("price"))
        if px is None:
            px = _f(r.get("value"))
        qty = _f(r.get("qty"))
        if qty is None:
            qty = _f(r.get("quantity"))
        return (px, qty)

    best_px = None
    best_qty = None
    for r in rows:
        px, qty = row_px_qty(r)
        if px is None:
            continue
        if best_px is None:
            best_px = float(px)
            best_qty = qty
            continue
        if is_bid and px > best_px:
            best_px = float(px)
            best_qty = qty
        if (not is_bid) and px < best_px:
            best_px = float(px)
            best_qty = qty
    return (best_px, best_qty)


def book_top_from_us_book(book: Dict[str, Any]) -> BookTop:
    md = (book or {}).get("marketData") if isinstance(book, dict) else None
    if not isinstance(md, dict):
        return BookTop(bid_px=None, bid_qty=None, ask_px=None, ask_qty=None)
    bid_px, bid_qty = _top_row(md.get("bids"), is_bid=True)
    ask_px, ask_qty = _top_row(md.get("offers"), is_bid=False)
    return BookTop(
        bid_px=float(bid_px) if isinstance(bid_px, (int, float)) else None,
        bid_qty=float(bid_qty) if isinstance(bid_qty, (int, float)) else None,
        ask_px=float(ask_px) if isinstance(ask_px, (int, float)) else None,
        ask_qty=float(ask_qty) if isinstance(ask_qty, (int, float)) else None,
    )


def detect_pair_arbs(
    *,
    top_a: BookTop,
    top_b: BookTop,
    yes_sum_max: float = 0.98,
    no_sum_max: float = 0.98,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "yes": {"ok": False, "sum_price": None, "edge_bps": None},
        "no": {"ok": False, "sum_price": None, "edge_bps": None},
    }

    if isinstance(top_a.ask_px, (int, float)) and isinstance(top_b.ask_px, (int, float)):
        yes_sum = float(top_a.ask_px) + float(top_b.ask_px)
        yes_edge_bps = (float(yes_sum_max) - float(yes_sum)) * 10_000.0
        out["yes"] = {
            "ok": bool(yes_sum <= float(yes_sum_max)),
            "sum_price": float(yes_sum),
            "edge_bps": float(yes_edge_bps),
        }
        # In binary complementary books, NO(A) ~= YES(B) and NO(B) ~= YES(A).
        # This gives a conservative NO-pair estimate and avoids over-stating NO edges.
        no_sum_comp = float(yes_sum)
        no_edge_comp = (float(no_sum_max) - float(no_sum_comp)) * 10_000.0
        out["no"] = {
            "ok": bool(no_sum_comp <= float(no_sum_max)),
            "sum_price": float(no_sum_comp),
            "edge_bps": float(no_edge_comp),
            "source": "complement_ask",
        }

    # Fallback NO proxy from top bid when asks are unavailable.
    # no_ask ~= 1 - bid_yes
    if isinstance(top_a.bid_px, (int, float)) and isinstance(top_b.bid_px, (int, float)):
        if isinstance(out.get("no"), dict) and out["no"].get("sum_price") is not None:
            return out
        no_a = 1.0 - float(top_a.bid_px)
        no_b = 1.0 - float(top_b.bid_px)
        no_sum = float(no_a) + float(no_b)
        no_edge_bps = (float(no_sum_max) - float(no_sum)) * 10_000.0
        out["no"] = {
            "ok": bool(no_sum <= float(no_sum_max)),
            "sum_price": float(no_sum),
            "edge_bps": float(no_edge_bps),
            "no_ask_a_proxy": float(no_a),
            "no_ask_b_proxy": float(no_b),
            "source": "bid_proxy",
        }

    return out


def choose_best_arb(arb: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    yes = arb.get("yes") if isinstance(arb, dict) else None
    no = arb.get("no") if isinstance(arb, dict) else None
    cands = []
    if isinstance(yes, dict) and bool(yes.get("ok")):
        cands.append({"side_mode": "yes", **yes})
    if isinstance(no, dict) and bool(no.get("ok")):
        cands.append({"side_mode": "no", **no})
    if not cands:
        return None
    cands.sort(key=lambda x: float(x.get("edge_bps") or -1e18), reverse=True)
    return cands[0]


def simulate_pair_fok_fill(
    *,
    side_mode: str,
    top_a: BookTop,
    top_b: BookTop,
    sum_max: float,
    max_risk_per_side_usd: float,
    remaining_run_notional_usd: float,
    max_shares_per_side: int,
    min_shares: int,
    slippage_bps: float,
    latency_ms: int,
) -> Dict[str, Any]:
    mode = str(side_mode or "").strip().lower()
    if mode not in ("yes", "no"):
        return {"ok": False, "reason": "invalid_side_mode"}

    if mode == "yes":
        pa = top_a.ask_px
        pb = top_b.ask_px
        qa = top_a.ask_qty
        qb = top_b.ask_qty
    else:
        if top_a.bid_px is None or top_b.bid_px is None:
            return {"ok": False, "reason": "no_proxy_missing_bid"}
        pa = 1.0 - float(top_a.bid_px)
        pb = 1.0 - float(top_b.bid_px)
        qa = top_a.bid_qty
        qb = top_b.bid_qty

    if pa is None or pb is None:
        return {"ok": False, "reason": "missing_price"}
    if pa <= 0.0 or pb <= 0.0 or pa >= 1.0 or pb >= 1.0:
        return {"ok": False, "reason": "price_out_of_bounds"}

    # Adverse execution emulator.
    lat_penalty_bps = max(0.0, float(latency_ms) * 0.02)
    total_adverse_bps = max(0.0, float(slippage_bps) + float(lat_penalty_bps))
    pa_eff = float(pa) * (1.0 + (total_adverse_bps / 10_000.0))
    pb_eff = float(pb) * (1.0 + (total_adverse_bps / 10_000.0))
    sum_eff = float(pa_eff) + float(pb_eff)
    if sum_eff > float(sum_max):
        return {
            "ok": False,
            "reason": "slippage_over_threshold",
            "sum_effective": float(sum_eff),
            "sum_max": float(sum_max),
        }

    # FOK semantics: both legs must satisfy liquidity and budget simultaneously.
    qty_liq = min(float(qa) if isinstance(qa, (int, float)) else 0.0, float(qb) if isinstance(qb, (int, float)) else 0.0)
    if qty_liq <= 0.0:
        return {"ok": False, "reason": "insufficient_liquidity"}

    shares_by_side_a = int(max(0.0, float(max_risk_per_side_usd)) / max(1e-9, float(pa_eff)))
    shares_by_side_b = int(max(0.0, float(max_risk_per_side_usd)) / max(1e-9, float(pb_eff)))
    shares_by_run = int(max(0.0, float(remaining_run_notional_usd)) / max(1e-9, float(pa_eff + pb_eff)))
    shares = min(int(max_shares_per_side), int(math.floor(qty_liq)), int(shares_by_side_a), int(shares_by_side_b), int(shares_by_run))
    if shares < int(min_shares):
        return {
            "ok": False,
            "reason": "size_below_min",
            "shares": int(shares),
            "min_shares": int(min_shares),
        }

    notional = float(shares) * float(pa_eff + pb_eff)
    edge_bps = (1.0 - float(sum_eff)) * 10_000.0
    return {
        "ok": True,
        "shares": int(shares),
        "side_mode": str(mode),
        "price_a": float(pa_eff),
        "price_b": float(pb_eff),
        "sum_price": float(sum_eff),
        "edge_bps": float(edge_bps),
        "notional_usd": float(notional),
        "emulator": {
            "slippage_bps": float(slippage_bps),
            "latency_ms": int(latency_ms),
            "latency_penalty_bps": float(lat_penalty_bps),
        },
        "ts_unix": int(time.time()),
    }
