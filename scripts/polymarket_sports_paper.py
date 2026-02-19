#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from scripts.arb.polymarket_us import PolymarketUSClient  # type: ignore
    from scripts.sports_paper.core import (  # type: ignore
        BookTop,
        book_top_from_us_book,
        choose_best_arb,
        detect_pair_arbs,
        is_binary_sports_market,
        market_side_ids,
        simulate_pair_fok_fill,
    )
    from scripts.sports_paper.ledger import (  # type: ignore
        add_position,
        append_run,
        load_ledger,
        open_positions,
        recompute_stats,
        save_ledger,
        settle_position,
    )
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.polymarket_us import PolymarketUSClient  # type: ignore
    from scripts.sports_paper.core import (  # type: ignore
        BookTop,
        book_top_from_us_book,
        choose_best_arb,
        detect_pair_arbs,
        is_binary_sports_market,
        market_side_ids,
        simulate_pair_fok_fill,
    )
    from scripts.sports_paper.ledger import (  # type: ignore
        add_position,
        append_run,
        load_ledger,
        open_positions,
        recompute_stats,
        save_ledger,
        settle_position,
    )


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _load_dotenv(path: str) -> None:
    def _try(p: str) -> bool:
        try:
            with open(os.path.expanduser(p), "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if not k:
                        continue
                    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                        v = v[1:-1]
                    if k not in os.environ or os.environ.get(k, "") == "":
                        os.environ[k] = v
            return True
        except Exception:
            return False

    if _try(path):
        return
    if os.path.expanduser(path) != os.path.expanduser("~/.openclaw/.env"):
        _try("~/.openclaw/.env")


def _s(x: Any) -> str:
    return str(x or "").strip()


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _scan_once(
    c: PolymarketUSClient,
    *,
    limit: int,
    max_pages: int,
    offset: int,
    yes_sum_max: float,
    no_sum_max: float,
    sleep_ms: int,
) -> Dict[str, Any]:
    opportunities: List[Dict[str, Any]] = []
    errors: List[str] = []
    scanned = 0
    used_pages = 0
    cur = int(offset)

    while used_pages < int(max_pages):
        used_pages += 1
        try:
            obj = c.get_markets(
                params={
                    "active": True,
                    "closed": False,
                    "category": "sports",
                    "limit": int(limit),
                    "offset": int(cur),
                }
            )
        except Exception as e:
            errors.append(f"markets(offset={cur}): {e}")
            break

        markets = obj.get("markets") if isinstance(obj, dict) else None
        if not isinstance(markets, list) or not markets:
            break

        for m in markets:
            if not isinstance(m, dict):
                continue
            if not is_binary_sports_market(m):
                continue
            slug = _s(m.get("slug"))
            if not slug:
                continue
            side_a, side_b = market_side_ids(m)
            if not side_a or not side_b:
                continue

            scanned += 1
            try:
                book_a = c.get_market_book_side(slug, market_side_id=side_a)
                if sleep_ms > 0:
                    time.sleep(max(0.0, float(sleep_ms) / 1000.0))
                book_b = c.get_market_book_side(slug, market_side_id=side_b)
                top_a = book_top_from_us_book(book_a)
                top_b = book_top_from_us_book(book_b)
                arb = detect_pair_arbs(top_a=top_a, top_b=top_b, yes_sum_max=float(yes_sum_max), no_sum_max=float(no_sum_max))
                best = choose_best_arb(arb)
                opportunities.append(
                    {
                        "slug": slug,
                        "question": _s(m.get("question")),
                        "market_type": _s(m.get("sportsMarketType") or m.get("marketType")),
                        "side_a_id": side_a,
                        "side_b_id": side_b,
                        "top_a": {
                            "bid_px": top_a.bid_px,
                            "bid_qty": top_a.bid_qty,
                            "ask_px": top_a.ask_px,
                            "ask_qty": top_a.ask_qty,
                        },
                        "top_b": {
                            "bid_px": top_b.bid_px,
                            "bid_qty": top_b.bid_qty,
                            "ask_px": top_b.ask_px,
                            "ask_qty": top_b.ask_qty,
                        },
                        "arb": arb,
                        "best_arb": best,
                    }
                )
            except Exception as e:
                errors.append(f"{slug}: {e}")

        cur += int(limit)

    opportunities.sort(key=lambda x: float(((x.get("best_arb") or {}).get("edge_bps") or -1e18)), reverse=True)
    return {
        "scanned_markets": int(scanned),
        "pages_used": int(used_pages),
        "offset_end": int(cur),
        "opportunities": opportunities,
        "errors": errors[:100],
    }


def _settle_closed_positions(c: PolymarketUSClient, ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    settled: List[Dict[str, Any]] = []
    for pos in open_positions(ledger):
        pid = _s(pos.get("id"))
        slug = _s(pos.get("slug"))
        if not pid or not slug:
            continue
        try:
            mk = c.get_market_by_slug(slug)
        except Exception:
            continue
        closed = bool(mk.get("closed"))
        ep3 = _s(mk.get("ep3Status")).upper()
        if not closed and ep3 not in ("EXPIRED", "RESOLVED", "SETTLED", "FINALIZED"):
            continue
        shares = int(pos.get("shares") or 0)
        sum_price = _f(pos.get("sum_price")) or 0.0
        pnl = float(shares) * (1.0 - float(sum_price))
        ok = settle_position(ledger, pid, settled_ts_unix=int(time.time()), pnl_usd=float(pnl), note="closed_market_settlement_proxy")
        if ok:
            settled.append({"id": pid, "slug": slug, "shares": shares, "pnl_usd": float(pnl)})
    return settled


def cmd_scan(args: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    scan = _scan_once(
        c,
        limit=int(args.limit),
        max_pages=int(args.max_pages),
        offset=int(args.offset),
        yes_sum_max=float(args.yes_sum_max),
        no_sum_max=float(args.no_sum_max),
        sleep_ms=int(args.sleep_ms),
    )
    out = {
        "mode": "sports_scan",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "limit": int(args.limit),
            "max_pages": int(args.max_pages),
            "offset": int(args.offset),
            "yes_sum_max": float(args.yes_sum_max),
            "no_sum_max": float(args.no_sum_max),
            "sleep_ms": int(args.sleep_ms),
        },
        **scan,
    }
    print(_json(out))
    return 0


def cmd_trade(args: argparse.Namespace) -> int:
    if bool(getattr(args, "allow_write", False)):
        print(_json({"mode": "sports_trade", "status": "refused", "reason": "paper_only_module"}))
        return 2

    root = _repo_root()
    c = PolymarketUSClient()
    ledger = load_ledger(root)
    settled = _settle_closed_positions(c, ledger)

    scan = _scan_once(
        c,
        limit=int(args.limit),
        max_pages=int(args.max_pages),
        offset=int(args.offset),
        yes_sum_max=float(args.yes_sum_max),
        no_sum_max=float(args.no_sum_max),
        sleep_ms=int(args.sleep_ms),
    )
    opps = scan.get("opportunities") if isinstance(scan, dict) else []
    if not isinstance(opps, list):
        opps = []

    max_pairs = int(args.max_pairs_per_run)
    max_notional = float(args.max_notional_per_run_usd)
    placed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    total_notional = 0.0
    open_keys = set()
    for p in open_positions(ledger):
        slug = _s(p.get("slug"))
        mode = _s(p.get("side_mode"))
        if slug and mode:
            open_keys.add(f"{slug}:{mode}")

    for it in opps:
        if len(placed) >= max_pairs:
            break
        if not isinstance(it, dict):
            continue
        best = it.get("best_arb")
        if not isinstance(best, dict):
            continue
        edge = _f(best.get("edge_bps"))
        if edge is None or float(edge) < float(args.min_edge_bps):
            skipped.append({"slug": _s(it.get("slug")), "reason": "edge_below_min"})
            continue
        mode = _s(best.get("side_mode")).lower()
        slug = _s(it.get("slug"))
        if not slug or mode not in ("yes", "no"):
            continue
        if f"{slug}:{mode}" in open_keys:
            skipped.append({"slug": slug, "reason": "duplicate_open_position", "side_mode": mode})
            continue

        top_a = it.get("top_a") if isinstance(it.get("top_a"), dict) else {}
        top_b = it.get("top_b") if isinstance(it.get("top_b"), dict) else {}
        arb = it.get("arb") if isinstance(it.get("arb"), dict) else {}
        sum_max = float(args.yes_sum_max if mode == "yes" else args.no_sum_max)
        sim = simulate_pair_fok_fill(
            side_mode=mode,
            top_a=BookTop(
                bid_px=_f(top_a.get("bid_px")),
                bid_qty=_f(top_a.get("bid_qty")),
                ask_px=_f(top_a.get("ask_px")),
                ask_qty=_f(top_a.get("ask_qty")),
            ),
            top_b=BookTop(
                bid_px=_f(top_b.get("bid_px")),
                bid_qty=_f(top_b.get("bid_qty")),
                ask_px=_f(top_b.get("ask_px")),
                ask_qty=_f(top_b.get("ask_qty")),
            ),
            sum_max=float(sum_max),
            max_risk_per_side_usd=float(args.max_risk_per_side_usd),
            remaining_run_notional_usd=max(0.0, float(max_notional) - float(total_notional)),
            max_shares_per_side=int(args.max_shares_per_side),
            min_shares=int(args.min_shares),
            slippage_bps=float(args.slippage_bps),
            latency_ms=int(args.latency_ms),
        )
        if not bool(sim.get("ok")):
            skipped.append({"slug": slug, "reason": _s(sim.get("reason") or "sim_reject"), "side_mode": mode})
            continue

        notional = float(sim.get("notional_usd") or 0.0)
        if notional <= 0.0:
            skipped.append({"slug": slug, "reason": "zero_notional", "side_mode": mode})
            continue
        if (float(total_notional) + float(notional)) > float(max_notional):
            skipped.append({"slug": slug, "reason": "run_notional_cap", "side_mode": mode})
            continue

        pid = f"pmsp-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"
        row = {
            "id": pid,
            "slug": slug,
            "question": _s(it.get("question")),
            "side_mode": mode,
            "shares": int(sim.get("shares") or 0),
            "price_a": _f(sim.get("price_a")),
            "price_b": _f(sim.get("price_b")),
            "sum_price": _f(sim.get("sum_price")),
            "edge_bps": _f(sim.get("edge_bps")),
            "notional_usd": float(notional),
            "side_a_id": _s(it.get("side_a_id")),
            "side_b_id": _s(it.get("side_b_id")),
            "arb_snapshot": arb,
            "execution_emulator": sim.get("emulator"),
            "opened_ts_unix": int(time.time()),
            "status": "open",
            "paper_only": True,
        }
        add_position(ledger, row)
        placed.append(row)
        open_keys.add(f"{slug}:{mode}")
        total_notional += float(notional)

    st = recompute_stats(ledger)
    append_run(
        ledger,
        {
            "ts_unix": int(time.time()),
            "mode": "trade",
            "placed": len(placed),
            "skipped": len(skipped),
            "settled": len(settled),
            "total_notional_usd": float(total_notional),
        },
    )
    save_ledger(root, ledger)

    out = {
        "mode": "sports_trade",
        "timestamp_unix": int(time.time()),
        "status": "ok",
        "paper_only": True,
        "inputs": {
            "limit": int(args.limit),
            "max_pages": int(args.max_pages),
            "offset": int(args.offset),
            "yes_sum_max": float(args.yes_sum_max),
            "no_sum_max": float(args.no_sum_max),
            "min_edge_bps": float(args.min_edge_bps),
            "max_pairs_per_run": int(args.max_pairs_per_run),
            "max_risk_per_side_usd": float(args.max_risk_per_side_usd),
            "max_notional_per_run_usd": float(args.max_notional_per_run_usd),
            "max_shares_per_side": int(args.max_shares_per_side),
            "min_shares": int(args.min_shares),
            "slippage_bps": float(args.slippage_bps),
            "latency_ms": int(args.latency_ms),
            "sleep_ms": int(args.sleep_ms),
        },
        "scan": {
            "scanned_markets": int(scan.get("scanned_markets") or 0),
            "errors": scan.get("errors") if isinstance(scan.get("errors"), list) else [],
            "opportunities_total": len(opps),
        },
        "settled": settled,
        "placed": placed,
        "skipped": skipped,
        "total_notional_usd": float(total_notional),
        "ledger_stats": st,
    }
    print(_json(out))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    root = _repo_root()
    ledger = load_ledger(root)
    st = recompute_stats(ledger)
    out = {
        "mode": "sports_status",
        "timestamp_unix": int(time.time()),
        "paper_only": True,
        "stats": st,
        "open_positions": open_positions(ledger)[:20],
    }
    save_ledger(root, ledger)
    print(_json(out))
    return 0


def main() -> int:
    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))
    ap = argparse.ArgumentParser(description="Polymarket sports paper arb module (separate from crypto, paper-only).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Read-only sports scan for YES/NO pair arbs.")
    scan.add_argument("--limit", type=int, default=50)
    scan.add_argument("--max-pages", type=int, default=4)
    scan.add_argument("--offset", type=int, default=0)
    scan.add_argument("--yes-sum-max", type=float, default=0.98, help="YES pair max combined ask (e.g. 0.98).")
    scan.add_argument("--no-sum-max", type=float, default=0.98, help="NO pair max combined proxy cost (e.g. 0.98).")
    scan.add_argument("--sleep-ms", type=int, default=25, help="Delay between side book requests to reduce API pressure.")
    scan.set_defaults(func=cmd_scan)

    trade = sub.add_parser("trade", help="Paper-only trade simulation with paired FOK semantics.")
    trade.add_argument("--limit", type=int, default=50)
    trade.add_argument("--max-pages", type=int, default=4)
    trade.add_argument("--offset", type=int, default=0)
    trade.add_argument("--yes-sum-max", type=float, default=0.98)
    trade.add_argument("--no-sum-max", type=float, default=0.98)
    trade.add_argument("--min-edge-bps", type=float, default=5.0)
    trade.add_argument("--max-pairs-per-run", type=int, default=2)
    trade.add_argument("--max-risk-per-side-usd", type=float, default=200.0)
    trade.add_argument("--max-notional-per-run-usd", type=float, default=500.0)
    trade.add_argument("--max-shares-per-side", type=int, default=500)
    trade.add_argument("--min-shares", type=int, default=1)
    trade.add_argument("--slippage-bps", type=float, default=8.0)
    trade.add_argument("--latency-ms", type=int, default=40)
    trade.add_argument("--sleep-ms", type=int, default=25)
    trade.add_argument("--allow-write", action="store_true", help="Forbidden here; module is paper-only.")
    trade.set_defaults(func=cmd_trade)

    status = sub.add_parser("status", help="Show paper sports ledger summary.")
    status.set_defaults(func=cmd_status)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
