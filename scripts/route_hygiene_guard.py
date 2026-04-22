#!/usr/bin/env python3
"""
Daily route-hygiene guard for whatsapp routing regressions.

Scans runtime state under ~/.openclaw for:
- enabled cron jobs routing directly to whatsapp (unsafe)
- enabled cron jobs routing last+announce
  - safe autofix when payload contains NO_REPLY (mode -> none)
  - unsafe otherwise
- main agent sessions with route fields pointing to whatsapp
  - safe autofix clears route fields
- delivery queue files with channel=whatsapp
  - safe autofix archives queue files

Outputs JSON + Markdown summaries and returns:
- 0 when no unsafe findings remain
- 2 when unsafe findings remain
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROUTE_FIELDS = ("channel", "lastChannel", "deliveryContext")


def _normalize_channel(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""


def _contains_no_reply(text: str) -> bool:
    return "NO_REPLY" in text.upper()


def _extract_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("message", "text", "prompt", "body", "content"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        for value in payload.values():
            found = _extract_message(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _extract_message(item)
            if found:
                return found
    return ""


def _is_job_enabled(job: dict[str, Any]) -> bool:
    if job.get("enabled") is False:
        return False
    if job.get("disabled") is True:
        return False

    status = str(job.get("status") or "").strip().lower()
    if status in {"disabled", "inactive", "paused"}:
        return False

    state = job.get("state")
    if isinstance(state, str) and state.strip().lower() in {"disabled", "inactive", "paused"}:
        return False
    if isinstance(state, dict):
        if state.get("enabled") is False:
            return False
        state_status = str(state.get("status") or "").strip().lower()
        if state_status in {"disabled", "inactive", "paused"}:
            return False
    return True


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _backup_path(path: Path, ts: str) -> Path:
    return path.with_name(f"{path.name}.bak.routehygiene.{ts}")


def _ensure_backup(path: Path, ts: str, backups: list[str]) -> Path:
    backup = _backup_path(path, ts)
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        backups.append(str(backup))
    return backup


def _value_points_to_whatsapp(value: Any) -> bool:
    if isinstance(value, str):
        return _normalize_channel(value) == "whatsapp"
    if isinstance(value, dict):
        if _normalize_channel(value.get("channel")) == "whatsapp":
            return True
        return any(_value_points_to_whatsapp(v) for v in value.values())
    if isinstance(value, list):
        return any(_value_points_to_whatsapp(v) for v in value)
    return False


def _iter_delivery_payloads(job: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for delivery_key in ("delivery", "deliveryContext"):
        delivery = job.get(delivery_key)
        if isinstance(delivery, dict):
            payloads.append(delivery)
        elif isinstance(delivery, str):
            payloads.append({"channel": delivery})
    return payloads


def _iter_sessions(data: Any) -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(data, dict):
        sessions = data.get("sessions")
        if isinstance(sessions, list):
            for idx, session in enumerate(sessions):
                if isinstance(session, dict):
                    sid = str(session.get("sessionId") or f"sessions[{idx}]")
                    yield sid, session
            return
        for sid, session in data.items():
            if isinstance(session, dict):
                yield str(sid), session
        return

    if isinstance(data, list):
        for idx, session in enumerate(data):
            if isinstance(session, dict):
                sid = str(session.get("sessionId") or f"sessions[{idx}]")
                yield sid, session


def _queue_candidates(queue_root: Path) -> list[Path]:
    out: list[Path] = []
    for folder in (queue_root, queue_root / "failed"):
        if not folder.exists() or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            if ".bak.routehygiene." in path.name:
                continue
            out.append(path)
    return out


def _safe_unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    suffix = 1
    while True:
        candidate = path.with_name(f"{path.name}.{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def _write_markdown(report: dict[str, Any], output_md: Path) -> None:
    counts = report.get("counts", {})
    safe = report.get("findings", {}).get("safe_autofix", [])
    unsafe = report.get("findings", {}).get("unsafe", [])
    changes = report.get("changes", [])
    backups = report.get("backups", [])
    warnings = report.get("warnings", [])
    window = report.get("window_stats", {})

    lines: list[str] = [
        "# Route Hygiene Guard",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Apply mode: `{report.get('apply')}`",
        f"- Timezone: `{report.get('timezone')}`",
        f"- Exit code: `{report.get('exit_code')}`",
        "",
        "## Counts",
        "",
        f"- Safe autofix findings: `{counts.get('safe_autofix', 0)}`",
        f"- Unsafe findings: `{counts.get('unsafe', 0)}`",
        f"- Applied changes: `{counts.get('applied_changes', 0)}`",
        f"- Backups created: `{counts.get('backups', 0)}`",
        "",
        "## Unsafe Findings",
        "",
    ]
    if unsafe:
        for item in unsafe:
            lines.append(
                f"- `{item.get('type')}` at `{item.get('path')}` ({item.get('ref', '-')}) - {item.get('reason')}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Safe Autofix Findings", ""])
    if safe:
        for item in safe:
            lines.append(
                f"- `{item.get('type')}` at `{item.get('path')}` ({item.get('ref', '-')}) - {item.get('reason')}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Changes", ""])
    if changes:
        for item in changes:
            to_path = item.get("to")
            if to_path:
                lines.append(
                    f"- `{item.get('action')}`: `{item.get('path')}` -> `{to_path}` ({item.get('detail', '')})"
                )
            else:
                lines.append(f"- `{item.get('action')}`: `{item.get('path')}` ({item.get('detail', '')})")
    else:
        lines.append("- None")

    lines.extend(["", "## Backups", ""])
    if backups:
        for path in backups:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Window Stats", ""])
    lines.append(f"- Hours: `{window.get('hours')}`")
    lines.append(f"- Cutoff local: `{window.get('cutoff_local')}`")
    lines.append(
        f"- Cron mtime within window: `{window.get('cron_jobs_mtime_within_window')}`"
    )
    lines.append(
        f"- Sessions mtime within window: `{window.get('sessions_mtime_within_window')}`"
    )
    lines.append(f"- Queue files scanned: `{window.get('queue_files_scanned')}`")
    lines.append(f"- Queue files within window: `{window.get('queue_files_within_window')}`")
    lines.append(
        f"- Queue whatsapp findings within window: `{window.get('queue_whatsapp_findings_within_window')}`"
    )

    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily route hygiene guard.")
    parser.add_argument("--apply", action="store_true", help="Apply safe autofixes.")
    parser.add_argument("--hours", type=int, default=24, help="Optional lookback window in hours for stats.")
    parser.add_argument("--output-json", default=None, help="JSON report path.")
    parser.add_argument("--output-md", default=None, help="Markdown report path.")
    parser.add_argument("--timezone", default="America/New_York", help="Timezone for timestamps.")
    args = parser.parse_args()

    try:
        tz = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        raise SystemExit(f"Invalid timezone: {args.timezone}")

    hours = args.hours if args.hours > 0 else 24
    now = dt.datetime.now(tz)
    ts = now.strftime("%Y%m%d-%H%M%S")

    repo_root = Path(__file__).resolve().parent.parent
    history_dir = repo_root / "eval" / "history"
    output_json = (
        Path(args.output_json).expanduser()
        if args.output_json
        else history_dir / f"route-hygiene-{ts}.json"
    )
    output_md = (
        Path(args.output_md).expanduser()
        if args.output_md
        else history_dir / f"route-hygiene-{ts}.md"
    )

    home = Path.home() / ".openclaw"
    cron_path = home / "cron" / "jobs.json"
    sessions_path = home / "agents" / "main" / "sessions" / "sessions.json"
    queue_root = home / "delivery-queue"
    archive_root = home / "delivery-queue-archive" / f"route-hygiene-{ts}"

    safe_findings: list[dict[str, Any]] = []
    unsafe_findings: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    backups: list[str] = []
    warnings: list[str] = []

    # Cron scan + optional safe autofix.
    cron_doc: Any = {}
    cron_modified = False
    if cron_path.exists():
        try:
            cron_doc = _json_load(cron_path)
        except Exception as exc:
            unsafe_findings.append(
                {
                    "type": "cron_parse_error",
                    "path": str(cron_path),
                    "ref": "-",
                    "reason": f"failed to parse cron jobs JSON: {exc}",
                }
            )
        jobs = cron_doc.get("jobs") if isinstance(cron_doc, dict) else None
        if isinstance(jobs, list):
            for idx, job in enumerate(jobs):
                if not isinstance(job, dict):
                    continue
                if not _is_job_enabled(job):
                    continue

                job_ref = str(job.get("id") or job.get("name") or f"jobs[{idx}]")
                message = _extract_message(job.get("payload"))
                for payload in _iter_delivery_payloads(job):
                    channel = _normalize_channel(payload.get("channel"))
                    mode = _normalize_channel(payload.get("mode"))
                    if channel == "whatsapp":
                        unsafe_findings.append(
                            {
                                "type": "cron_whatsapp_enabled",
                                "path": str(cron_path),
                                "ref": job_ref,
                                "reason": "enabled cron job routes delivery.channel=whatsapp",
                            }
                        )

                    if channel == "last" and mode == "announce":
                        if _contains_no_reply(message):
                            safe_findings.append(
                                {
                                    "type": "cron_last_announce_noreply",
                                    "path": str(cron_path),
                                    "ref": job_ref,
                                    "reason": "enabled last+announce cron with NO_REPLY marker can be set to mode=none",
                                }
                            )
                            if args.apply and "mode" in payload:
                                payload["mode"] = "none"
                                cron_modified = True
                                changes.append(
                                    {
                                        "action": "cron_delivery_mode_set_none",
                                        "path": str(cron_path),
                                        "detail": f"{job_ref} delivery.mode announce -> none",
                                    }
                                )
                        else:
                            unsafe_findings.append(
                                {
                                    "type": "cron_last_announce_without_noreply",
                                    "path": str(cron_path),
                                    "ref": job_ref,
                                    "reason": "enabled last+announce cron missing NO_REPLY marker",
                                }
                            )
        elif cron_path.exists() and not unsafe_findings:
            warnings.append(f"cron jobs file present but has unexpected shape: {cron_path}")
    else:
        warnings.append(f"cron jobs file missing: {cron_path}")

    if args.apply and cron_modified:
        _ensure_backup(cron_path, ts, backups)
        _json_write(cron_path, cron_doc)

    # Main sessions scan + optional safe autofix.
    sessions_doc: Any = {}
    sessions_modified = False
    if sessions_path.exists():
        try:
            sessions_doc = _json_load(sessions_path)
        except Exception as exc:
            unsafe_findings.append(
                {
                    "type": "sessions_parse_error",
                    "path": str(sessions_path),
                    "ref": "-",
                    "reason": f"failed to parse sessions JSON: {exc}",
                }
            )

        if sessions_doc:
            for sid, session in _iter_sessions(sessions_doc):
                for container_name, container in (("session", session), ("route", session.get("route"))):
                    if not isinstance(container, dict):
                        continue
                    for field in ROUTE_FIELDS:
                        if field not in container:
                            continue
                        value = container.get(field)
                        if not _value_points_to_whatsapp(value):
                            continue
                        safe_findings.append(
                            {
                                "type": "session_whatsapp_route_field",
                                "path": str(sessions_path),
                                "ref": f"{sid}:{container_name}.{field}",
                                "reason": "session route field points to whatsapp and can be cleared",
                            }
                        )
                        if args.apply and container[field] is not None:
                            container[field] = None
                            sessions_modified = True
                            changes.append(
                                {
                                    "action": "session_route_field_cleared",
                                    "path": str(sessions_path),
                                    "detail": f"{sid}:{container_name}.{field}",
                                }
                            )
    else:
        warnings.append(f"sessions file missing: {sessions_path}")

    if args.apply and sessions_modified:
        _ensure_backup(sessions_path, ts, backups)
        _json_write(sessions_path, sessions_doc)

    # Delivery queue scan + optional safe autofix.
    queue_files = _queue_candidates(queue_root)
    queue_whatsapp_recent = 0
    cutoff = now - dt.timedelta(hours=hours)
    queue_within_window: dict[str, bool] = {}
    for queue_file in queue_files:
        queue_within_window[str(queue_file)] = (
            dt.datetime.fromtimestamp(queue_file.stat().st_mtime, tz=tz) >= cutoff
        )

    for queue_file in queue_files:
        try:
            item = _json_load(queue_file)
        except Exception as exc:
            unsafe_findings.append(
                {
                    "type": "queue_parse_error",
                    "path": str(queue_file),
                    "ref": "-",
                    "reason": f"failed to parse queue item JSON: {exc}",
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        channel = _normalize_channel(item.get("channel"))
        if channel != "whatsapp":
            continue

        if queue_within_window.get(str(queue_file), False):
            queue_whatsapp_recent += 1

        safe_findings.append(
            {
                "type": "queue_whatsapp_item",
                "path": str(queue_file),
                "ref": queue_file.name,
                "reason": "delivery queue item channel=whatsapp can be archived",
            }
        )

        if args.apply:
            _ensure_backup(queue_file, ts, backups)
            rel = queue_file.relative_to(queue_root) if queue_file.is_relative_to(queue_root) else Path(queue_file.name)
            target = _safe_unique_target(archive_root / rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(queue_file), str(target))
            changes.append(
                {
                    "action": "queue_item_archived",
                    "path": str(queue_file),
                    "to": str(target),
                    "detail": "channel=whatsapp",
                }
            )

    cron_recent = cron_path.exists() and dt.datetime.fromtimestamp(cron_path.stat().st_mtime, tz=tz) >= cutoff
    sessions_recent = sessions_path.exists() and dt.datetime.fromtimestamp(
        sessions_path.stat().st_mtime, tz=tz
    ) >= cutoff
    queue_recent = sum(1 for in_window in queue_within_window.values() if in_window)

    exit_code = 2 if unsafe_findings else 0
    report: dict[str, Any] = {
        "kind": "route_hygiene_guard",
        "generated_at": now.isoformat(),
        "timezone": args.timezone,
        "apply": bool(args.apply),
        "hours": hours,
        "paths": {
            "cron_jobs": str(cron_path),
            "sessions_main": str(sessions_path),
            "delivery_queue": str(queue_root),
            "delivery_queue_archive": str(archive_root),
            "output_json": str(output_json),
            "output_md": str(output_md),
        },
        "counts": {
            "safe_autofix": len(safe_findings),
            "unsafe": len(unsafe_findings),
            "applied_changes": len(changes),
            "backups": len(backups),
            "warnings": len(warnings),
        },
        "findings": {
            "safe_autofix": safe_findings,
            "unsafe": unsafe_findings,
        },
        "changes": changes,
        "backups": backups,
        "warnings": warnings,
        "window_stats": {
            "hours": hours,
            "cutoff_local": cutoff.isoformat(),
            "cron_jobs_mtime_within_window": bool(cron_recent),
            "sessions_mtime_within_window": bool(sessions_recent),
            "queue_files_scanned": len(queue_files),
            "queue_files_within_window": queue_recent,
            "queue_whatsapp_findings_within_window": queue_whatsapp_recent,
        },
        "exit_code": exit_code,
    }

    _json_write(output_json, report)
    _write_markdown(report, output_md)

    print("ROUTE_HYGIENE_GUARD")
    print(f"apply={args.apply}")
    print(f"safe_autofix={len(safe_findings)}")
    print(f"unsafe={len(unsafe_findings)}")
    print(f"applied_changes={len(changes)}")
    print(f"json={output_json}")
    print(f"md={output_md}")
    print("exit_code_semantics: 0=no_unsafe_findings, 2=unsafe_findings_present")
    print(f"exit_code={exit_code}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
