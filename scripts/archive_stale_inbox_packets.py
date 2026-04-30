#!/usr/bin/env python3
"""Archive and remove selected inbox packet families by packet/workflow ids.

Use this for bounded cleanup of stale recovery artifacts:
- It moves selected packet blocks to an archive file.
- It removes those blocks from `tasks/INBOX/*.md`.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable
import hashlib


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Archive selected Task Packet blocks from INBOX markdown files."
    )
    ap.add_argument("--repo-root", default=".", help="Repository root")
    ap.add_argument(
        "--targets",
        nargs="+",
        required=True,
        help="Packet/workflow ids to remove (Packet ID, Parent/Root/Workflow ID, or idempotency suffix).",
    )
    ap.add_argument(
        "--archive",
        required=True,
        help="Path to archive markdown file (created if missing).",
    )
    return ap.parse_args()


def packet_blocks(lines: list[str]) -> list[tuple[int, int]]:
    starts = [idx for idx, line in enumerate(lines) if line.startswith("TASK_PACKET v1")]
    return [(start, (starts[i + 1] if i + 1 < len(starts) else len(lines))) for i, start in enumerate(starts)]


def packet_fields(block: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block:
        if line == "Result:":
            break
        if ":" not in line:
            continue
        match = re.match(r"^([A-Za-z0-9 _-]+):\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key in {
            "Idempotency Key",
            "Packet ID",
            "Parent Packet ID",
            "Root Packet ID",
            "Workflow ID",
            "Objective",
            "Owner",
        }:
            fields[key] = value
    return fields


def sha256_lines(lines: Iterable[str]) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update((line + "\n").encode("utf-8"))
    return h.hexdigest()


def synthetic_job_id(fields: dict[str, str], block: list[str]) -> str:
    before = []
    for line in block:
        if line == "Result:":
            break
        before.append(line)
    idem = fields.get("Idempotency Key", "").strip()
    if idem:
        return "ik-" + sha256_lines([idem])[:16]
    return "ik-" + sha256_lines(before)[:16]


def block_matches(block: list[str], targets: set[str]) -> bool:
    fields = packet_fields(block)
    candidate_keys = (
        fields.get("Idempotency Key", ""),
        fields.get("Packet ID", ""),
        fields.get("Parent Packet ID", ""),
        fields.get("Root Packet ID", ""),
        fields.get("Workflow ID", ""),
    )
    if any(item in targets for item in candidate_keys):
        return True

    idem = fields.get("Idempotency Key", "")
    if idem.startswith("recovery:stale:"):
        tail = idem.split(":", 2)[-1]
        if tail in targets:
            return True

    derived_id = synthetic_job_id(fields, block)
    if derived_id in targets:
        return True
    return False


def ensure_archive_header(lines: list[str]) -> None:
    if not lines:
        lines.extend(["# Archived Task Packets", ""])
        return
    if not lines[0].startswith("# Archived Task Packets"):
        lines.insert(0, "# Archived Task Packets")
    if len(lines) < 2 or lines[1].strip():
        lines.insert(1, "")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    inbox_dir = repo_root / "tasks" / "INBOX"
    archive_path = repo_root / args.archive

    targets = {item.strip() for item in args.targets if item.strip()}
    removed: list[tuple[str, list[str]]] = []

    if not inbox_dir.exists():
        print("INBOX not found", inbox_dir)
        return 1

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_lines = archive_path.read_text(encoding="utf-8").splitlines()
    else:
        archive_lines = []
    ensure_archive_header(archive_lines)

    for inbox_path in sorted(inbox_dir.glob("*.md")):
        if inbox_path.name.upper() == "README.MD":
            continue
        lines = inbox_path.read_text(encoding="utf-8").splitlines()
        blocks = packet_blocks(lines)
        if not blocks:
            continue

        out_lines: list[str] = []
        cursor = 0
        any_removed = False
        for i, (start, end) in enumerate(blocks):
            block = lines[start:end]
            if block_matches(block, targets):
                any_removed = True
                removed.append((inbox_path.name, block))
            else:
                if cursor < start:
                    out_lines.extend(lines[cursor:start])
                out_lines.extend(block)
            cursor = end

        out_lines.extend(lines[cursor:])
        out_text = "\n".join(out_lines).rstrip() + "\n"
        if any_removed:
            inbox_path.write_text(out_text, encoding="utf-8")

    if removed:
        for owner, block in removed:
            archive_lines.append("")
            archive_lines.append(f"## Source: {owner}")
            archive_lines.extend(block)
        archive_lines.append("")
        archive_path.write_text("\n".join(archive_lines).rstrip() + "\n", encoding="utf-8")

    print(
        f"ARCHIVE_STALE_PACKETS: removed={len(removed)} target_hits={len(targets)} "
        f"archive={archive_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
