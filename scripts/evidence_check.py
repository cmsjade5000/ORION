#!/usr/bin/env python3
"""
CLI wrapper for evidence_core validation.

Input: JSON object with:
  - items: list[EvidenceItem-like dict]
Optional:
  - time_window_hours: number
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_core import validate_items


def _read_json(path: str | None) -> object:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate evidence items (freshness + tier + traceability).")
    ap.add_argument("--input", help="Path to input JSON. If omitted, reads from stdin.")
    ap.add_argument("--time-window-hours", type=float, default=None, help="Override time window in hours.")
    ap.add_argument(
        "--min-source-tier",
        default="secondary",
        choices=["primary", "secondary", "low"],
        help="Minimum allowed source tier.",
    )
    args = ap.parse_args()

    obj = _read_json(args.input)
    if not isinstance(obj, dict):
        print("FAIL: input must be a JSON object", file=sys.stderr)
        return 2

    items = obj.get("items")
    if not isinstance(items, list):
        print("FAIL: missing 'items' list", file=sys.stderr)
        return 2

    tw = obj.get("time_window_hours", 24.0)
    if args.time_window_hours is not None:
        tw = args.time_window_hours

    try:
        twf = float(tw)
    except Exception:
        print("FAIL: time_window_hours must be a number", file=sys.stderr)
        return 2

    res = validate_items(items, time_window_hours=twf, min_source_tier=args.min_source_tier)
    if res.ok:
        print("OK")
        return 0

    for e in res.errors:
        print(e, file=sys.stderr)
    print(f"FAIL: {len(res.errors)} error(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

