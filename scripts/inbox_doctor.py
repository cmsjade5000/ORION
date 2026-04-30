#!/usr/bin/env python3
"""Read-only health check for the ORION inbox follow-through system."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


LEGACY_CRON_NAMES = {"assistant-task-loop", "inbox-result-notify-discord"}
CANONICAL_LABEL = "ai.orion.inbox_result_notify"
EMAIL_REPLY_STUCK_MINUTES = 15.0


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _run(argv: list[str], *, cwd: Path, timeout: int = 20) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as exc:
        return 127, "", str(exc)
    return int(proc.returncode), proc.stdout or "", proc.stderr or ""


def _validate_packets(repo_root: Path) -> dict[str, object]:
    rc, stdout, stderr = _run(["python3", "scripts/validate_task_packets.py"], cwd=repo_root)
    return {"ok": rc == 0, "returncode": rc, "output": (stdout + stderr).strip()}


def _packet_audit(repo_root: Path) -> dict[str, object]:
    rc, stdout, stderr = _run(["python3", "scripts/packet_audit.py", "--repo-root", str(repo_root), "--json"], cwd=repo_root)
    try:
        payload = json.loads(stdout)
    except Exception:
        payload = {}
    counts = payload.get("counts", {}) if isinstance(payload, dict) else {}
    issues = payload.get("issues", []) if isinstance(payload, dict) else []
    return {
        "ok": rc == 0 and bool(payload.get("ok", False)) if isinstance(payload, dict) else False,
        "returncode": rc,
        "issue_count": int(payload.get("issue_count", 0) or 0) if isinstance(payload, dict) else 0,
        "counts": counts if isinstance(counts, dict) else {},
        "issues": issues if isinstance(issues, list) else [],
        "output": (stderr or "").strip(),
    }


def _summary_health(repo_root: Path, *, max_age_seconds: int) -> dict[str, object]:
    path = repo_root / "tasks" / "JOBS" / "summary.json"
    payload = _load_json(path, {})
    exists = path.exists()
    age_seconds = int(max(0, time.time() - path.stat().st_mtime)) if exists else None
    counts = payload.get("counts", {}) if isinstance(payload, dict) else {}
    workflows = payload.get("workflow_counts", {}) if isinstance(payload, dict) else {}
    stale = bool(age_seconds is not None and age_seconds > max_age_seconds)
    return {
        "ok": exists and isinstance(payload, dict) and not stale,
        "exists": exists,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "counts": counts if isinstance(counts, dict) else {},
        "workflow_counts": workflows if isinstance(workflows, dict) else {},
    }


def _dead_letters(repo_root: Path) -> dict[str, object]:
    path = repo_root / "tmp" / "inbox_notify_dead_letters.jsonl"
    if not path.exists():
        return {"ok": True, "count": 0, "active_failed_delivery_count": 0, "path": str(path)}
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = _load_json(repo_root / "tasks" / "JOBS" / "summary.json", {})
    active_failed = 0
    for job in summary.get("jobs", []) if isinstance(summary, dict) else []:
        if not isinstance(job, dict):
            continue
        delivery = job.get("notification_delivery")
        if not isinstance(delivery, dict):
            continue
        for kind in ("queued", "result"):
            payload = delivery.get(kind)
            if isinstance(payload, dict) and str(payload.get("status") or "") == "failed-to-deliver":
                active_failed += 1
    return {
        "ok": active_failed == 0,
        "count": len(lines),
        "active_failed_delivery_count": active_failed,
        "path": str(path),
    }


def _notify_state(repo_root: Path) -> dict[str, object]:
    path = repo_root / "tmp" / "inbox_notify_state.json"
    payload = _load_json(path, {})
    if not isinstance(payload, dict):
        payload = {}
    outcomes: dict[str, int] = {}
    for key in payload:
        parts = str(key).split(":")
        if len(parts) >= 4 and parts[0] in {"telegram", "discord"} and parts[2] != "attempts":
            outcomes[parts[2]] = outcomes.get(parts[2], 0) + 1
    return {"ok": True, "exists": path.exists(), "path": str(path), "outcomes": outcomes}


def _runtime(repo_root: Path, *, skip_runtime: bool) -> dict[str, object]:
    launchagent = Path.home() / "Library" / "LaunchAgents" / f"{CANONICAL_LABEL}.plist"
    if skip_runtime:
        return {"ok": True, "skipped": True, "launchagent_exists": launchagent.exists()}
    rc, stdout, stderr = _run(["launchctl", "print", f"gui/{_uid()}/{CANONICAL_LABEL}"], cwd=repo_root)
    return {
        "ok": launchagent.exists() and rc == 0,
        "skipped": False,
        "launchagent_exists": launchagent.exists(),
        "launchctl_returncode": rc,
        "launchctl_excerpt": "\n".join((stdout + stderr).splitlines()[:12]),
    }


def _uid() -> str:
    rc, stdout, _stderr = _run(["id", "-u"], cwd=Path.cwd(), timeout=5)
    return stdout.strip() if rc == 0 and stdout.strip() else "501"


def _cron_overlap(repo_root: Path) -> dict[str, object]:
    rc, stdout, _stderr = _run(["openclaw", "cron", "list", "--all", "--json"], cwd=repo_root)
    if rc != 0:
        return {"ok": True, "checked": False, "enabled_legacy": []}
    payload = _load_json_from_text(stdout, {})
    enabled: list[str] = []
    for job in payload.get("jobs", []) if isinstance(payload, dict) else []:
        if isinstance(job, dict) and job.get("enabled") and str(job.get("name") or "") in LEGACY_CRON_NAMES:
            enabled.append(str(job.get("name")))
    return {"ok": not enabled, "checked": True, "enabled_legacy": sorted(set(enabled))}


def _email_reply_queue(repo_root: Path, *, threshold_minutes: float = EMAIL_REPLY_STUCK_MINUTES) -> dict[str, object]:
    summary = _load_json(repo_root / "tasks" / "JOBS" / "summary.json", {})
    now_ts = time.time()
    stuck: list[dict[str, object]] = []
    queued_count = 0
    for job in summary.get("jobs", []) if isinstance(summary, dict) else []:
        if not isinstance(job, dict):
            continue
        if str(job.get("state") or "") != "queued":
            continue
        owner = str(job.get("owner") or "").strip().upper()
        objective = str(job.get("objective") or "").strip().lower()
        if owner != "SCRIBE" or "send-ready draft response" not in objective:
            continue
        queued_count += 1
        detail = job
        job_id = str(job.get("job_id") or "").strip()
        if job_id:
            loaded = _load_json(repo_root / "tasks" / "JOBS" / f"{job_id}.json", {})
            if isinstance(loaded, dict):
                detail = {**job, **loaded}
        age_minutes = None
        pending_since = detail.get("pending_since_ts")
        if isinstance(pending_since, (int, float)):
            age_minutes = max(0.0, (now_ts - float(pending_since)) / 60.0)
        elif isinstance(detail.get("age_hours"), (int, float)):
            age_minutes = max(0.0, float(detail["age_hours"]) * 60.0)
        if age_minutes is not None and age_minutes >= threshold_minutes:
            stuck.append(
                {
                    "job_id": job.get("job_id"),
                    "objective": job.get("objective"),
                    "age_minutes": round(age_minutes, 1),
                    "inbox": job.get("inbox"),
                }
            )
    return {
        "ok": not stuck,
        "queued_count": queued_count,
        "stuck_count": len(stuck),
        "threshold_minutes": threshold_minutes,
        "stuck": stuck,
    }


def _load_json_from_text(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def run_doctor(repo_root: Path, *, skip_runtime: bool = False, max_summary_age_seconds: int = 900) -> dict[str, object]:
    checks = {
        "packet_validation": _validate_packets(repo_root),
        "packet_audit": _packet_audit(repo_root),
        "jobs_summary": _summary_health(repo_root, max_age_seconds=max_summary_age_seconds),
        "dead_letters": _dead_letters(repo_root),
        "notify_state": _notify_state(repo_root),
        "email_reply_queue": _email_reply_queue(repo_root),
        "runtime": _runtime(repo_root, skip_runtime=skip_runtime),
        "cron_overlap": _cron_overlap(repo_root),
    }
    issues: list[str] = []
    for name, payload in checks.items():
        if isinstance(payload, dict) and not payload.get("ok", False):
            issues.append(name)
    return {"ok": not issues, "issues": issues, "checks": checks}


def _render_text(report: dict[str, object]) -> str:
    checks = report.get("checks", {}) if isinstance(report.get("checks"), dict) else {}
    summary = checks.get("jobs_summary", {}) if isinstance(checks.get("jobs_summary"), dict) else {}
    dead = checks.get("dead_letters", {}) if isinstance(checks.get("dead_letters"), dict) else {}
    runtime = checks.get("runtime", {}) if isinstance(checks.get("runtime"), dict) else {}
    email = checks.get("email_reply_queue", {}) if isinstance(checks.get("email_reply_queue"), dict) else {}
    audit = checks.get("packet_audit", {}) if isinstance(checks.get("packet_audit"), dict) else {}
    return "\n".join(
        [
            f"INBOX_DOCTOR {'OK' if report.get('ok') else 'WARN'}",
            f"issues: {', '.join(report.get('issues', [])) if report.get('issues') else 'none'}",
            f"queue: {summary.get('counts', {})}",
            f"packet_audit: issues={audit.get('issue_count', 0)} errors={audit.get('counts', {}).get('error', 0) if isinstance(audit.get('counts'), dict) else 0}",
            f"email_reply_queue: queued={email.get('queued_count', 0)} stuck={email.get('stuck_count', 0)}",
            f"summary_age_seconds: {summary.get('age_seconds')}",
            f"dead_letters: {dead.get('count', 0)}",
            f"launchagent: {'ok' if runtime.get('ok') else 'warn'}",
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose ORION inbox follow-through health.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-runtime", action="store_true", help="Skip launchctl/runtime checks for tests or CI.")
    ap.add_argument("--max-summary-age-seconds", type=int, default=900)
    args = ap.parse_args()
    report = run_doctor(
        Path(args.repo_root).resolve(),
        skip_runtime=bool(args.skip_runtime),
        max_summary_age_seconds=max(1, int(args.max_summary_age_seconds)),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
