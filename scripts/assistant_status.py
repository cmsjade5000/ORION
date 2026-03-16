#!/usr/bin/env python3
"""
Deterministic assistant agenda/status generator for ORION Telegram commands.
"""

from __future__ import annotations

import argparse
import json
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
    short_calendar_lines,
    short_reminder_lines,
    today_et,
    write_text,
)


AGENDA_PATH = Path("tasks/NOTES/assistant-agenda.md")


def _render_today(root: Path) -> tuple[str, str]:
    calendar_payload = load_calendar_events(root)
    reminders = load_reminders(root)
    tickets = load_tickets(root)
    packets = load_packets(root)
    active_tickets = [ticket for ticket in tickets if ticket.lane in {"backlog", "in-progress", "testing"}]
    pending_packets = [packet for packet in packets if packet.result_status is None]

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
    if pending_packets:
        for packet in pending_packets[:5]:
            owner = packet.fields.get("Owner", "UNKNOWN")
            objective = packet.fields.get("Objective", "").strip() or "(no objective)"
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

    message = "\n".join(lines).strip()
    return message, _render_markdown_snapshot(calendar_payload, reminders, active_tickets, pending_packets)


def _render_followups(root: Path) -> tuple[str, str]:
    tickets = load_tickets(root)
    followups = extract_followup_lines(tickets)
    packets = load_packets(root, owner="POLARIS")
    pending_polaris = [
        f"{packet.fields.get('Objective', '(no objective)')}"
        for packet in packets
        if packet.result_status is None
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

    message = "\n".join(lines).strip()
    return message, message


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


def _render_markdown_snapshot(calendar_payload, reminders, tickets, pending_packets) -> str:
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
    if pending_packets:
        for packet in pending_packets[:8]:
            owner = packet.fields.get("Owner", "UNKNOWN")
            objective = packet.fields.get("Objective", "").strip() or "(no objective)"
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
    elif args.cmd == "followups":
        message, _ = _render_followups(root)
    elif args.cmd == "review":
        message, _ = _render_review(root)
    elif args.cmd == "refresh":
        path = _write_agenda(root)
        message = f"Assistant agenda refreshed: {path}"
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
    parser.add_argument("--cmd", required=True, choices=["today", "followups", "review", "refresh"])
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
