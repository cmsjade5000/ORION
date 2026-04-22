#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from scripts.arb.kalshi import KalshiClient, KalshiNoFillError, KalshiOrder
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi import KalshiClient, KalshiNoFillError, KalshiOrder


def _load_dotenv(path: str) -> None:
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                    value = value[1:-1]
                if key and (key not in os.environ or os.environ.get(key, "") == ""):
                    os.environ[key] = value
    except FileNotFoundError:
        return


def _position_rows(kc: KalshiClient) -> List[Dict[str, Any]]:
    pos = kc.get_positions(limit=200)
    items = pos.get("market_positions") if isinstance(pos, dict) else None
    return items if isinstance(items, list) else []


def _owned_side_and_count(row: Dict[str, Any]) -> tuple[Optional[str], int]:
    try:
        qty = float(row.get("position_fp") or 0.0)
    except Exception:
        qty = 0.0
    if qty > 0:
        return "yes", int(round(qty))
    if qty < 0:
        return "no", int(round(abs(qty)))
    return None, 0


def _quote_for_side(market: Any, side: str) -> Optional[float]:
    if side == "yes":
        return getattr(market, "yes_bid", None)
    if side == "no":
        return getattr(market, "no_bid", None)
    return None


def _order_status(resp: Dict[str, Any]) -> str:
    order = resp.get("order") if isinstance(resp, dict) else None
    if isinstance(order, dict):
        return str(order.get("status") or "")
    return ""


def _filled_count(resp: Dict[str, Any], requested: int) -> int:
    order = resp.get("order") if isinstance(resp, dict) else None
    if not isinstance(order, dict):
        return 0
    for key in ("fill_count", "fill_count_fp", "filled_count", "filled_count_fp"):
        raw = order.get(key)
        if raw is None:
            continue
        try:
            return int(round(float(raw)))
        except Exception:
            continue
    remaining = order.get("remaining_count_fp")
    if remaining is not None:
        try:
            return max(0, int(requested) - int(round(float(remaining))))
        except Exception:
            return 0
    return 0


def liquidate_positions(*, max_passes: int = 3, sleep_s: float = 1.0) -> Dict[str, Any]:
    _load_dotenv("~/.openclaw/.env")
    kc = KalshiClient()
    started_at = int(time.time())

    passes: List[Dict[str, Any]] = []
    for idx in range(max(1, int(max_passes))):
        rows = _position_rows(kc)
        actionable = []
        for row in rows:
            side, count = _owned_side_and_count(row)
            if not side or count <= 0:
                continue
            actionable.append((row, side, count))
        if not actionable:
            break

        pass_results: List[Dict[str, Any]] = []
        for row, side, count in actionable:
            ticker = str(row.get("ticker") or "")
            market = kc.get_market(ticker)
            if market is None:
                pass_results.append({"ticker": ticker, "side": side, "count": count, "status": "skipped", "reason": "market_not_found"})
                continue

            bid = _quote_for_side(market, side)
            if bid is None or float(bid) <= 0.0:
                pass_results.append(
                    {
                        "ticker": ticker,
                        "side": side,
                        "count": count,
                        "status": "skipped",
                        "reason": "no_bid",
                    }
                )
                continue

            order = KalshiOrder(
                ticker=ticker,
                side=side,
                action="sell",
                count=count,
                price_dollars=f"{float(bid):.4f}",
                client_order_id=f"orion-liquidate-{uuid.uuid4()}",
                time_in_force="immediate_or_cancel",
                reduce_only=True,
            )
            try:
                resp = kc.create_order(order)
                pass_results.append(
                    {
                        "ticker": ticker,
                        "side": side,
                        "count": count,
                        "bid": float(bid),
                        "status": _order_status(resp) or "submitted",
                        "filled_count": _filled_count(resp, count),
                        "response": resp,
                    }
                )
            except KalshiNoFillError as exc:
                pass_results.append(
                    {
                        "ticker": ticker,
                        "side": side,
                        "count": count,
                        "bid": float(bid),
                        "status": "no_fill",
                        "error": str(exc),
                    }
                )
            except Exception as exc:
                pass_results.append(
                    {
                        "ticker": ticker,
                        "side": side,
                        "count": count,
                        "bid": float(bid),
                        "status": "error",
                        "error": str(exc),
                    }
                )

        time.sleep(float(sleep_s))
        balance = kc.get_balance()
        remaining_rows = _position_rows(kc)
        remaining = []
        for row in remaining_rows:
            side, count = _owned_side_and_count(row)
            if not side or count <= 0:
                continue
            remaining.append({"ticker": row.get("ticker"), "side": side, "count": count})

        passes.append(
            {
                "pass": idx + 1,
                "attempted": pass_results,
                "post_balance": balance,
                "remaining_positions": remaining,
            }
        )
        if not remaining:
            break

    final_balance = kc.get_balance()
    final_positions = _position_rows(kc)
    remaining_final = []
    for row in final_positions:
        side, count = _owned_side_and_count(row)
        if not side or count <= 0:
            continue
        remaining_final.append({"ticker": row.get("ticker"), "side": side, "count": count})

    return {
        "mode": "kalshi_liquidate_positions",
        "timestamp_unix": started_at,
        "passes": passes,
        "final_balance": final_balance,
        "remaining_positions": remaining_final,
    }


def main() -> int:
    out = liquidate_positions()
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
