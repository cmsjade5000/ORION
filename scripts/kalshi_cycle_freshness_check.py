#!/usr/bin/env python3
"""Check freshness of the latest Kalshi cycle status artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Check freshness of tmp/kalshi_ref_arb/last_cycle_status.json")
    parser.add_argument("--repo-root", default=".", help="Repository root containing tmp/kalshi_ref_arb/")
    parser.add_argument("--max-age-sec", type=int, default=600, help="Maximum allowed artifact age in seconds.")
    args = parser.parse_args()

    status_path = os.path.join(args.repo_root, "tmp", "kalshi_ref_arb", "last_cycle_status.json")
    if not os.path.exists(status_path):
        return 2

    with open(status_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    ts_unix = int(payload.get("ts_unix") or 0)
    age_sec = int(time.time()) - ts_unix
    print(age_sec)
    return 0 if age_sec <= int(args.max_age_sec) else 3


if __name__ == "__main__":
    sys.exit(main())
