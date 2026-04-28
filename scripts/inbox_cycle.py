#!/usr/bin/env python3
"""
Canonical inbox cycle for packet-backed delegated work.

Order matters:
1. run safe/read-only inbox packets
2. complete eligible low-risk AgentMail reply packets
3. reconcile ticket lanes + regenerate notes + write delegated-job artifacts
4. notify on new result/workflow milestone events
5. archive completed packets after their notification age-out window
6. run a read-only doctor summary
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run_step(argv: list[str], *, emit: bool = True) -> dict[str, object]:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    if emit and proc.stdout:
        sys.stdout.write(proc.stdout)
    if emit and proc.stderr:
        sys.stderr.write(proc.stderr)
    return {
        "argv": argv,
        "returncode": int(proc.returncode),
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def _safe_json(stdout: str) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run(
    repo_root: Path,
    *,
    runner_max_packets: int,
    stale_hours: float,
    notify_max_per_run: int,
    archive_older_than_hours: float = 48.0,
    json_output: bool = False,
) -> int:
    py = sys.executable or "python3"
    emit = not json_output
    report: dict[str, object] = {"ok": True, "steps": []}

    def _append_step(name: str, argv: list[str], *, step_emit: bool | None = None) -> dict[str, object]:
        step = _run_step(argv, emit=emit if step_emit is None else step_emit)
        step["name"] = name
        report["steps"].append(step)  # type: ignore[union-attr]
        if int(step["returncode"]) != 0:
            report["ok"] = False
        return step

    steps = [
        (
            "runner",
            [
            py,
            "scripts/run_inbox_packets.py",
            "--repo-root",
            str(repo_root),
            "--max-packets",
            str(max(1, int(runner_max_packets))),
            ],
        ),
        (
            "email-reply-worker",
            [
                py,
                "scripts/email_reply_worker.py",
                "--repo-root",
                str(repo_root),
                "--max-packets",
                "2",
                "--alert-stuck",
                "--stuck-minutes",
                "15",
            ],
        ),
        (
            "reconcile",
            [
            py,
            "scripts/task_execution_loop.py",
            "--repo-root",
            str(repo_root),
            "--apply",
            "--stale-hours",
            str(max(0.1, float(stale_hours))),
            ],
        ),
        (
            "notify",
            [
            py,
            "scripts/notify_inbox_results.py",
            "--repo-root",
            str(repo_root),
            "--require-notify-telegram",
            "--max-per-run",
            str(max(1, int(notify_max_per_run))),
            ],
        ),
        (
            "archive",
            [
                py,
                "scripts/archive_completed_inbox_packets.py",
                "--repo-root",
                str(repo_root),
                "--older-than-hours",
                str(max(0.1, float(archive_older_than_hours))),
                "--apply",
                "--json",
            ],
        ),
    ]

    final_rc = 0
    archived_count = 0
    for name, argv in steps:
        step = _append_step(name, argv, step_emit=False if name == "archive" else None)
        if name == "email-reply-worker" and int(step["returncode"]) != 0:
            if emit and step.get("stderr"):
                sys.stderr.write(str(step["stderr"]))
            continue
        if name == "archive":
            archive_payload = _safe_json(str(step.get("stdout") or ""))
            step["parsed"] = archive_payload
            archived_count = int(archive_payload.get("archived_count") or 0)
            if emit:
                sys.stdout.write(
                    "ARCHIVE_COMPLETED "
                    f"archived={archived_count} "
                    f"older_than_hours={archive_payload.get('older_than_hours', archive_older_than_hours)}\n"
                )
        if int(step["returncode"]) != 0:
            final_rc = int(step["returncode"])
            break

    if final_rc == 0 and archived_count > 0:
        _append_step(
            "reconcile-after-archive",
            [
                py,
                "scripts/task_execution_loop.py",
                "--repo-root",
                str(repo_root),
                "--apply",
                "--stale-hours",
                str(max(0.1, float(stale_hours))),
            ],
        )

    doctor = _append_step(
        "doctor",
        [
            py,
            "scripts/inbox_doctor.py",
            "--repo-root",
            str(repo_root),
            "--max-summary-age-seconds",
            "900",
            "--json",
        ],
        step_emit=False,
    )
    doctor_payload = _safe_json(str(doctor.get("stdout") or ""))
    doctor["parsed"] = doctor_payload
    report["doctor"] = doctor_payload
    if emit:
        sys.stdout.write(
            f"INBOX_DOCTOR {'OK' if doctor_payload.get('ok') else 'WARN'} "
            f"issues={','.join(doctor_payload.get('issues', [])) if isinstance(doctor_payload.get('issues'), list) and doctor_payload.get('issues') else 'none'}\n"
        )
    if int(doctor["returncode"]) != 0 and final_rc == 0:
        final_rc = int(doctor["returncode"])

    report["ok"] = bool(final_rc == 0)
    report["returncode"] = final_rc
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    return final_rc


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the inbox execution/reconcile/notify cycle.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--runner-max-packets", type=int, default=4, help="Max packets for the safe inbox runner.")
    ap.add_argument("--stale-hours", type=float, default=24.0, help="Pending-packet stale threshold in hours.")
    ap.add_argument("--notify-max-per-run", type=int, default=8, help="Max notifications per run.")
    ap.add_argument("--archive-older-than-hours", type=float, default=48.0, help="Archive completed packets older than this notification age.")
    ap.add_argument("--json", action="store_true", help="Print structured cycle output.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    return run(
        repo_root,
        runner_max_packets=args.runner_max_packets,
        stale_hours=args.stale_hours,
        notify_max_per_run=args.notify_max_per_run,
        archive_older_than_hours=args.archive_older_than_hours,
        json_output=bool(args.json),
    )


if __name__ == "__main__":
    raise SystemExit(main())
