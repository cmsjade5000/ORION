#!/usr/bin/env python3
"""
Quick capture helper for ORION's admin-copilot workflows.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from assistant_common import ET, repo_root


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "capture"


def _next_intake_path(root: Path, text: str) -> Path:
    stamp = dt.datetime.now(tz=ET).strftime("%Y-%m-%d-%H%M%S")
    slug = _slugify(text)[:48]
    return root / "tasks" / "INTAKE" / f"{stamp}-{slug}.md"


def _append_polaris_packet(root: Path, intake_rel: str, text: str, notify: str) -> int:
    inbox_path = root / "tasks" / "INBOX" / "POLARIS.md"
    current = inbox_path.read_text(encoding="utf-8")
    opened = dt.datetime.now(tz=ET).date()
    due = opened + dt.timedelta(days=2)
    packet = (
        "\n"
        "TASK_PACKET v1\n"
        "Owner: POLARIS\n"
        "Requester: ORION\n"
        f"Notify: {notify}\n"
        f"Opened: {opened.isoformat()}\n"
        f"Due: {due.isoformat()}\n"
        "Execution Mode: direct\n"
        "Tool Scope: read-only\n"
        "Objective: Triage and file Cory's captured admin item into the correct assistant workflow.\n"
        "Success Criteria:\n"
        "- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).\n"
        "- The next safe step is identified without taking external side effects.\n"
        "- ORION can follow up with a concise status update.\n"
        "Constraints:\n"
        "- Prepare/draft first; do not create external records without explicit approval.\n"
        "- Keep all changes local to repo artifacts unless ORION relays approval.\n"
        "Inputs:\n"
        f"- {intake_rel}\n"
        f"- Capture text: {text.strip()}\n"
        "Risks:\n"
        "- low\n"
        "Stop Gates:\n"
        "- Any external send, calendar write, reminder write, or destructive edit.\n"
        "Output Format:\n"
        "- Result block with classification, proposed next step, and any approval gate.\n"
    )
    inbox_path.write_text(current.rstrip() + packet, encoding="utf-8")
    return current.count("TASK_PACKET v1") + 1


def _append_memory(root: Path, text: str) -> None:
    memory_path = root / "memory" / "assistant_memory.jsonl"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": "capture",
        "text": text.strip(),
        "tokens": [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1],
    }
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def cmd_capture(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    text = args.text.strip()
    if not text:
        raise SystemExit("capture text must not be empty")

    intake_path = _next_intake_path(root, text)
    intake_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text(
        "\n".join(
            [
                f"# Intake: {_slugify(text)}",
                "",
                f"Opened: {dt.datetime.now(tz=ET).strftime('%Y-%m-%d %H:%M %Z')}",
                "Source: Telegram /capture",
                "",
                text,
                "",
            ]
        ),
        encoding="utf-8",
    )

    intake_rel = str(intake_path.relative_to(root))
    packet_number = _append_polaris_packet(root, intake_rel, text, args.notify)
    _append_memory(root, text)

    result = {
        "message": (
            "Captured for POLARIS.\n"
            f"- Intake: {intake_rel}\n"
            f"- POLARIS packet queued: #{packet_number}\n"
            "- Next step: POLARIS will classify it and prepare the safest follow-through path."
        ),
        "intake_path": intake_rel,
        "packet_number": packet_number,
    }
    print(json.dumps(result, indent=2) if args.json else result["message"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a quick assistant capture and queue POLARIS triage.")
    parser.add_argument("--repo-root", help="Override repo root.")
    parser.add_argument("--text", required=True, help="Capture text.")
    parser.add_argument("--notify", default="telegram", help="Notify channel(s) for the POLARIS packet.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.set_defaults(func=cmd_capture)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
