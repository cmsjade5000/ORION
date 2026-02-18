#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

# When executed as `python3 scripts/arb_bot.py`, sys.path[0] is the scripts/
# directory and the repo root may not be importable as a package. Fix up path.
try:
    from scripts.arb.arb import build_internal_opportunity  # type: ignore
    from scripts.arb.polymarket import PolymarketAPI  # type: ignore
    from scripts.arb.polymarket_us import PolymarketUSClient, best_bid_ask_from_us_book  # type: ignore
except ModuleNotFoundError:
    import os

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.arb import build_internal_opportunity  # type: ignore
    from scripts.arb.polymarket import PolymarketAPI  # type: ignore
    from scripts.arb.polymarket_us import PolymarketUSClient, best_bid_ask_from_us_book  # type: ignore


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def cmd_scan(args: argparse.Namespace) -> int:
    pm = PolymarketAPI(
        gamma_base_url=args.gamma_base_url,
        clob_base_url=args.clob_base_url,
        web_base_url=args.web_base_url,
    )

    geoblock: Optional[Dict[str, Any]] = None
    if not args.skip_geoblock:
        try:
            geoblock = pm.get_geoblock()
        except Exception as e:
            geoblock = {"error": str(e)}

    opportunities: List[Dict[str, Any]] = []
    scanned = 0
    errors: List[str] = []

    for m in pm.iter_gamma_markets(
        active=True,
        closed=False,
        limit=args.gamma_limit,
        max_pages=args.max_pages,
        offset=args.gamma_offset,
    ):
        if scanned >= args.max_markets:
            break
        scanned += 1

        # Only handle binary markets with an enabled order book.
        if not m.enable_order_book:
            continue
        if len(m.outcomes) != 2 or len(m.clob_token_ids) != 2:
            continue

        # Heuristic mapping: Gamma's outcomes/clobTokenIds arrays are aligned.
        out_a, out_b = m.outcomes[0], m.outcomes[1]
        tok_a, tok_b = m.clob_token_ids[0], m.clob_token_ids[1]

        try:
            _, ask_a = pm.get_best_bid_ask(tok_a)
            _, ask_b = pm.get_best_bid_ask(tok_b)
            if ask_a is None or ask_b is None:
                continue
            opp = build_internal_opportunity(
                market_slug=m.slug,
                outcome_a=out_a,
                outcome_b=out_b,
                token_a=tok_a,
                token_b=tok_b,
                ask_a=ask_a,
                ask_b=ask_b,
                fee_bps=args.fee_bps,
                min_edge_bps=args.min_edge_bps,
            )
            if opp is not None:
                opportunities.append(asdict(opp))
        except Exception as e:
            errors.append(f"{m.slug}: {e}")

        if args.sleep_ms > 0:
            time.sleep(max(0.0, args.sleep_ms / 1000.0))

    out = {
        "mode": "scan",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "gamma_base_url": args.gamma_base_url,
            "clob_base_url": args.clob_base_url,
            "web_base_url": args.web_base_url,
            "max_markets": args.max_markets,
            "max_pages": args.max_pages,
            "gamma_limit": args.gamma_limit,
            "gamma_offset": args.gamma_offset,
            "min_edge_bps": args.min_edge_bps,
            "fee_bps": args.fee_bps,
            "sleep_ms": args.sleep_ms,
            "skip_geoblock": args.skip_geoblock,
        },
        "geoblock": geoblock,
        "scanned_markets": scanned,
        "opportunities": sorted(opportunities, key=lambda x: float(x.get("edge_bps", 0.0)), reverse=True),
        "errors": errors[:50],
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def cmd_scan_us(args: argparse.Namespace) -> int:
    pm = PolymarketUSClient()

    opportunities: List[Dict[str, Any]] = []
    scanned = 0
    errors: List[str] = []

    # Basic pagination; API supports offset/limit.
    offset = int(args.offset or 0)
    page = 0
    while scanned < int(args.max_markets) and page < int(args.max_pages):
        page += 1
        try:
            obj = pm.get_markets(
                params={
                    "active": True,
                    "closed": False,
                    "limit": int(args.limit),
                    "offset": int(offset),
                }
            )
        except Exception as e:
            errors.append(f"markets_page(offset={offset}): {e}")
            break

        ms = obj.get("markets") if isinstance(obj, dict) else None
        if not isinstance(ms, list) or not ms:
            break

        for m in ms:
            if scanned >= int(args.max_markets):
                break
            scanned += 1
            if not isinstance(m, dict):
                continue
            slug = m.get("slug")
            outcomes = m.get("outcomes")
            sides = m.get("marketSides")
            if not isinstance(slug, str) or not slug:
                continue
            if not (isinstance(outcomes, list) and len(outcomes) == 2):
                continue
            if not (isinstance(sides, list) and len(sides) == 2):
                continue
            side_a = sides[0].get("id") if isinstance(sides[0], dict) else None
            side_b = sides[1].get("id") if isinstance(sides[1], dict) else None
            if not (isinstance(side_a, str) and side_a and isinstance(side_b, str) and side_b):
                continue

            try:
                book_a = pm.get_market_book_side(slug, market_side_id=side_a)
                book_b = pm.get_market_book_side(slug, market_side_id=side_b)
                _, ask_a = best_bid_ask_from_us_book(book_a)
                _, ask_b = best_bid_ask_from_us_book(book_b)
                if ask_a is None or ask_b is None:
                    continue
                opp = build_internal_opportunity(
                    market_slug=slug,
                    outcome_a=str(outcomes[0]),
                    outcome_b=str(outcomes[1]),
                    token_a=str(side_a),
                    token_b=str(side_b),
                    ask_a=float(ask_a),
                    ask_b=float(ask_b),
                    fee_bps=float(args.fee_bps),
                    min_edge_bps=float(args.min_edge_bps),
                )
                if opp is not None:
                    opportunities.append(asdict(opp))
            except Exception as e:
                errors.append(f"{slug}: {e}")

            if int(args.sleep_ms or 0) > 0:
                time.sleep(max(0.0, float(args.sleep_ms) / 1000.0))

        offset += int(args.limit)

    out = {
        "mode": "scan_us",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "max_markets": int(args.max_markets),
            "max_pages": int(args.max_pages),
            "limit": int(args.limit),
            "offset": int(args.offset),
            "min_edge_bps": float(args.min_edge_bps),
            "fee_bps": float(args.fee_bps),
            "sleep_ms": int(args.sleep_ms),
        },
        "scanned_markets": scanned,
        "opportunities": sorted(opportunities, key=lambda x: float(x.get("edge_bps", 0.0)), reverse=True),
        "errors": errors[:50],
    }
    sys.stdout.write(_json(out) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="arb_bot.py",
        description="Read-only Polymarket arb scanner (safe by default).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan for within-market YES/NO buy-both arbs (read-only).")
    scan.add_argument("--gamma-base-url", default="https://gamma-api.polymarket.com")
    scan.add_argument("--clob-base-url", default="https://clob.polymarket.com")
    scan.add_argument("--web-base-url", default="https://polymarket.com")
    scan.add_argument("--max-markets", type=int, default=25)
    scan.add_argument("--max-pages", type=int, default=3)
    scan.add_argument("--gamma-limit", type=int, default=25)
    scan.add_argument("--gamma-offset", type=int, default=0)
    scan.add_argument("--min-edge-bps", type=float, default=20.0)
    scan.add_argument("--fee-bps", type=float, default=0.0, help="Conservative fee assumption in bps.")
    scan.add_argument("--sleep-ms", type=int, default=50, help="Sleep between markets to reduce API pressure.")
    scan.add_argument("--skip-geoblock", action="store_true", help="Skip geoblock probe call.")
    scan.set_defaults(func=cmd_scan)

    scan_us = sub.add_parser("scan-us", help="Scan Polymarket US Gateway for within-market buy-both arbs (read-only).")
    scan_us.add_argument("--max-markets", type=int, default=25)
    scan_us.add_argument("--max-pages", type=int, default=3)
    scan_us.add_argument("--limit", type=int, default=25, help="Page size for /v1/markets.")
    scan_us.add_argument("--offset", type=int, default=0)
    scan_us.add_argument("--min-edge-bps", type=float, default=20.0)
    scan_us.add_argument("--fee-bps", type=float, default=0.0, help="Conservative fee assumption in bps.")
    scan_us.add_argument("--sleep-ms", type=int, default=50, help="Sleep between markets to reduce API pressure.")
    scan_us.set_defaults(func=cmd_scan_us)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
