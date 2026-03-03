#!/usr/bin/env python3
"""
Enforce canary stop gates using recent reliability snapshots.

Policy:
- If SLO-R1 or SLO-R2 fail for N consecutive ET days, disable canary promotion
  cron jobs that match configured name patterns.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def _parse_csv_patterns(value: str) -> list[str]:
    parts = [p.strip().lower() for p in (value or "").split(",")]
    return [p for p in parts if p]


def _parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _parse_ts_from_name(path: Path) -> dt.datetime | None:
    m = re.match(r"^reliability-(\d{8})-(\d{6})\.json$", path.name)
    if not m:
        return None
    try:
        parsed = dt.datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc)


def _load_snapshot(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _latest_by_et_day(history_dir: Path, tz: ZoneInfo) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(history_dir.glob("reliability-*.json")):
        payload = _load_snapshot(path)
        if payload is None:
            continue
        ts = _parse_iso(payload.get("generated_at")) or _parse_ts_from_name(path)
        if ts is None:
            continue
        et_day = ts.astimezone(tz).date().isoformat()
        lane = payload.get("lane_wait_24h", {})
        row = {
            "path": str(path),
            "timestamp_utc": ts.isoformat(),
            "date_et": et_day,
            "lane_wait_count": int(lane.get("count", 0)),
            "lane_wait_p95_ms": int(lane.get("p95_ms", 0)),
        }
        prior = rows.get(et_day)
        if prior is None or row["timestamp_utc"] > prior["timestamp_utc"]:
            rows[et_day] = row
    ordered = [rows[k] for k in sorted(rows.keys())]
    return ordered


def _job_matches(name: str, include: list[str], exclude: list[str]) -> bool:
    n = (name or "").lower()
    if include and not any(p in n for p in include):
        return False
    if exclude and any(p in n for p in exclude):
        return False
    return True


def _render_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Stop Gate Enforcement")
    lines.append("")
    lines.append(f"- Generated at: `{report['generated_at_et']}`")
    lines.append(f"- Timezone: `{report['timezone']}`")
    lines.append(f"- Apply: `{report['apply']}`")
    lines.append(f"- Triggered: `{report['triggered']}`")
    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append(
        f"- Consecutive failing ET days required: `{report['policy']['consecutive_days']}`"
    )
    lines.append(
        f"- SLO-R1 max lane wait count: `{report['policy']['max_lane_wait_count']}`"
    )
    lines.append(
        f"- SLO-R2 max lane wait p95 ms: `{report['policy']['max_lane_wait_p95_ms']}`"
    )
    lines.append(
        f"- Include job name patterns: `{report['policy']['include_name_patterns']}`"
    )
    lines.append(
        f"- Exclude job name patterns: `{report['policy']['exclude_name_patterns']}`"
    )
    lines.append("")
    lines.append("## Recent Days")
    lines.append("")
    lines.append("| ET Date | Lane Count | Lane P95 (ms) | R1 Fail | R2 Fail | Day Fail | Snapshot |")
    lines.append("| --- | ---: | ---: | --- | --- | --- | --- |")
    for day in report["recent_days"]:
        lines.append(
            f"| {day['date_et']} | {day['lane_wait_count']} | {day['lane_wait_p95_ms']} | "
            f"{day['r1_fail']} | {day['r2_fail']} | {day['day_fail']} | `{day['path']}` |"
        )
    if not report["recent_days"]:
        lines.append("| none | - | - | - | - | - | - |")
    lines.append("")
    lines.append("## Target Jobs")
    lines.append("")
    for job in report["target_jobs"]:
        lines.append(f"- `{job['id']}` `{job['name']}` (enabled={job['enabled']})")
    if not report["target_jobs"]:
        lines.append("- none")
    lines.append("")
    lines.append("## Changes")
    lines.append("")
    for change in report["changes"]:
        lines.append(f"- {change}")
    if not report["changes"]:
        lines.append("- none")
    lines.append("")
    if report["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce canary stop gates from reliability history.")
    parser.add_argument("--history-dir", default="eval/history")
    parser.add_argument("--jobs-path", default="~/.openclaw/cron/jobs.json")
    parser.add_argument("--timezone", default="America/New_York")
    parser.add_argument("--max-lane-wait-count", type=int, default=6)
    parser.add_argument("--max-lane-wait-p95-ms", type=int, default=10000)
    parser.add_argument("--consecutive-days", type=int, default=2)
    parser.add_argument(
        "--include-name-patterns",
        default="party-batch,canary-rollout,canary-promote,canary-promotion",
    )
    parser.add_argument(
        "--exclude-name-patterns",
        default="route-hygiene,lane-hotspots,reliability,scorecard,skill-discovery",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    now = dt.datetime.now(tz)
    ts = now.strftime("%Y%m%d-%H%M%S")

    history_dir = Path(args.history_dir)
    jobs_path = Path(args.jobs_path).expanduser()
    out_json = Path(args.output_json) if args.output_json else history_dir / f"stop-gate-{ts}.json"
    out_md = Path(args.output_md) if args.output_md else history_dir / f"stop-gate-{ts}.md"
    warnings: list[str] = []

    daily = _latest_by_et_day(history_dir, tz) if history_dir.exists() else []
    if not daily:
        warnings.append("no reliability snapshots found")

    recent = daily[-max(1, args.consecutive_days) :]
    recent_eval: list[dict[str, Any]] = []
    for row in recent:
        r1_fail = row["lane_wait_count"] > args.max_lane_wait_count
        r2_fail = row["lane_wait_p95_ms"] > args.max_lane_wait_p95_ms
        item = dict(row)
        item["r1_fail"] = r1_fail
        item["r2_fail"] = r2_fail
        item["day_fail"] = bool(r1_fail or r2_fail)
        recent_eval.append(item)

    enough_days = len(recent_eval) >= max(1, args.consecutive_days)
    triggered = bool(enough_days and all(x["day_fail"] for x in recent_eval))

    jobs_doc: dict[str, Any] = {}
    if jobs_path.exists():
        try:
            jobs_doc = json.loads(jobs_path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"failed to read jobs file: {exc}")
            jobs_doc = {}
    else:
        warnings.append(f"jobs file missing: {jobs_path}")

    include = _parse_csv_patterns(args.include_name_patterns)
    exclude = _parse_csv_patterns(args.exclude_name_patterns)
    jobs = jobs_doc.get("jobs", []) if isinstance(jobs_doc, dict) else []
    target_jobs: list[dict[str, Any]] = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict):
            continue
        name = str(job.get("name", ""))
        if not _job_matches(name, include, exclude):
            continue
        target_jobs.append(
            {
                "id": str(job.get("id", "")),
                "name": name,
                "enabled": bool(job.get("enabled")),
            }
        )

    changes: list[str] = []
    disabled_ids: list[str] = []
    jobs_changed = False
    if triggered and args.apply and isinstance(jobs, list):
        backup_path = jobs_path.with_name(f"{jobs_path.name}.bak.stopgate.{ts}")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(jobs_path.read_text(encoding="utf-8"), encoding="utf-8")
        changes.append(f"backup created: {backup_path}")

        target_by_id = {x["id"] for x in target_jobs if x["id"]}
        for job in jobs:
            if not isinstance(job, dict):
                continue
            jid = str(job.get("id", ""))
            if jid not in target_by_id:
                continue
            if job.get("enabled") is True:
                job["enabled"] = False
                disabled_ids.append(jid)
                jobs_changed = True
                changes.append(f"disabled job: {jid} ({job.get('name')})")

        if jobs_changed:
            jobs_path.write_text(json.dumps(jobs_doc, indent=2) + "\n", encoding="utf-8")

    if triggered and not args.apply:
        changes.append("triggered but apply=false; no changes written")
    if triggered and args.apply and not disabled_ids:
        changes.append("triggered but no matching enabled target jobs to disable")

    report = {
        "kind": "stop_gate_enforcement",
        "generated_at_et": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "generated_at_utc": now.astimezone(dt.timezone.utc).isoformat(),
        "timezone": args.timezone,
        "apply": args.apply,
        "triggered": triggered,
        "policy": {
            "consecutive_days": int(max(1, args.consecutive_days)),
            "max_lane_wait_count": int(args.max_lane_wait_count),
            "max_lane_wait_p95_ms": int(args.max_lane_wait_p95_ms),
            "include_name_patterns": include,
            "exclude_name_patterns": exclude,
        },
        "recent_days": recent_eval,
        "target_jobs": target_jobs,
        "disabled_job_ids": disabled_ids,
        "changes": changes,
        "warnings": warnings,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(report) + "\n", encoding="utf-8")

    print("STOP_GATE_ENFORCER")
    print(f"json: {out_json.resolve()}")
    print(f"md: {out_md.resolve()}")
    print(f"triggered: {triggered}")
    print(f"disabled_jobs: {len(disabled_ids)}")
    print(f"recent_days_evaluated: {len(recent_eval)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

