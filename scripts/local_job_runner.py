#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


TZ = ZoneInfo("America/New_York")
SCHEDULE_GRACE_SECONDS = 300


@dataclass(frozen=True)
class Job:
    name: str
    schedule: dict[str, object]
    runner: Callable[[Path], None]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def state_path(root: Path) -> Path:
    return root / "tmp" / "local_job_bundle_state.json"


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, cwd=str(cwd), env=merged_env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def _assistant_agenda_refresh(root: Path) -> None:
    _run(["/usr/bin/python3", "scripts/assistant_status.py", "--cmd", "refresh", "--json"], cwd=root)


def _assistant_task_loop(root: Path) -> None:
    _run(
        ["/usr/bin/python3", "scripts/inbox_cycle.py", "--repo-root", ".", "--runner-max-packets", "4", "--stale-hours", "24", "--notify-max-per-run", "8"],
        cwd=root,
    )


def _orion_error_review(root: Path) -> None:
    _run(
        [
            "/usr/bin/python3",
            "scripts/orion_error_db.py",
            "--repo-root",
            ".",
            "review",
            "--window-hours",
            "24",
            "--apply-safe-fixes",
            "--escalate-incidents",
            "--json",
        ],
        cwd=root,
    )


def _orion_session_maintenance(root: Path) -> None:
    _run(
        [
            "/usr/bin/python3",
            "scripts/session_maintenance.py",
            "--repo-root",
            ".",
            "--agent",
            "main",
            "--fix-missing",
            "--apply",
            "--doctor",
            "--min-missing",
            "50",
            "--min-reclaim",
            "25",
            "--json",
        ],
        cwd=root,
        env={"AUTO_OK": "1"},
    )


def _orion_ops_bundle(root: Path) -> None:
    _run(
        ["/usr/bin/python3", "scripts/orion_incident_bundle.py", "--repo-root", ".", "--write-latest", "--json"],
        cwd=root,
    )


JOBS: list[Job] = [
    Job("assistant-agenda-refresh", {"type": "interval", "minutes": 15}, _assistant_agenda_refresh),
    Job("assistant-task-loop", {"type": "interval", "minutes": 5}, _assistant_task_loop),
    Job("orion-error-review", {"type": "daily", "times": [(2, 15)]}, _orion_error_review),
    Job("orion-session-maintenance", {"type": "daily", "times": [(2, 45)]}, _orion_session_maintenance),
    Job("orion-ops-bundle", {"type": "daily", "times": [(3, 30)]}, _orion_ops_bundle),
]


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"jobs": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {"jobs": {}}


def save_state(path: Path, obj: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _slot_due(now: dt.datetime, slot: dt.datetime) -> bool:
    delta = (now - slot).total_seconds()
    return 0 <= delta <= SCHEDULE_GRACE_SECONDS


def due_slot_key(job: Job, now: dt.datetime) -> str | None:
    sched_type = str(job.schedule["type"])
    local_now = now.astimezone(TZ).replace(second=0, microsecond=0)

    if sched_type == "interval":
        minutes = int(job.schedule["minutes"])
        minute_total = local_now.hour * 60 + local_now.minute
        aligned_total = minute_total - (minute_total % minutes)
        slot = local_now.replace(hour=aligned_total // 60, minute=aligned_total % 60)
        if _slot_due(local_now, slot):
            return f"{job.name}:{slot.strftime('%Y%m%d%H%M')}"
        return None

    if sched_type == "daily":
        for hour, minute in job.schedule["times"]:  # type: ignore[index]
            slot = local_now.replace(hour=hour, minute=minute)
            if _slot_due(local_now, slot):
                return f"{job.name}:{slot.strftime('%Y%m%d%H%M')}"
        return None

    if sched_type == "weekly":
        weekday = int(job.schedule["weekday"])
        hour, minute = job.schedule["time"]  # type: ignore[index]
        if local_now.isoweekday() != weekday:
            return None
        slot = local_now.replace(hour=hour, minute=minute)
        if _slot_due(local_now, slot):
            return f"{job.name}:{slot.strftime('%Y%m%d%H%M')}"
        return None

    raise ValueError(f"unknown schedule type: {sched_type}")


def run_bundle(root: Path) -> int:
    now = dt.datetime.now(TZ)
    state = load_state(state_path(root))
    jobs_state = state.setdefault("jobs", {})
    failures: list[str] = []

    for job in JOBS:
        slot_key = due_slot_key(job, now)
        if not slot_key:
            continue
        entry = jobs_state.setdefault(job.name, {})
        if entry.get("last_slot_key") == slot_key:
            continue
        try:
            job.runner(root)
            entry["last_status"] = "ok"
            entry["last_error"] = ""
        except Exception as exc:
            entry["last_status"] = "error"
            entry["last_error"] = str(exc)
            failures.append(f"{job.name}: {exc}")
        entry["last_slot_key"] = slot_key
        entry["last_run_at"] = now.isoformat()

    state["updated_at"] = now.isoformat()
    save_state(state_path(root), state)

    if failures:
        for item in failures:
            print(item, file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run direct local scheduled ORION jobs.")
    ap.add_argument("--repo-root", default="")
    ap.add_argument("--bundle", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    if args.bundle:
        return run_bundle(root)
    print("Nothing to do.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
