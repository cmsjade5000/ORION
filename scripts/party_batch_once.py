#!/usr/bin/env python3
"""
Run one "coding party" batch:
- eval-run
- eval-reliability-daily
- canary health check
and persist a summary artifact.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> dict:
    p = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run one party batch and persist artifacts.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--candidate", default="openprose-workflow-2026-03")
    ap.add_argument("--continue-on-error", action="store_true", default=True)
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    canary_out = repo / "eval" / "history" / f"canary-check-{ts}.json"

    steps = [
        ("eval_run", ["make", "eval-run"]),
        ("eval_reliability_daily", ["make", "eval-reliability-daily"]),
        (
            "canary_health_check",
            [
                "python3",
                "scripts/canary_health_check.py",
                "--candidate",
                args.candidate,
                "--output-json",
                str(canary_out),
            ],
        ),
    ]

    results: dict[str, dict] = {}
    overall_rc = 0
    for name, cmd in steps:
        res = _run(cmd, repo)
        results[name] = res
        if res["returncode"] != 0 and overall_rc == 0:
            overall_rc = res["returncode"]
            if not args.continue_on_error:
                break

    summary = {
        "kind": "party_batch_once",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo_root": str(repo),
        "results": results,
        "overall_returncode": overall_rc,
    }
    out = repo / "eval" / "history" / f"party-batch-{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("PARTY_BATCH")
    print(f"summary: {out}")
    for name, res in results.items():
        print(f"{name}: rc={res['returncode']}")
    return 0 if overall_rc == 0 else overall_rc


if __name__ == "__main__":
    raise SystemExit(main())
