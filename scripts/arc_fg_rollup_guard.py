#!/usr/bin/env python3
"""Validate forced-handoff rollup completeness and mark blocked state."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_MARKERS = [
    "SCRIBE_DELTA_PRESENT: yes",
    "LEDGER_DELTA_PRESENT: yes",
    "POLARIS_DELTA_PRESENT: yes",
    "CHAPTERS_FILE_UPDATED: yes",
    "COST_FILE_UPDATED: yes",
    "PM_FILE_UPDATED: yes",
    "FINAL_STATUS: complete",
]


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def run_cmd(args: list[str]) -> str:
    proc = subprocess.run(args, check=True, text=True, capture_output=True)
    return proc.stdout


def latest_summary(job_id: str) -> tuple[str | None, dict[str, Any] | None]:
    raw = run_cmd(["openclaw", "cron", "runs", "--id", job_id, "--limit", "1"])
    data = json.loads(raw)
    entries = data.get("entries") or []
    if not entries:
        return None, None
    entry = entries[0]
    return entry.get("summary"), entry


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": now_iso(), "active_run": None}
    return json.loads(path.read_text())


def write_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(path)


def evaluate(summary: str | None) -> dict[str, Any]:
    if not summary:
        return {"ok": False, "reason": "missing_summary", "missing_markers": REQUIRED_MARKERS}
    missing = [m for m in REQUIRED_MARKERS if m not in summary]
    if missing:
        return {"ok": False, "reason": "missing_required_markers", "missing_markers": missing}
    return {"ok": True, "reason": "all_required_markers_present", "missing_markers": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard forced-handoff rollup completeness.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()

    state_path = Path(args.state)
    summary, entry = latest_summary(args.job_id)
    verdict = evaluate(summary)
    state = load_state(state_path)

    guard_meta = {
        "checked_at": now_iso(),
        "job_id": args.job_id,
        "ok": verdict["ok"],
        "reason": verdict["reason"],
        "missing_markers": verdict["missing_markers"],
        "run_at_ms": None if not entry else entry.get("runAtMs"),
        "status": None if not entry else entry.get("status"),
    }

    state["forced_handoff_guard"] = guard_meta
    state["updated_at"] = guard_meta["checked_at"]

    if verdict["ok"]:
        if state.get("last_error") == "forced_handoff_incomplete_rollup":
            state.pop("last_error", None)
    else:
        state["last_error"] = "forced_handoff_incomplete_rollup"

    write_state(state_path, state)
    print(json.dumps({"status": "ok", "guard": guard_meta, "state": str(state_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
