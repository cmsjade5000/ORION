#!/usr/bin/env python3
"""
Deterministic POLARIS admin packet worker.

This intentionally handles only read-only direct admin triage packets. It
classifies quick captures and writes a bounded Result block for ORION to review.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from inbox_file_ops import atomic_write_text, locked_file, parse_inbox_packets, packet_identity
except Exception:  # pragma: no cover
    from scripts.inbox_file_ops import atomic_write_text, locked_file, parse_inbox_packets, packet_identity  # type: ignore


def _is_eligible(packet) -> bool:
    fields = packet.fields
    return (
        fields.get("Owner", "").strip().upper() == "POLARIS"
        and fields.get("Requester", "").strip().upper() == "ORION"
        and fields.get("Tool Scope", "").strip().lower() == "read-only"
        and fields.get("Execution Mode", "").strip().lower() == "direct"
        and packet.result_status is None
    )


def _extract_capture_text(lines: list[str]) -> str:
    out: list[str] = []
    in_capture = False
    for line in lines:
        stripped = line.strip()
        if stripped == "- Capture text:":
            in_capture = True
            continue
        if in_capture:
            if line.startswith("  "):
                out.append(line[2:])
                continue
            if stripped:
                break
    return "\n".join(out).strip()


def _extract_intake_path(lines: list[str]) -> str:
    in_inputs = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Inputs:":
            in_inputs = True
            continue
        if in_inputs:
            if stripped.startswith("- tasks/INTAKE/"):
                return stripped[2:].strip()
            if stripped.endswith(":") and not stripped.startswith("-"):
                break
    return ""


def _combined_text(repo_root: Path, packet_lines: list[str]) -> tuple[str, str]:
    capture_text = _extract_capture_text(packet_lines)
    intake_rel = _extract_intake_path(packet_lines)
    intake_text = ""
    if intake_rel:
        intake_path = repo_root / intake_rel
        if intake_path.exists():
            intake_text = intake_path.read_text(encoding="utf-8", errors="replace")
    return intake_rel, "\n".join(part for part in [capture_text, intake_text] if part).strip()


def _classify(text: str) -> str:
    t = text.lower()
    if any(word in t for word in ("reply", "email", "inbox", "send mail")):
        return "email-prep"
    if any(word in t for word in ("remind", "reminder", "calendar", "schedule", "due ")):
        return "reminder"
    if any(word in t for word in ("agenda", "today", "tomorrow", "weekly review")):
        return "agenda item"
    if any(word in t for word in ("follow up", "follow-up", "delegated", "blocked", "waiting", "check on")):
        return "follow-up"
    if any(word in t for word in ("note", "remember", "save this")):
        return "note"
    return "note"


def _next_step(classification: str, text: str) -> str:
    t = text.lower()
    if classification == "follow-up" and "owner: atlas" in t:
        return "Review the referenced ATLAS packet/result, then ask Cory for any required approval or route the next execution step back through ATLAS."
    if classification == "follow-up":
        return "Summarize the current owner/state and identify the next non-side-effecting follow-up for ORION."
    if classification == "email-prep":
        return "Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof."
    if classification == "reminder":
        return "Prepare the reminder details and ask ORION/Cory for approval before creating any external reminder or calendar record."
    if classification == "agenda item":
        return "Place this into the next agenda/review surface and keep any external scheduling gated on approval."
    return "File as a note/follow-through item and surface the concise next action to ORION."


def _result_block(*, classification: str, next_step: str, intake_rel: str) -> list[str]:
    lines = [
        "",
        "Result:",
        "Status: OK",
        f"Classification: {classification}",
        "Proposed next step:",
        f"- {next_step}",
        "Approval gate:",
        "- Required before any external send, calendar write, reminder write, or destructive edit.",
    ]
    if intake_rel:
        lines.extend(["Evidence:", f"- Intake: {intake_rel}"])
    lines.append("")
    return lines


def _write_result(packet, result_block: list[str]) -> bool:
    inbox = packet.inbox_path
    lock_path = inbox.with_suffix(inbox.suffix + ".lock")
    target_identity = packet_identity(fields=packet.fields, packet_before_result=packet.before_result)

    with locked_file(lock_path):
        lines = inbox.read_text(encoding="utf-8").splitlines()
        packets = parse_inbox_packets(inbox)
        for current in packets:
            current_identity = packet_identity(fields=current.fields, packet_before_result=current.before_result)
            if current_identity != target_identity:
                continue
            if current.result_status is not None:
                return False
            start = current.start_line - 1
            end = current.end_line
            result_idx = None
            for idx, line in enumerate(current.lines):
                if line.strip() == "Result:":
                    result_idx = start + idx
                    break
            if result_idx is None:
                new_lines = lines[:end] + result_block + lines[end:]
            else:
                new_lines = lines[:result_idx] + result_block + lines[end:]
            atomic_write_text(inbox, "\n".join(new_lines).rstrip() + "\n")
            return True
    return False


def run(repo_root: Path, *, max_packets: int) -> int:
    inbox = repo_root / "tasks" / "INBOX" / "POLARIS.md"
    processed = 0
    for packet in reversed(parse_inbox_packets(inbox, repo_root=repo_root)):
        if not _is_eligible(packet):
            continue
        intake_rel, text = _combined_text(repo_root, packet.lines)
        classification = _classify(text)
        next_step = _next_step(classification, text)
        if _write_result(packet, _result_block(classification=classification, next_step=next_step, intake_rel=intake_rel)):
            processed += 1
        if processed >= max_packets:
            break
    print("POLARIS_WORKER_IDLE" if processed == 0 else f"POLARIS_WORKER_OK processed={processed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Process eligible POLARIS admin packets.")
    parser.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    parser.add_argument("--max-packets", type=int, default=1, help="Maximum packets to process.")
    args = parser.parse_args()
    return run(Path(args.repo_root).resolve(), max_packets=max(1, int(args.max_packets)))


if __name__ == "__main__":
    raise SystemExit(main())
