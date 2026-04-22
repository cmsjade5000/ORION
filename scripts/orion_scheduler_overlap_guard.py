#!/usr/bin/env python3
"""Fail when local maintenance LaunchAgents overlap with enabled OpenClaw cron jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


KNOWN_OVERLAPS = {
    "assistant-inbox-notify": "ai.orion.inbox_result_notify",
    "assistant-email-triage": "com.openclaw.orion.assistant_email_triage",
    "assistant-agenda-refresh": "com.openclaw.orion.assistant_agenda_refresh",
    "orion-error-review": "com.openclaw.orion.orion_error_review",
    "orion-session-maintenance": "com.openclaw.orion.orion_session_maintenance",
    "orion-ops-bundle": "com.openclaw.orion.orion_ops_bundle",
    "orion-judgment-layer": "com.openclaw.orion.orion_judgment_layer",
}


def load_enabled_cron_jobs(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs") if isinstance(data, dict) else []
    enabled: set[str] = set()
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict):
            continue
        if not bool(job.get("enabled")):
            continue
        name = str(job.get("name") or "").strip()
        if name:
            enabled.add(name)
    return enabled


def detect_overlaps(*, launch_agents_dir: Path, cron_jobs_path: Path) -> list[dict[str, str]]:
    enabled_jobs = load_enabled_cron_jobs(cron_jobs_path)
    overlaps: list[dict[str, str]] = []
    for job_name, label in KNOWN_OVERLAPS.items():
        plist_path = launch_agents_dir / f"{label}.plist"
        if job_name not in enabled_jobs or not plist_path.exists():
            continue
        overlaps.append(
            {
                "job": job_name,
                "launchagent_label": label,
                "launchagent_path": str(plist_path),
            }
        )
    return overlaps


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Fail when LaunchAgents and OpenClaw cron overlap.")
    ap.add_argument(
        "--launch-agents-dir",
        default=str(Path.home() / "Library" / "LaunchAgents"),
        help="LaunchAgents directory to inspect.",
    )
    ap.add_argument(
        "--cron-jobs",
        default=str(Path.home() / ".openclaw" / "cron" / "jobs.json"),
        help="OpenClaw cron jobs JSON file.",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON output.")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    launch_agents_dir = Path(args.launch_agents_dir).expanduser().resolve()
    cron_jobs_path = Path(args.cron_jobs).expanduser().resolve()
    overlaps = detect_overlaps(
        launch_agents_dir=launch_agents_dir,
        cron_jobs_path=cron_jobs_path,
    )
    payload = {
        "ok": not overlaps,
        "launch_agents_dir": str(launch_agents_dir),
        "cron_jobs_path": str(cron_jobs_path),
        "overlaps": overlaps,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    elif overlaps:
        print("ERROR: overlapping ORION maintenance schedulers detected:")
        for item in overlaps:
            print(
                f"- {item['job']}: enabled OpenClaw cron + LaunchAgent {item['launchagent_path']}"
            )
    else:
        print("OK: no overlapping ORION maintenance schedulers detected.")
    return 0 if not overlaps else 1


if __name__ == "__main__":
    raise SystemExit(main())
