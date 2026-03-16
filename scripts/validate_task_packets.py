#!/usr/bin/env python3
"""
Validate TASK_PACKET v1 blocks in tasks/INBOX/*.md.

This is intentionally lightweight: it enforces required fields and section presence
so ORION -> specialist delegation stays structured and auditable.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from dataclasses import dataclass


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")

REQUIRED_FIELDS = ("Owner", "Requester", "Objective")
REQUIRED_SECTIONS = (
    "Success Criteria",
    "Constraints",
    "Inputs",
    "Risks",
    "Stop Gates",
    "Output Format",
)

ATLAS_DIRECTED_SUBAGENTS = {"NODE", "PULSE", "STRATUS"}
ALLOWED_NOTIFY_CHANNELS = {"telegram", "discord", "none"}
ALLOWED_APPROVAL_GATES = {"LEDGER_RESULT_REQUIRED"}
RE_YYYY_MM_DD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Packet:
    start_line: int
    lines: list[str]


def _is_yyyy_mm_dd(value: str) -> bool:
    return bool(RE_YYYY_MM_DD.match(value))


def _expected_owner_from_path(path: str) -> str | None:
    base = os.path.basename(path)
    if not base.endswith(".md"):
        return None
    name = base[: -len(".md")]
    if name.upper() == "README":
        return None
    return name.upper()


def _split_packets(lines: list[str], start_line_offset: int) -> list[Packet]:
    packets: list[Packet] = []
    in_fence = False
    current: list[str] | None = None
    current_start: int | None = None

    for idx, raw in enumerate(lines, start=1 + start_line_offset):
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_fence = not in_fence

        if not in_fence and RE_PACKET_HEADER.match(line):
            if current is not None and current_start is not None:
                packets.append(Packet(start_line=current_start, lines=current))
            current = [line]
            current_start = idx
            continue

        if current is not None:
            current.append(line)

    if current is not None and current_start is not None:
        packets.append(Packet(start_line=current_start, lines=current))

    return packets


def _parse_packet(packet: Packet) -> tuple[dict[str, str], dict[str, list[str]]]:
    # "fields" includes required and optional top-level fields (Owner/Requester/Objective/Emergency/etc).
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {s: [] for s in REQUIRED_SECTIONS}
    current_section: str | None = None

    # Skip header line
    for line in packet.lines[1:]:
        m = RE_KV.match(line)
        if m:
            key = m.group("key").strip()
            value = m.group("value").strip()

            # Store all top-level KV pairs so we can validate policy fields like Emergency/Incident.
            # Section headers (Success Criteria, etc.) are handled below.
            if key not in REQUIRED_SECTIONS:
                fields[key] = value
                if key in REQUIRED_FIELDS:
                    current_section = None
                continue

            if key in REQUIRED_SECTIONS:
                current_section = key
                if value:
                    sections[key].append(value)
                continue

            # Unknown header: reset section and continue
            current_section = None
            continue

        if current_section:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                sections[current_section].append(stripped[2:].strip())
            else:
                # Allow non-bullet lines, but they're still counted as content.
                sections[current_section].append(stripped)

    return fields, sections


def validate_inbox_file(path: str) -> list[str]:
    errors: list[str] = []
    expected_owner = _expected_owner_from_path(path)

    with open(path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    # Packets must be appended under "## Packets" to avoid scanning examples/notes.
    packets_header_idx = None
    for i, line in enumerate(all_lines):
        if line.strip() == "## Packets":
            packets_header_idx = i
            break

    if packets_header_idx is None:
        # If there are any packets in this file, it's misformatted.
        if any(RE_PACKET_HEADER.match(ln.rstrip("\n")) for ln in all_lines):
            errors.append(f"{path}: missing required '## Packets' header (TASK_PACKET blocks must be under it)")
        return errors

    start_idx = packets_header_idx + 1

    packets = _split_packets(all_lines[start_idx:], start_line_offset=start_idx)

    for n, pkt in enumerate(packets, start=1):
        fields, sections = _parse_packet(pkt)

        for k in REQUIRED_FIELDS:
            if not fields.get(k, "").strip():
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field '{k}:'")

        for s in REQUIRED_SECTIONS:
            if len([x for x in sections.get(s, []) if x.strip()]) == 0:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: section '{s}:' has no items")

        owner = fields.get("Owner", "").strip()
        if expected_owner and owner:
            if "<" in owner or ">" in owner:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: Owner looks like a placeholder: {owner!r}")
            elif owner.upper() != expected_owner:
                errors.append(
                    f"{path}:{pkt.start_line}: packet {n}: Owner {owner!r} does not match inbox {expected_owner!r}"
                )

        requester = fields.get("Requester", "").strip()
        emergency = fields.get("Emergency", "").strip().upper()
        incident = fields.get("Incident", "").strip()
        notify = fields.get("Notify", "").strip().lower()
        approval_gate = fields.get("Approval Gate", "").strip()
        gate_evidence = fields.get("Gate Evidence", "").strip()

        if notify:
            # Support "telegram,discord" style lists but reject unknown tokens.
            tokens = [t.strip() for t in re.split(r"[,+\s]+", notify) if t.strip()]
            bad = sorted({t for t in tokens if t not in ALLOWED_NOTIFY_CHANNELS})
            if bad:
                errors.append(
                    f"{path}:{pkt.start_line}: packet {n}: Notify contains unknown channel(s): {bad!r} "
                    f"(allowed: {sorted(ALLOWED_NOTIFY_CHANNELS)!r})"
                )

        if expected_owner:
            allowed_requesters = {"ORION"}
            if expected_owner in ATLAS_DIRECTED_SUBAGENTS:
                allowed_requesters = {"ATLAS"}

                # Emergency bypass: ORION may request directly only when ATLAS is unavailable,
                # and only for reversible diagnostic/recovery work (see docs/AGENT_HIERARCHY.md).
                if emergency == "ATLAS_UNAVAILABLE":
                    allowed_requesters = {"ATLAS", "ORION"}

            if requester:
                if requester.upper() not in allowed_requesters:
                    extra = ""
                    if expected_owner in ATLAS_DIRECTED_SUBAGENTS:
                        extra = " (use 'Requester: ATLAS' unless Emergency: ATLAS_UNAVAILABLE)"
                    errors.append(
                        f"{path}:{pkt.start_line}: packet {n}: Requester must be one of {sorted(allowed_requesters)!r} "
                        f"(got {requester!r}){extra}"
                    )

        if approval_gate:
            if approval_gate not in ALLOWED_APPROVAL_GATES:
                errors.append(
                    f"{path}:{pkt.start_line}: packet {n}: Approval Gate must be one of "
                    f"{sorted(ALLOWED_APPROVAL_GATES)!r} (got {approval_gate!r})"
                )
            if not gate_evidence:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: Approval Gate requires non-empty 'Gate Evidence:'")
            if approval_gate == "LEDGER_RESULT_REQUIRED":
                if owner.upper() not in {"ATLAS", "ORION"}:
                    errors.append(
                        f"{path}:{pkt.start_line}: packet {n}: Approval Gate LEDGER_RESULT_REQUIRED requires "
                        f"Owner to be 'ATLAS' or 'ORION' (got {owner!r})"
                    )
                if gate_evidence and not re.search(r"\bledger\b", gate_evidence, flags=re.IGNORECASE):
                    errors.append(
                        f"{path}:{pkt.start_line}: packet {n}: Gate Evidence must reference LEDGER when "
                        f"Approval Gate is LEDGER_RESULT_REQUIRED"
                    )

        if expected_owner == "POLARIS":
            opened = fields.get("Opened", "").strip()
            due = fields.get("Due", "").strip()
            execution_mode = fields.get("Execution Mode", "").strip()
            tool_scope = fields.get("Tool Scope", "").strip()
            notify = fields.get("Notify", "").strip()
            if not opened:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field 'Opened:'")
            elif not _is_yyyy_mm_dd(opened):
                errors.append(f"{path}:{pkt.start_line}: packet {n}: 'Opened:' must be YYYY-MM-DD (got {opened!r})")
            if not due:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field 'Due:'")
            elif not _is_yyyy_mm_dd(due):
                errors.append(f"{path}:{pkt.start_line}: packet {n}: 'Due:' must be YYYY-MM-DD (got {due!r})")
            if not execution_mode:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field 'Execution Mode:'")
            if not tool_scope:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field 'Tool Scope:'")
            if not notify:
                errors.append(f"{path}:{pkt.start_line}: packet {n}: missing required field 'Notify:'")

        # Emergency bypass packets must be incident-linked for auditability.
        if emergency == "ATLAS_UNAVAILABLE" and not incident:
            errors.append(
                f"{path}:{pkt.start_line}: packet {n}: Emergency ATLAS_UNAVAILABLE requires non-empty 'Incident:' field"
            )

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate TASK_PACKET v1 blocks in inbox files.")
    ap.add_argument("paths", nargs="*", help="Inbox file paths to validate. Default: tasks/INBOX/*.md")
    args = ap.parse_args()

    paths = args.paths or sorted(glob.glob(os.path.join("tasks", "INBOX", "*.md")))
    if not paths:
        print("No inbox files found.", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    for p in paths:
        # Skip README if passed explicitly
        if os.path.basename(p).upper() == "README.MD":
            continue
        all_errors.extend(validate_inbox_file(p))

    if all_errors:
        for e in all_errors:
            print(e, file=sys.stderr)
        print(f"\nFAIL: {len(all_errors)} validation error(s).", file=sys.stderr)
        return 1

    print("OK: Task Packets look valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
