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


@dataclass
class Packet:
    start_line: int
    lines: list[str]


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
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {s: [] for s in REQUIRED_SECTIONS}
    current_section: str | None = None

    # Skip header line
    for line in packet.lines[1:]:
        m = RE_KV.match(line)
        if m:
            key = m.group("key").strip()
            value = m.group("value").strip()

            if key in REQUIRED_FIELDS:
                fields[key] = value
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

    # Only validate packets appended under "## Packets" to avoid flagging examples.
    start_idx = 0
    for i, line in enumerate(all_lines):
        if line.strip() == "## Packets":
            start_idx = i + 1
            break

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
        if requester and requester.upper() != "ORION":
            errors.append(f"{path}:{pkt.start_line}: packet {n}: Requester should be 'ORION' (got {requester!r})")

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

