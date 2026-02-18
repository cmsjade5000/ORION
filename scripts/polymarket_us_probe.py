#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional

try:
    from scripts.arb.polymarket_us import PolymarketUSClient  # type: ignore
except ModuleNotFoundError:
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.polymarket_us import PolymarketUSClient  # type: ignore


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _load_dotenv(path: str) -> None:
    # Minimal dotenv loader to support unattended runs (OpenClaw env).
    def _try(p: str) -> bool:
        try:
            with open(os.path.expanduser(p), "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if not k:
                        continue
                    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                        v = v[1:-1]
                    # Do not override explicit environment.
                    if k not in os.environ or os.environ.get(k, "") == "":
                        os.environ[k] = v
            return True
        except Exception:
            return False

    if _try(path):
        return
    if os.path.expanduser(path) != os.path.expanduser("~/.openclaw/.env"):
        _try("~/.openclaw/.env")


def cmd_health(_: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    # Public endpoints should work without creds.
    markets = c.get_markets(params={"limit": 1})
    ok = isinstance(markets, dict)
    out = {"mode": "health", "ok": bool(ok), "ts_unix": int(time.time()), "has_auth": bool(os.environ.get("POLY_US_API_KEY_ID"))}
    print(_json(out))
    return 0 if ok else 2


def cmd_markets(args: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    out = c.get_markets(params={"limit": int(args.limit)})
    print(_json(out))
    return 0


def cmd_book(args: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    out = c.get_market_book_side(str(args.slug), market_side_id=str(args.market_side_id or ""))
    print(_json(out))
    return 0


def cmd_balances(_: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    out = c.get_account_balances()
    print(_json(out))
    return 0


def cmd_positions(args: argparse.Namespace) -> int:
    c = PolymarketUSClient()
    out = c.get_portfolio_positions(limit=int(args.limit))
    print(_json(out))
    return 0


def main() -> int:
    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))

    ap = argparse.ArgumentParser(description="Polymarket US probe (safe, read-only unless you call order endpoints directly).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("health")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("markets")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_markets)

    p = sub.add_parser("book")
    p.add_argument("slug")
    p.add_argument("--market-side-id", default="", help="Optional; fetch per-outcome book using marketSideId.")
    p.set_defaults(func=cmd_book)

    p = sub.add_parser("balances")
    p.set_defaults(func=cmd_balances)

    p = sub.add_parser("positions")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_positions)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
