#!/usr/bin/env python3
"""Self-heal stale Arc Field Guide loop locks."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Result:
    status: str
    action: str
    reason: str
    age_minutes: float | None = None
    cleared_kind: str | None = None


def now_iso_local() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "updated_at": now_iso_local(),
            "active_run": None,
            "last_processed_message_ids": {},
            "inflight_subagents": [],
            "recent_deltas": [],
            "quality": {"min_sources_per_new_fact": 1, "max_repost_without_delta": 0},
        }
    return json.loads(path.read_text())


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def check_and_clear(state: dict[str, Any], max_age_minutes: int) -> Result:
    active = state.get("active_run")
    if not active:
        return Result(status="ok", action="none", reason="no_active_run")

    started_at = active.get("started_at")
    kind = active.get("kind")
    if not started_at:
        state["active_run"] = None
        state["updated_at"] = now_iso_local()
        return Result(
            status="ok",
            action="cleared",
            reason="missing_started_at",
            cleared_kind=kind,
        )

    try:
        started = parse_iso(started_at)
    except ValueError:
        state["active_run"] = None
        state["updated_at"] = now_iso_local()
        return Result(
            status="ok",
            action="cleared",
            reason="invalid_started_at",
            cleared_kind=kind,
        )

    age_minutes = (datetime.now(timezone.utc) - started.astimezone(timezone.utc)).total_seconds() / 60.0
    if age_minutes >= max_age_minutes:
        state["active_run"] = None
        state["updated_at"] = now_iso_local()
        state["last_watchdog_clear"] = {
            "cleared_at": state["updated_at"],
            "cleared_kind": kind,
            "cleared_started_at": started_at,
            "age_minutes": round(age_minutes, 2),
            "max_age_minutes": max_age_minutes,
        }
        return Result(
            status="ok",
            action="cleared",
            reason="stale_lock",
            age_minutes=age_minutes,
            cleared_kind=kind,
        )

    return Result(
        status="ok",
        action="none",
        reason="active_run_within_window",
        age_minutes=age_minutes,
        cleared_kind=kind,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear stale Arc FG active_run locks.")
    parser.add_argument("--state", required=True, help="Path to arc_fg_loop_state.json")
    parser.add_argument("--max-age-minutes", type=int, default=25, help="Stale threshold in minutes")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = load_json(state_path)
    result = check_and_clear(state, args.max_age_minutes)

    if result.action == "cleared":
        save_json(state_path, state)

    print(
        json.dumps(
            {
                "status": result.status,
                "action": result.action,
                "reason": result.reason,
                "age_minutes": None if result.age_minutes is None else round(result.age_minutes, 2),
                "cleared_kind": result.cleared_kind,
                "state": str(state_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
