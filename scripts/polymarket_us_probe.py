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


def cmd_debug_auth(_: argparse.Namespace) -> int:
    # Print safe metadata only (no secrets).
    api = os.environ.get("POLY_US_API_KEY_ID") or ""
    sec = os.environ.get("POLY_US_SECRET_KEY_B64") or ""
    pth = os.environ.get("POLY_US_PRIVATE_KEY_PATH") or ""

    def _looks_hex(s: str) -> bool:
        t = s.strip()
        if t.lower().startswith("0x"):
            t = t[2:]
        return bool(t) and all(c in "0123456789abcdefABCDEF" for c in t)

    def _looks_b64ish(s: str) -> bool:
        t = "".join(str(s).split())
        if not t:
            return False
        ok = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-")
        return all(c in ok for c in t)

    def _looks_uuid(s: str) -> bool:
        t = str(s or "").strip()
        if len(t) != 36:
            return False
        parts = t.split("-")
        if len(parts) != 5 or [len(x) for x in parts] != [8, 4, 4, 4, 12]:
            return False
        hx = "0123456789abcdefABCDEF"
        return all(c in hx for c in "".join(parts))

    out: Dict[str, Any] = {
        "mode": "debug_auth",
        "ts_unix": int(time.time()),
        "api_key_id_present": bool(api.strip()),
        "api_key_id_len": len(api.strip()),
        "api_key_id_looks_uuid": _looks_uuid(api),
        "secret_present": bool(sec.strip()),
        "secret_len": len("".join(sec.split())),
        "secret_mod4": len("".join(sec.split())) % 4 if sec.strip() else None,
        "secret_looks_hex": _looks_hex(sec),
        "secret_looks_base64ish": _looks_b64ish(sec),
        "private_key_path_set": bool(pth.strip()),
    }
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

    p = sub.add_parser("debug-auth", help="Print safe auth metadata (no secrets).")
    p.set_defaults(func=cmd_debug_auth)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
    def _looks_uuid(s: str) -> bool:
        t = s.strip()
        if len(t) != 36:
            return False
        # 8-4-4-4-12 with hex + dashes
        parts = t.split("-")
        if len(parts) != 5 or [len(x) for x in parts] != [8, 4, 4, 4, 12]:
            return False
        hx = "0123456789abcdefABCDEF"
        return all(c in hx for c in "".join(parts))
