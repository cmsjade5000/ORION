#!/usr/bin/env python3
"""
Canonical inbox cycle for packet-backed delegated work.

Order matters:
1. run safe/read-only inbox packets
2. reconcile ticket lanes + regenerate notes + write delegated-job artifacts
3. notify on new queued/results events
4. archive old terminal packets out of the active inbox
5. reconcile again so tasks/JOBS reflects any archive changes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_step(argv: list[str]) -> int:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return int(proc.returncode)


def run(
    repo_root: Path,
    *,
    runner_max_packets: int,
    stale_hours: float,
    notify_max_per_run: int,
    archive_min_age_hours: float = 48.0,
) -> int:
    py = sys.executable or "python3"
    steps = [
        [
            py,
            "scripts/run_inbox_packets.py",
            "--repo-root",
            str(repo_root),
            "--max-packets",
            str(max(1, int(runner_max_packets))),
        ],
        [
            py,
            "scripts/task_execution_loop.py",
            "--repo-root",
            str(repo_root),
            "--apply",
            "--stale-hours",
            str(max(0.1, float(stale_hours))),
        ],
        [
            py,
            "scripts/notify_inbox_results.py",
            "--repo-root",
            str(repo_root),
            "--require-notify-telegram",
            "--notify-queued",
            "--max-per-run",
            str(max(1, int(notify_max_per_run))),
        ],
        [
            py,
            "scripts/archive_completed_inbox_packets.py",
            "--repo-root",
            str(repo_root),
            "--min-age-hours",
            str(max(0.0, float(archive_min_age_hours))),
            "--apply",
        ],
        [
            py,
            "scripts/task_execution_loop.py",
            "--repo-root",
            str(repo_root),
            "--apply",
            "--stale-hours",
            str(max(0.1, float(stale_hours))),
        ],
    ]

    for argv in steps:
        rc = _run_step(argv)
        if rc != 0:
            return rc
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the inbox execution/reconcile/notify cycle.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--runner-max-packets", type=int, default=4, help="Max packets for the safe inbox runner.")
    ap.add_argument("--stale-hours", type=float, default=24.0, help="Pending-packet stale threshold in hours.")
    ap.add_argument("--notify-max-per-run", type=int, default=8, help="Max notifications per run.")
    ap.add_argument("--archive-min-age-hours", type=float, default=48.0, help="Minimum terminal-packet age before archive.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    return run(
        repo_root,
        runner_max_packets=args.runner_max_packets,
        stale_hours=args.stale_hours,
        notify_max_per_run=args.notify_max_per_run,
        archive_min_age_hours=args.archive_min_age_hours,
    )


if __name__ == "__main__":
    raise SystemExit(main())
