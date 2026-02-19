#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

try:
    from scripts.arb.kalshi_backtest import (  # type: ignore
        settled_rows,
        summarize_by,
        summarize_by_tte_bucket,
        summarize_rows,
        walk_forward,
    )
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi_backtest import (  # type: ignore
        settled_rows,
        summarize_by,
        summarize_by_tte_bucket,
        summarize_rows,
        walk_forward,
    )


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def main() -> int:
    ap = argparse.ArgumentParser(description="Kalshi paper backtest from closed-loop ledger.")
    ap.add_argument("--window-hours", type=float, default=24.0 * 14.0, help="Lookback window for settled trades.")
    ap.add_argument("--fee-bps", type=float, default=0.0, help="Assumed additional fee cost in bps of notional.")
    ap.add_argument("--slippage-bps", type=float, default=0.0, help="Assumed additional slippage cost in bps of notional.")
    ap.add_argument("--walk-forward-folds", type=int, default=4, help="Number of contiguous walk-forward folds.")
    args = ap.parse_args()

    root = _repo_root()
    rows = settled_rows(
        root,
        window_hours=float(args.window_hours),
        fee_bps=float(args.fee_bps),
        slippage_bps=float(args.slippage_bps),
    )
    rows.sort(key=lambda r: int(r.get("ts_unix") or 0))
    out: Dict[str, Any] = {
        "mode": "kalshi_backtest",
        "timestamp_unix": int(time.time()),
        "inputs": {
            "window_hours": float(args.window_hours),
            "fee_bps": float(args.fee_bps),
            "slippage_bps": float(args.slippage_bps),
            "walk_forward_folds": int(args.walk_forward_folds),
        },
        "summary": summarize_rows(rows),
        "breakdown": {
            "by_series": summarize_by(rows, "series"),
            "by_side": summarize_by(rows, "side"),
            "by_regime_bucket": summarize_by(rows, "regime_bucket"),
            "by_tte_bucket": summarize_by_tte_bucket(rows),
        },
        "walk_forward": walk_forward(rows, folds=int(args.walk_forward_folds)),
        "rows": rows,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
