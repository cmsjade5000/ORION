#!/usr/bin/env python3
"""
Deterministic assistant agenda/status generator for ORION Telegram commands.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from assistant_common import (
    ET,
    extract_followup_lines,
    load_calendar_events,
    load_memory_matches,
    load_packets,
    load_reminders,
    load_tickets,
    now_et,
    repo_root,
    run_json_command,
    short_calendar_lines,
    short_reminder_lines,
    today_et,
    write_text,
)
from delegation_delivery_rules import blocked_direct_telegram_delivery


AGENDA_PATH = Path("tasks/NOTES/assistant-agenda.md")
DREAMING_COMMANDS = ["dreaming-status", "dreaming-help", "dreaming-on", "dreaming-off"]
STATUS_ATTENTION_LIMIT = 6
SUMMARY_STALE_HOURS = 24


def _load_job_summary(root: Path) -> dict[str, object]:
    summary_path = root / "tasks" / "JOBS" / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary_jobs(root: Path) -> list[dict[str, object]]:
    jobs = _load_job_summary(root).get("jobs", [])
    if isinstance(jobs, list) and jobs:
        return [job for job in jobs if isinstance(job, dict)]

    fallback_jobs: list[dict[str, object]] = []
    for packet in load_packets(root):
        owner = packet.fields.get("Owner", packet.inbox_path.stem.upper())
        objective = packet.fields.get("Objective", "").strip() or "(no objective)"
        notify = packet.fields.get("Notify", "")
        state = "queued" if packet.result_status is None else "pending_verification"
        result: dict[str, object] = {
            "present": bool(packet.result_status),
            "raw_status": packet.result_status,
            "status": (packet.result_status or "pending").lower(),
            "job_state": state,
        }
        fallback_jobs.append(
            {
                "job_id": f"fallback:{packet.inbox_path.name}:{packet.start_line}",
                "workflow_id": "",
                "state": state,
                "state_reason": "fallback_packet_scan",
                "owner": owner,
                "objective": objective,
                "notify": notify,
                "notify_channels": [],
                "queued_digest": "",
                "result_digest": "",
                "result": result,
                "inbox": {
                    "path": str(packet.inbox_path.relative_to(root)),
                    "line": packet.start_line,
                },
            }
        )
    return fallback_jobs


def _summary_workflows(root: Path) -> list[dict[str, object]]:
    workflows = _load_job_summary(root).get("workflows", [])
    return [item for item in workflows if isinstance(item, dict)] if isinstance(workflows, list) else []


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _counts_from_jobs(jobs: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for job in jobs:
        state = str(job.get("state") or "unknown").strip().lower() or "unknown"
        counts[state] = counts.get(state, 0) + 1
    return counts


def _summary_counts(summary: dict[str, object], jobs: list[dict[str, object]]) -> dict[str, int]:
    raw_counts = summary.get("counts")
    if isinstance(raw_counts, dict) and raw_counts:
        return {str(key): _safe_int(value) for key, value in raw_counts.items()}
    return _counts_from_jobs(jobs)


def _job_delivery_status(job: dict[str, object], phase: str) -> str:
    delivery = job.get("notification_delivery")
    if not isinstance(delivery, dict):
        return "unknown"
    phase_payload = delivery.get(phase)
    if not isinstance(phase_payload, dict):
        return "unknown"
    return str(phase_payload.get("status") or "unknown").strip().lower() or "unknown"


def _is_terminal_job(job: dict[str, object]) -> bool:
    state = str(job.get("state") or "").strip().lower()
    if state in {"blocked", "cancelled", "complete", "pending_verification"}:
        return True
    result = job.get("result")
    if not isinstance(result, dict):
        return False
    return bool(result.get("present")) or str(result.get("status") or "").strip().lower() in {"ok", "failed", "blocked"}


def _status_job_label(job: dict[str, object]) -> str:
    owner = str(job.get("owner") or "UNKNOWN").strip() or "UNKNOWN"
    objective = str(job.get("objective") or "(no objective)").strip() or "(no objective)"
    return f"{owner}: {objective}"


def _status_attention_items(summary: dict[str, object], jobs: list[dict[str, object]], workflows: list[dict[str, object]]) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []

    if not summary:
        items.append((0, "Job summary missing; using inbox fallback."))
    else:
        updated_ts = _safe_float(summary.get("updated_ts"))
        if updated_ts is None:
            items.append((0, "Job summary timestamp unavailable."))
        else:
            age_hours = max(0.0, (time.time() - updated_ts) / 3600.0)
            if age_hours > SUMMARY_STALE_HOURS:
                items.append((0, f"Job summary stale ({age_hours:.1f}h old)."))

    for job in jobs:
        label = _status_job_label(job)
        result_delivery = _job_delivery_status(job, "result")
        if result_delivery == "failed-to-deliver":
            items.append((1, f"{label} (result notification failed-to-deliver)"))
            continue
        if _is_terminal_job(job) and result_delivery == "pending":
            items.append((2, f"{label} (result notification pending)"))
            continue

        state = str(job.get("state") or "").strip().lower()
        if state == "blocked":
            reason = str(job.get("state_reason") or "blocked").strip() or "blocked"
            items.append((3, f"{label} ({reason})"))
        elif state == "pending_verification":
            items.append((4, f"{label} (pending verification)"))

    for workflow in workflows:
        state = str(workflow.get("state") or "").strip().lower()
        if state not in {"manual_required", "unsupported"}:
            continue
        workflow_id = str(workflow.get("workflow_id") or "(unknown)").strip() or "(unknown)"
        owners = workflow.get("owners")
        owner_text = ", ".join(str(owner).strip() for owner in owners if str(owner).strip()) if isinstance(owners, list) else "unknown"
        if not owner_text:
            owner_text = "unknown"
        items.append((5, f"workflow {workflow_id} requires {state} handling (owners={owner_text})"))

    return sorted(items, key=lambda item: (item[0], item[1]))


def _format_status_updated_at(summary: dict[str, object]) -> str:
    updated_ts = _safe_float(summary.get("updated_ts"))
    if updated_ts is None:
        return "unknown"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(updated_ts))
    except (OSError, OverflowError, ValueError):
        return "unknown"


def _render_status(root: Path) -> tuple[str, str]:
    summary = _load_job_summary(root)
    jobs = _summary_jobs(root)
    workflows = _summary_workflows(root)
    counts = _summary_counts(summary, jobs)
    job_count = _safe_int(summary.get("job_count"), len(jobs)) if summary else len(jobs)
    notification_issue_count = sum(
        1
        for job in jobs
        if _job_delivery_status(job, "queued") == "failed-to-deliver"
        or _job_delivery_status(job, "result") == "failed-to-deliver"
    )
    pending_result_delivery_count = sum(
        1
        for job in jobs
        if _is_terminal_job(job) and _job_delivery_status(job, "result") == "pending"
    )
    source = "tasks/JOBS/summary.json" if summary else "inbox fallback (summary missing)"
    count_parts = [f"total={job_count}"]
    for state in ("queued", "in_progress", "pending_verification", "blocked", "complete", "cancelled"):
        if counts.get(state, 0):
            count_parts.append(f"{state}={counts[state]}")

    attention_items = _status_attention_items(summary, jobs, workflows)
    visible_attention = attention_items[:STATUS_ATTENTION_LIMIT]

    lines = [
        "ORION status",
        "",
        "Delegated work:",
        f"- {' '.join(count_parts)}",
        "",
        "Attention needed:",
    ]
    if visible_attention:
        lines.extend(f"- {text}" for _, text in visible_attention)
        if len(attention_items) > STATUS_ATTENTION_LIMIT:
            lines.append(f"- +{len(attention_items) - STATUS_ATTENTION_LIMIT} more attention items")
    else:
        lines.append("- No attention items.")

    lines.extend(
        [
            "",
            "Follow-through:",
            f"- Summary source: {source}",
            f"- Notification issues: {notification_issue_count}",
            f"- Pending result notifications: {pending_result_delivery_count}",
            "",
            "Last updated:",
            f"- {_format_status_updated_at(summary)}",
        ]
    )
    message = "\n".join(lines).strip()
    return message, message


def _run_text_command(argv: list[str], *, cwd: Path, timeout: int = 20) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""

    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, (proc.stdout or "").strip()


def _short_term_recall_audit_from_disk(root: Path) -> dict:
    store_path = root / "memory" / ".dreams" / "short-term-recall.json"
    if not store_path.exists():
        return {
            "exists": False,
            "entryCount": 0,
            "updatedAt": None,
            "storePath": str(store_path),
        }

    entry_count = 0
    updated_at = None
    try:
        raw = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        raw = None

    if isinstance(raw, list):
        entry_count = len(raw)
    elif isinstance(raw, dict):
        updated_at = raw.get("updatedAt")
        for key in ("entries", "items", "recalls", "records"):
            value = raw.get(key)
            if isinstance(value, list):
                entry_count = len(value)
                break
            if isinstance(value, dict):
                entry_count = len(value)
                break

    return {
        "exists": True,
        "entryCount": entry_count,
        "updatedAt": updated_at,
        "storePath": str(store_path),
    }


def _main_memory_sources_from_config(root: Path) -> list[str]:
    agents_payload = run_json_command(["openclaw", "config", "get", "agents.list", "--json"], cwd=root, timeout=5)
    if not isinstance(agents_payload, list):
        return []
    for item in agents_payload:
        if not isinstance(item, dict) or item.get("id") != "main":
            continue
        memory_search = item.get("memorySearch") or {}
        if not isinstance(memory_search, dict):
            return []
        sources = memory_search.get("sources") or []
        return sources if isinstance(sources, list) else []
    return []


def _dreaming_status_payload(root: Path) -> dict:
    slot_ok, slot = _run_text_command(["openclaw", "config", "get", "plugins.slots.memory"], cwd=root)
    enabled_ok, enabled_raw = _run_text_command(
        ["openclaw", "config", "get", "plugins.entries.memory-core.config.dreaming.enabled"],
        cwd=root,
    )
    sources = _main_memory_sources_from_config(root)
    audit = _short_term_recall_audit_from_disk(root)
    entry = {}
    if not audit.get("exists") or not sources:
        memory_payload = run_json_command(["openclaw", "memory", "status", "--agent", "main", "--json"], cwd=root, timeout=5)
        entry = memory_payload[0] if isinstance(memory_payload, list) and memory_payload else {}
        status = entry.get("status") or {}
        status_audit = entry.get("audit") or {}
        if status_audit.get("exists") or not audit.get("exists"):
            audit = status_audit or audit
        sources = sources or status.get("sources") or []

    enabled = enabled_raw.lower() == "true" if enabled_ok else None

    return {
        "slot": slot if slot_ok else None,
        "enabled": enabled,
        "status_ok": bool(entry),
        "sources": sources if isinstance(sources, list) else [],
        "recall_exists": bool(audit.get("exists")),
        "recall_entries": int(audit.get("entryCount") or 0),
        "recall_updated_at": audit.get("updatedAt"),
        "store_path": audit.get("storePath"),
    }


def _render_dreaming_status(root: Path) -> str:
    payload = _dreaming_status_payload(root)
    slot = payload["slot"] or "unknown"
    enabled = payload["enabled"]
    enabled_text = "enabled" if enabled is True else "disabled" if enabled is False else "unknown"
    sources = ", ".join(payload["sources"]) if payload["sources"] else "unknown"
    recall_text = "present" if payload["recall_exists"] else "missing"

    lines = [
        "ORION dreaming status",
        "",
        f"- Memory slot: {slot}",
        f"- Dreaming config: {enabled_text}",
        f"- ORION memory sources: {sources}",
        f"- Short-term recall store: {recall_text}",
        f"- Recall entries: {payload['recall_entries']}",
    ]
    if payload["recall_updated_at"]:
        lines.append(f"- Recall updated: {payload['recall_updated_at']}")
    if payload["store_path"]:
        lines.append(f"- Recall path: {payload['store_path']}")

    if slot != "memory-core":
        lines.append("- Fix needed: dreaming requires the memory slot to be memory-core.")
    elif enabled is False:
        lines.append("- Fix needed: dreaming is disabled in runtime config.")
    elif not payload["recall_exists"]:
        lines.append(
            "- Fix needed: dreaming is enabled, but the short-term recall store is missing; promotion cannot run yet."
        )
    elif payload["recall_entries"] <= 0:
        lines.append(
            "- Dreaming is enabled and the recall store exists, but no recall entries are staged yet."
        )
    else:
        lines.append("- Dreaming is active and the short-term recall store has staged recall entries.")

    return "\n".join(lines)


def _render_dreaming_help() -> str:
    return "\n".join(
        [
            "ORION dreaming commands",
            "",
            "- /dreaming status",
            "- /dreaming on",
            "- /dreaming off",
            "- /dreaming help",
            "",
            "Changing dreaming updates runtime config and may require a gateway restart to apply.",
        ]
    )


def _set_dreaming_enabled(root: Path, enabled: bool) -> str:
    payload = _dreaming_status_payload(root)
    if payload["slot"] != "memory-core":
        return "Dreaming control is blocked because the active memory slot is not memory-core."

    current = payload["enabled"]
    target = "true" if enabled else "false"
    if current is enabled:
        return f"Dreaming is already {'enabled' if enabled else 'disabled'}."

    ok, output = _run_text_command(
        ["openclaw", "config", "set", "plugins.entries.memory-core.config.dreaming.enabled", target],
        cwd=root,
        timeout=45,
    )
    if not ok:
        return output or "Failed to update dreaming config."

    validate_payload = run_json_command(["openclaw", "config", "validate", "--json"], cwd=root, timeout=45)
    validated = bool(validate_payload and validate_payload.get("valid") is True)
    _, enabled_raw = _run_text_command(
        ["openclaw", "config", "get", "plugins.entries.memory-core.config.dreaming.enabled"],
        cwd=root,
    )
    state = "enabled" if enabled_raw.lower() == "true" else "disabled"
    suffix = " Config validated." if validated else " Config validation is pending."
    return f"Dreaming config is now {state}. Restart the gateway to apply.{suffix}"


def _render_today(root: Path) -> tuple[str, str]:
    calendar_payload = load_calendar_events(root)
    reminders = load_reminders(root)
    tickets = load_tickets(root)
    active_tickets = [ticket for ticket in tickets if ticket.lane in {"backlog", "in-progress", "testing"}]
    pending_jobs = [job for job in _summary_jobs(root) if str(job.get("state") or "").strip().lower() == "queued"]

    lines = [
        f"ORION today ({today_et()})",
        "",
        "Calendar:",
    ]
    cal_lines = short_calendar_lines(calendar_payload)
    lines.extend([f"- {line}" for line in cal_lines] or ["- No upcoming calendar events found."])

    lines.append("")
    lines.append("Reminders:")
    reminder_lines = short_reminder_lines(reminders)
    lines.extend([f"- {line}" for line in reminder_lines] or ["- No reminders found."])

    lines.append("")
    lines.append("Open delegated work:")
    if pending_jobs:
        for job in pending_jobs[:5]:
            owner = str(job.get("owner") or "UNKNOWN").strip() or "UNKNOWN"
            objective = str(job.get("objective") or "").strip() or "(no objective)"
            lines.append(f"- {owner}: {objective}")
    else:
        lines.append("- No pending Task Packets.")

    lines.append("")
    lines.append("Next actions:")
    if active_tickets:
        for ticket in active_tickets[:5]:
            lines.append(f"- {ticket.title} [{ticket.lane}]")
    else:
        lines.append("- No open tickets.")

    safety_checks = _load_delegated_specialist_delivery_checks(root)
    if safety_checks:
        lines.append("")
        lines.append("Delegation safety checks:")
        for item in safety_checks:
            lines.append(f"- {item}")

    message = "\n".join(lines).strip()
    return message, _render_markdown_snapshot(calendar_payload, reminders, active_tickets, pending_jobs)


def _render_followups(root: Path) -> tuple[str, str]:
    tickets = load_tickets(root)
    followups = extract_followup_lines(tickets)
    pending_polaris = [
        str(job.get("objective") or "(no objective)")
        for job in _summary_jobs(root)
        if str(job.get("owner") or "").strip().upper() == "POLARIS"
        and str(job.get("state") or "").strip().lower() == "queued"
    ]

    lines = [
        "ORION follow-ups",
        "",
        "Waiting on people/systems:",
    ]
    for item in followups[:6]:
        lines.append(f"- {item}")
    if not followups:
        lines.append("- No explicit follow-ups are recorded in open tickets.")

    lines.append("")
    lines.append("POLARIS queue:")
    for item in pending_polaris[:4]:
        lines.append(f"- {item}")
    if not pending_polaris:
        lines.append("- No pending POLARIS packets.")

    lines.append("")
    lines.append("Delegated workflow follow-ups:")
    job_followups = _load_delegated_workflow_followups(root)
    for item in job_followups:
        lines.append(f"- {item}")
    if not job_followups:
        lines.append("- None blocking or manual.")

    followup_safety = _load_delegated_specialist_delivery_checks(root)
    if followup_safety:
        lines.append("")
        lines.append("Delegation safety checks:")
        for item in followup_safety:
            lines.append(f"- {item}")

    message = "\n".join(lines).strip()
    return message, message


def _load_delegated_workflow_followups(root: Path) -> list[str]:
    followups: list[str] = []
    state_priority = {"blocked": 0, "manual_required": 1, "unsupported": 2}

    def _safe_int(value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _workflow_sort_key(entry: dict[str, object]) -> tuple[int, str]:
        state = str(entry.get("state") or "").strip().lower()
        return (state_priority.get(state, 99), str(entry.get("workflow_id") or ""))

    for workflow in sorted(_summary_workflows(root), key=_workflow_sort_key):
        if not isinstance(workflow, dict):
            continue

        state = str(workflow.get("state") or "").strip().lower()
        if state not in {"blocked", "manual_required", "unsupported"}:
            continue

        workflow_id = str(workflow.get("workflow_id") or "(unknown)").strip()
        owners = workflow.get("owners")
        owner_text = ", ".join(str(owner).strip() for owner in owners if str(owner).strip()) if isinstance(owners, list) else "unknown"
        if not owner_text:
            owner_text = "unknown"
        job_count = _safe_int(workflow.get("job_count"), 0)
        followups.append(
            f"{state}: workflow {workflow_id} (owners={owner_text}, jobs={job_count})"
        )

    return followups


def _load_delegated_specialist_delivery_checks(root: Path) -> list[str]:
    safety_findings: list[str] = []
    for job in _summary_jobs(root):
        state = str(job.get("state") or "").strip().lower()
        if state in {"complete", "cancelled"}:
            continue
        owner = str(job.get("owner") or "UNKNOWN").strip() or "UNKNOWN"
        notify = str(job.get("notify") or "")
        if not blocked_direct_telegram_delivery(owner, notify):
            continue

        objective = str(job.get("objective") or "").strip() or "(no objective)"
        status = str(job.get("result", {}).get("raw_status") or job.get("state") or "pending") if isinstance(job.get("result"), dict) else str(job.get("state") or "pending")
        inbox = job.get("inbox", {})
        if not isinstance(inbox, dict):
            inbox = {}
        inbox_path = str(inbox.get("path") or "(unknown)")
        line_no = int(inbox.get("line") or 0)
        safety_findings.append(
            f"Potential direct specialist Telegram delivery: {owner} packet in {Path(inbox_path).name}:{line_no} ({status}) — {objective}"
        )

    return safety_findings


def _render_review(root: Path) -> tuple[str, str]:
    today_message, _ = _render_today(root)
    followups_message, _ = _render_followups(root)
    memory_lines = load_memory_matches(root, "routine priorities follow-up calendar reminders")

    lines = [
        "ORION daily review",
        "",
        "What matters now:",
        *[f"- {line}" for line in today_message.splitlines()[2:6] if line.strip()],
        "",
        "Follow-through:",
        *[f"- {line}" for line in followups_message.splitlines()[3:6] if line.strip()],
        "",
        "Recent memory worth keeping in mind:",
    ]
    lines.extend([f"- {line}" for line in memory_lines] or ["- No recent assistant memory matches."])
    message = "\n".join(lines).strip()
    return message, message


def _render_markdown_snapshot(calendar_payload, reminders, tickets, pending_jobs) -> str:
    generated_at = now_et().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "# Assistant Agenda",
        "",
        f"Generated: {generated_at}",
        "",
        "## Calendar",
    ]
    lines.extend([f"- {line}" for line in short_calendar_lines(calendar_payload)] or ["- No upcoming calendar events found."])
    lines.append("")
    lines.append("## Reminders")
    lines.extend([f"- {line}" for line in short_reminder_lines(reminders)] or ["- No reminders found."])
    lines.append("")
    lines.append("## Open Tickets")
    lines.extend([f"- {ticket.title} [{ticket.lane}]" for ticket in tickets[:8]] or ["- No open tickets."])
    lines.append("")
    lines.append("## Delegated Work")
    if pending_jobs:
        for job in pending_jobs[:8]:
            owner = str(job.get("owner") or "UNKNOWN").strip() or "UNKNOWN"
            objective = str(job.get("objective") or "").strip() or "(no objective)"
            lines.append(f"- {owner}: {objective}")
    else:
        lines.append("- No pending Task Packets.")
    lines.append("")
    return "\n".join(lines)


def _write_agenda(root: Path) -> str:
    _, markdown = _render_today(root)
    target = root / AGENDA_PATH
    write_text(target, markdown)
    return str(target.relative_to(root))


def cmd_status(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    if args.cmd == "today":
        message, _ = _render_today(root)
    elif args.cmd == "status":
        message, _ = _render_status(root)
    elif args.cmd == "followups":
        message, _ = _render_followups(root)
    elif args.cmd == "review":
        message, _ = _render_review(root)
    elif args.cmd == "refresh":
        path = _write_agenda(root)
        message = f"Assistant agenda refreshed: {path}"
    elif args.cmd == "dreaming-status":
        message = _render_dreaming_status(root)
    elif args.cmd == "dreaming-help":
        message = _render_dreaming_help()
    elif args.cmd == "dreaming-on":
        message = _set_dreaming_enabled(root, True)
    elif args.cmd == "dreaming-off":
        message = _set_dreaming_enabled(root, False)
    else:
        raise SystemExit(f"unsupported command: {args.cmd}")

    if args.json:
        print(json.dumps({"message": message}, indent=2))
    else:
        print(message)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ORION assistant status views.")
    parser.add_argument("--repo-root", help="Override repo root.")
    parser.add_argument(
        "--cmd",
        required=True,
        choices=["today", "status", "followups", "review", "refresh", *DREAMING_COMMANDS],
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
