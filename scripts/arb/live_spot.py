from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LiveSpot:
    venue: str
    symbol: str
    price: float
    ts_unix: int
    ok: bool
    error: str = ""


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def _series_to_coinbase_product(series: str) -> Optional[str]:
    s = (series or "").upper()
    if "BTC" in s:
        return "BTC-USD"
    if "ETH" in s:
        return "ETH-USD"
    if "XRP" in s:
        return "XRP-USD"
    if "DOGE" in s:
        return "DOGE-USD"
    return None


def live_spot_coinbase_ws(series: str, *, timeout_s: float = 1.5) -> LiveSpot:
    """Fetch a one-shot spot price from Coinbase WS (public), with hard timeout."""
    product = _series_to_coinbase_product(series)
    now = int(time.time())
    if not product:
        return LiveSpot(venue="coinbase_ws", symbol=str(series), price=0.0, ts_unix=now, ok=False, error="unsupported_series")

    root = _repo_root()
    js = os.path.join(root, "scripts", "arb", "coinbase_ws_price.js")
    timeout_ms = int(max(200.0, float(timeout_s) * 1000.0))
    try:
        proc = subprocess.run(
            ["node", js, product, str(timeout_ms)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=float(timeout_s) + 0.5,
        )
    except Exception as e:
        return LiveSpot(venue="coinbase_ws", symbol=product, price=0.0, ts_unix=now, ok=False, error=f"spawn_failed:{type(e).__name__}")

    if int(proc.returncode) != 0:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip()
        err = err[:200] if err else f"rc={proc.returncode}"
        return LiveSpot(venue="coinbase_ws", symbol=product, price=0.0, ts_unix=now, ok=False, error=err)

    line = (proc.stdout or "").strip().splitlines()[-1] if (proc.stdout or "").strip() else ""
    try:
        obj = json.loads(line)
    except Exception:
        return LiveSpot(venue="coinbase_ws", symbol=product, price=0.0, ts_unix=now, ok=False, error="bad_json")

    price = obj.get("price") if isinstance(obj, dict) else None
    ts_ms = obj.get("ts_ms") if isinstance(obj, dict) else None
    try:
        px = float(price)
    except Exception:
        px = 0.0
    if px <= 0.0:
        return LiveSpot(venue="coinbase_ws", symbol=product, price=0.0, ts_unix=now, ok=False, error="bad_price")
    try:
        tsu = int(int(ts_ms) / 1000) if ts_ms is not None else now
    except Exception:
        tsu = now
    return LiveSpot(venue="coinbase_ws", symbol=product, price=float(px), ts_unix=int(tsu), ok=True, error="")


def live_spot(series: str) -> Optional[LiveSpot]:
    """Best-effort live spot fetch using env knobs. Returns None if disabled."""
    enabled = str(os.environ.get("KALSHI_ARB_LIVE_SPOT", "")).strip().lower() in ("1", "true", "yes", "y", "on")
    if not enabled:
        return None
    venue = (os.environ.get("KALSHI_ARB_LIVE_SPOT_VENUE") or "coinbase_ws").strip().lower()
    try:
        timeout_s = float(os.environ.get("KALSHI_ARB_LIVE_SPOT_TIMEOUT_S", "1.5") or 1.5)
    except Exception:
        timeout_s = 1.5

    if venue == "coinbase_ws":
        return live_spot_coinbase_ws(series, timeout_s=timeout_s)
    return live_spot_coinbase_ws(series, timeout_s=timeout_s)

