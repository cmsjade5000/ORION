#!/usr/bin/env python3
"""
Append/update a daily reliability summary row in the monthly scorecard.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo


HEADER = "## Daily Reliability Log"
TABLE_HEADER = [
    "| Date (ET) | Lane Wait Count | Lane Wait P95 (ms) | Cron Enabled | Delivery Queue | Eval Gate | Snapshot |",
    "| --- | ---: | ---: | ---: | ---: | --- | --- |",
]


def _latest_snapshot(history_dir: Path) -> Path:
    files = sorted(history_dir.glob("reliability-*.json"))
    if not files:
        raise FileNotFoundError(f"No reliability snapshots found in {history_dir}")
    return files[-1]


def _load_metrics(snapshot: Path) -> dict:
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    lane = data.get("lane_wait_24h", {})
    cron = data.get("cron", {})
    queue = data.get("delivery_queue", {})
    gate = data.get("eval_gate", {})
    return {
        "lane_count": int(lane.get("count", 0)),
        "lane_p95": int(lane.get("p95_ms", 0)),
        "cron_enabled": int(cron.get("enabled", 0)),
        "queue_files": int(queue.get("files", 0)),
        "eval_gate": str(gate.get("status", "unknown")),
    }


def _upsert_row_in_section(lines: list[str], row: str, date_key: str, section_idx: int) -> list[str]:
    next_section_idx = len(lines)
    for i in range(section_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            next_section_idx = i
            break

    # locate table separator inside this section
    sep_idx = -1
    for i in range(section_idx + 1, next_section_idx):
        if lines[i] == TABLE_HEADER[1]:
            sep_idx = i
            break
    if sep_idx == -1:
        lines.insert(section_idx + 1, "")
        lines.insert(section_idx + 2, TABLE_HEADER[0])
        lines.insert(section_idx + 3, TABLE_HEADER[1])
        sep_idx = section_idx + 3
        next_section_idx += 3

    data_start = sep_idx + 1
    for i in range(data_start, next_section_idx):
        if lines[i].startswith(f"| {date_key} |"):
            lines[i] = row
            return lines

    lines.insert(data_start, row)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Update daily reliability log in monthly scorecard.")
    ap.add_argument("--scorecard", default="eval/monthly-scorecard-2026-03.md")
    ap.add_argument("--history-dir", default="eval/history")
    ap.add_argument("--timezone", default="America/New_York")
    args = ap.parse_args()

    scorecard = Path(args.scorecard)
    history_dir = Path(args.history_dir)
    snapshot = _latest_snapshot(history_dir)
    metrics = _load_metrics(snapshot)

    now_et = dt.datetime.now(ZoneInfo(args.timezone))
    date_key = now_et.strftime("%Y-%m-%d")
    rel_snapshot = snapshot.as_posix()
    row = (
        f"| {date_key} | {metrics['lane_count']} | {metrics['lane_p95']} | "
        f"{metrics['cron_enabled']} | {metrics['queue_files']} | {metrics['eval_gate']} | `{rel_snapshot}` |"
    )

    if scorecard.exists():
        lines = scorecard.read_text(encoding="utf-8").splitlines()
    else:
        lines = ["# Monthly Scorecard", ""]

    if HEADER not in lines:
        lines.extend(["", HEADER, ""])
        lines.extend(TABLE_HEADER)

    section_idx = lines.index(HEADER)
    lines = _upsert_row_in_section(lines, row, date_key, section_idx)
    scorecard.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("RELIABILITY_DAILY_UPDATE")
    print(f"scorecard: {scorecard.resolve()}")
    print(f"snapshot: {snapshot.resolve()}")
    print(f"date: {date_key}")
    print(f"row: {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
