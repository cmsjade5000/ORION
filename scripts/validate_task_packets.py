#!/usr/bin/env python3
"""
Validate TASK_PACKET v1 blocks in tasks/INBOX/*.md.

This is intentionally lightweight: it enforces required fields and section presence
so ORION -> specialist delegation stays structured and auditable.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


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
NEXT_PACKET_PREFIX = "Next Packet "

ATLAS_DIRECTED_SUBAGENTS = {"NODE", "PULSE", "STRATUS"}
ALLOWED_NOTIFY_CHANNELS = {"telegram", "discord", "none"}
ALLOWED_APPROVAL_GATES = {"CORY_MINIAPP_APPROVED", "LEDGER_RESULT_REQUIRED"}
ALLOWED_NEXT_PACKET_RESULTS = {"OK", "FAILED", "BLOCKED", "ANY"}
RE_YYYY_MM_DD = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ROUTING_OVERRIDE_FIELDS = ("Routing Override Rationale",)


@dataclass
class Packet:
    start_line: int
    lines: list[str]


def _is_yyyy_mm_dd(value: str) -> bool:
    return bool(RE_YYYY_MM_DD.match(value))


def _load_route_owners() -> set[str]:
    path = Path(__file__).resolve().parents[1] / "src" / "core" / "shared" / "orion_routing_contract.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    routes = payload.get("routes", []) if isinstance(payload, dict) else []
    return {
        str(route.get("owner") or "").strip().upper()
        for route in routes
        if isinstance(route, dict) and str(route.get("owner") or "").strip()
    }


CONTRACT_OWNERS = _load_route_owners() | {"ATLAS", "POLARIS", "SCRIBE"}


def _routing_text(fields: dict[str, str], sections: dict[str, list[str]]) -> str:
    parts = [
        fields.get("Objective", ""),
        fields.get("Scope", ""),
        fields.get("Context", ""),
        " ".join(sections.get("Inputs", [])),
    ]
    return " ".join(parts).lower()


def infer_expected_owner(fields: dict[str, str], sections: dict[str, list[str]]) -> str | None:
    text = _routing_text(fields, sections)
    if not text.strip():
        return None
    if any(token in text for token in ("crisis", "panic", "distress", "safety-first support", "grounding response")):
        return "EMBER"
    if any(token in text for token in ("money", "budget", "spending", "tradeoff", "tradeoffs", "risk parameter")):
        return "LEDGER"
    if any(token in text for token in ("retrieve sources", "source-backed", "latest", "current external", "news")):
        return "WIRE"
    if any(token in text for token in ("send-ready draft", "draft response", "email draft", "reply draft")):
        return "SCRIBE"
    if any(token in text for token in ("cron", "reminder", "schedule", "gateway", "host health", "deploy", "recover stale", "implementation", "browser-led", "device-node")):
        return "ATLAS"
    if any(token in text for token in ("admin", "calendar", "inbox triage", "follow-through", "contact registry", "coordinate the inbound")):
        return "POLARIS"
    if any(token in text for token in ("tool scouting", "discovery", "options research")):
        return "PIXEL"
    if "gaming" in text:
        return "QUEST"
    return None


def _has_routing_override(fields: dict[str, str]) -> bool:
    return any(fields.get(key, "").strip() for key in ROUTING_OVERRIDE_FIELDS)


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


def _parse_packet(packet: Packet) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str], dict[str, list[str]]]:
    # "fields" includes required and optional top-level fields (Owner/Requester/Objective/Emergency/etc).
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {s: [] for s in REQUIRED_SECTIONS}
    next_fields: dict[str, str] = {}
    next_sections: dict[str, list[str]] = {s: [] for s in REQUIRED_SECTIONS}
    current_section: str | None = None
    current_next_section: str | None = None

    # Skip header line
    for line in packet.lines[1:]:
        m = RE_KV.match(line)
        if m:
            key = m.group("key").strip()
            value = m.group("value").strip()

            if key.startswith(NEXT_PACKET_PREFIX):
                next_key = key[len(NEXT_PACKET_PREFIX) :].strip()
                current_section = None
                if next_key in REQUIRED_SECTIONS:
                    current_next_section = next_key
                    if value:
                        next_sections[next_key].append(value)
                else:
                    current_next_section = None
                    next_fields[next_key] = value
                continue

            # Store all top-level KV pairs so we can validate policy fields like Emergency/Incident.
            # Section headers (Success Criteria, etc.) are handled below.
            if key not in REQUIRED_SECTIONS:
                fields[key] = value
                current_section = None
                current_next_section = None
                continue

            if key in REQUIRED_SECTIONS:
                current_section = key
                current_next_section = None
                if value:
                    sections[key].append(value)
                continue

            # Unknown header: reset section and continue
            current_section = None
            current_next_section = None
            continue

        if current_next_section:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                next_sections[current_next_section].append(stripped[2:].strip())
            else:
                next_sections[current_next_section].append(stripped)
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

    return fields, sections, next_fields, next_sections


def _validate_packet_fields(
    *,
    errors: list[str],
    path: str,
    packet_num: int,
    start_line: int,
    fields: dict[str, str],
    sections: dict[str, list[str]],
    expected_owner: str | None,
    packet_label: str = "packet",
) -> None:
    for k in REQUIRED_FIELDS:
        if not fields.get(k, "").strip():
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field '{k}:'")

    for s in REQUIRED_SECTIONS:
        if len([x for x in sections.get(s, []) if x.strip()]) == 0:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: section '{s}:' has no items")

    owner = fields.get("Owner", "").strip()
    if expected_owner and owner:
        if "<" in owner or ">" in owner:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: Owner looks like a placeholder: {owner!r}")
        elif owner.upper() != expected_owner:
            errors.append(
                f"{path}:{start_line}: {packet_label} {packet_num}: Owner {owner!r} does not match inbox {expected_owner!r}"
            )

    requester = fields.get("Requester", "").strip()
    emergency = fields.get("Emergency", "").strip().upper()
    incident = fields.get("Incident", "").strip()
    notify = fields.get("Notify", "").strip().lower()
    approval_gate = fields.get("Approval Gate", "").strip()
    gate_evidence = fields.get("Gate Evidence", "").strip()

    if notify:
        tokens = [t.strip() for t in re.split(r"[,+\s]+", notify) if t.strip()]
        bad = sorted({t for t in tokens if t not in ALLOWED_NOTIFY_CHANNELS})
        if bad:
            errors.append(
                f"{path}:{start_line}: {packet_label} {packet_num}: Notify contains unknown channel(s): {bad!r} "
                f"(allowed: {sorted(ALLOWED_NOTIFY_CHANNELS)!r})"
            )

    if expected_owner:
        allowed_requesters = {"ORION"}
        if expected_owner in ATLAS_DIRECTED_SUBAGENTS:
            allowed_requesters = {"ATLAS"}
            if emergency == "ATLAS_UNAVAILABLE":
                allowed_requesters = {"ATLAS", "ORION"}

        if requester and requester.upper() not in allowed_requesters:
            extra = ""
            if expected_owner in ATLAS_DIRECTED_SUBAGENTS:
                extra = " (use 'Requester: ATLAS' unless Emergency: ATLAS_UNAVAILABLE)"
            errors.append(
                f"{path}:{start_line}: {packet_label} {packet_num}: Requester must be one of {sorted(allowed_requesters)!r} "
                f"(got {requester!r}){extra}"
            )

    if approval_gate:
        if approval_gate not in ALLOWED_APPROVAL_GATES:
            errors.append(
                f"{path}:{start_line}: {packet_label} {packet_num}: Approval Gate must be one of "
                f"{sorted(ALLOWED_APPROVAL_GATES)!r} (got {approval_gate!r})"
            )
        if not gate_evidence:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: Approval Gate requires non-empty 'Gate Evidence:'")
        if approval_gate == "LEDGER_RESULT_REQUIRED":
            if owner.upper() not in {"ATLAS", "ORION"}:
                errors.append(
                    f"{path}:{start_line}: {packet_label} {packet_num}: Approval Gate LEDGER_RESULT_REQUIRED requires "
                    f"Owner to be 'ATLAS' or 'ORION' (got {owner!r})"
                )
            if gate_evidence and not re.search(r"\bledger\b", gate_evidence, flags=re.IGNORECASE):
                errors.append(
                    f"{path}:{start_line}: {packet_label} {packet_num}: Gate Evidence must reference LEDGER when "
                    f"Approval Gate is LEDGER_RESULT_REQUIRED"
                )
        if approval_gate == "CORY_MINIAPP_APPROVED":
            if gate_evidence and "task-packet-approvals.jsonl" not in gate_evidence:
                errors.append(
                    f"{path}:{start_line}: {packet_label} {packet_num}: Gate Evidence must reference "
                    f"task-packet-approvals.jsonl when Approval Gate is CORY_MINIAPP_APPROVED"
                )

    if expected_owner == "POLARIS":
        opened = fields.get("Opened", "").strip()
        due = fields.get("Due", "").strip()
        execution_mode = fields.get("Execution Mode", "").strip()
        tool_scope = fields.get("Tool Scope", "").strip()
        if not opened:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field 'Opened:'")
        elif not _is_yyyy_mm_dd(opened):
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: 'Opened:' must be YYYY-MM-DD (got {opened!r})")
        if not due:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field 'Due:'")
        elif not _is_yyyy_mm_dd(due):
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: 'Due:' must be YYYY-MM-DD (got {due!r})")
        if not execution_mode:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field 'Execution Mode:'")
        if not tool_scope:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field 'Tool Scope:'")
        if not notify:
            errors.append(f"{path}:{start_line}: {packet_label} {packet_num}: missing required field 'Notify:'")

    if emergency == "ATLAS_UNAVAILABLE" and not incident:
        errors.append(
            f"{path}:{start_line}: {packet_label} {packet_num}: Emergency ATLAS_UNAVAILABLE requires non-empty 'Incident:' field"
        )

    inferred_owner = infer_expected_owner(fields, sections)
    if inferred_owner and inferred_owner in CONTRACT_OWNERS and owner and owner.upper() != inferred_owner and not _has_routing_override(fields):
        errors.append(
            f"{path}:{start_line}: {packet_label} {packet_num}: routing decision expects Owner {inferred_owner!r} "
            f"for this objective (got {owner!r}); add 'Routing Override Rationale:' if this is intentional"
        )


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
        fields, sections, next_fields, next_sections = _parse_packet(pkt)
        _validate_packet_fields(
            errors=errors,
            path=path,
            packet_num=n,
            start_line=pkt.start_line,
            fields=fields,
            sections=sections,
            expected_owner=expected_owner,
        )

        has_next_packet = bool(next_fields) or any(next_sections[s] for s in REQUIRED_SECTIONS)
        if has_next_packet:
            _validate_packet_fields(
                errors=errors,
                path=path,
                packet_num=n,
                start_line=pkt.start_line,
                fields=next_fields,
                sections=next_sections,
                expected_owner=(next_fields.get("Owner", "").strip().upper() or None),
                packet_label="next packet",
            )
            trigger = (next_fields.get("On Result", "OK") or "OK").strip().upper()
            if trigger not in ALLOWED_NEXT_PACKET_RESULTS:
                errors.append(
                    f"{path}:{pkt.start_line}: next packet {n}: On Result must be one of "
                    f"{sorted(ALLOWED_NEXT_PACKET_RESULTS)!r} (got {trigger!r})"
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
