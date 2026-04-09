#!/usr/bin/env python3
"""
Consolidate OpenClaw session-memory slug files into canonical daily memory files.

OpenClaw's bundled session-memory hook writes files like:
  memory/YYYY-MM-DD-some-slug.md

memory-core dreaming only treats canonical daily files as short-term recall
sources:
  memory/YYYY-MM-DD.md

This script merges slugged session-memory notes into the canonical daily file
and archives the originals so the consolidation is reversible and idempotent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any


SLUGGED_SESSION_MEMORY_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")
CANONICAL_DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
IMPORT_MARKER_PREFIX = "<!-- openclaw-session-memory-import:"
IMPORT_MARKER_RE = re.compile(
    r"^<!-- openclaw-session-memory-import:\s+(?P<filename>[^\s]+)\s+sha256=(?P<digest>[0-9a-f]{16})\s+-->$",
    re.MULTILINE,
)
METADATA_BLOCK_RE = re.compile(r"^(?:user:\s*)?(?:Conversation info|Sender) \(untrusted metadata\):\s*$")
SESSION_METADATA_RE = re.compile(r"^- \*\*(?:Session Key|Session ID|Source)\*\*:")
HEARTBEAT_NOISE_RE = re.compile(
    r"^(?:user:\s*)?Read HEARTBEAT\.md if it exists|^When reading HEARTBEAT\.md|^Current time:"
)
TOOL_NOISE_RE = re.compile(r"^assistant:\s+<tool_code\s*$|^print\(default_api\.(?:read|memory_search)\(")
SYSTEM_NOISE_RE = re.compile(r"^(?:user:\s*)?System:")
HEARTBEAT_LINE_RE = re.compile(r"^(?:user:\s*)?(?:\[[^\]]+\]\s*)?ping\b", re.IGNORECASE)
HEARTBEAT_REPLY_RE = re.compile(r"^assistant:\s*(?:HEARTBEAT_OK|ORION_OK)\b", re.IGNORECASE)
TIMESTAMP_METADATA_RE = re.compile(r'^"timestamp":\s*"[^"]+"[,]?$', re.IGNORECASE)
JSON_BLOB_KEY_RE = re.compile(r'^"(?:label|id|message_id|sender_id|sender|timestamp|name)":')
INTERNAL_REASONING_HINT_RE = re.compile(
    r"\b(?:let me|let's see|i need to|i should|the user is|the user has been|"
    r"first,\s*i need to|looking at the user|in summary,\s*the assistant should|"
    r"the appropriate response)\b",
    re.IGNORECASE,
)
TRANSPORT_NOISE_RE = re.compile(
    r"(?:transport test|heartbeat_ok|orion_ok|everything ok orion\?|you ok orion\?)",
    re.IGNORECASE,
)


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def import_marker(filename: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{IMPORT_MARKER_PREFIX} {filename} sha256={digest} -->"


def canonical_header(date: str) -> str:
    return f"# Memory for {date}\n"


def collapse_blank_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            collapsed.append(line.rstrip())
            continue
        if blank_count == 0:
            collapsed.append("")
        blank_count += 1
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()
    return collapsed


def _split_blocks(lines: Iterable[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip()
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _dedupe_blocks(blocks: list[list[str]]) -> list[list[str]]:
    deduped: list[list[str]] = []
    seen: set[str] = set()
    for block in blocks:
        signature = "\n".join(block).strip()
        if not signature or signature in seen:
            continue
        seen.add(signature)
        deduped.append(block)
    return deduped


def _looks_like_control_json_block(block: list[str]) -> bool:
    stripped = [line.strip() for line in block if line.strip()]
    if not stripped:
        return False
    if stripped[0] == "```json":
        stripped = stripped[1:]
    if stripped and stripped[-1] == "```":
        stripped = stripped[:-1]
    if len(stripped) < 2:
        return False
    if stripped[0] != "{" or stripped[-1] != "}":
        return False
    key_lines = [line for line in stripped[1:-1] if JSON_BLOB_KEY_RE.match(line)]
    if not key_lines:
        return False
    return all(
        JSON_BLOB_KEY_RE.match(line) or TIMESTAMP_METADATA_RE.match(line) or line in {"{", "}"}
        for line in stripped
    )


def _is_heartbeat_only_block(block: list[str]) -> bool:
    meaningful = [
        line.strip()
        for line in block
        if line.strip() and line.strip().lower() != "## conversation summary"
    ]
    if not meaningful:
        return True
    saw_heartbeat = False
    for line in meaningful:
        if HEARTBEAT_LINE_RE.match(line) or HEARTBEAT_REPLY_RE.match(line):
            saw_heartbeat = True
            continue
        return False
    return saw_heartbeat


def _is_internal_reasoning_block(block: list[str]) -> bool:
    meaningful = [line.strip() for line in block if line.strip()]
    if not meaningful:
        return False
    first = meaningful[0].lower()
    if not first.startswith("assistant:"):
        return False
    text = "\n".join(meaningful)
    if "## conversation summary" in first and INTERNAL_REASONING_HINT_RE.search(text):
        return True
    return INTERNAL_REASONING_HINT_RE.search(text) is not None


def _should_drop_block(block: list[str]) -> bool:
    text = "\n".join(line.strip() for line in block if line.strip())
    if not text:
        return True
    if _looks_like_control_json_block(block):
        return True
    if _is_heartbeat_only_block(block):
        return True
    if _is_internal_reasoning_block(block):
        return True
    if TRANSPORT_NOISE_RE.search(text) and not re.search(r"\b(?:judgment layer|gateway|incident|cron|maintenance)\b", text, re.IGNORECASE):
        return True
    return False


def _sanitize_blocks(lines: list[str]) -> list[list[str]]:
    cleaned_blocks: list[list[str]] = []
    for block in _split_blocks(lines):
        trimmed = [line.rstrip() for line in block if line.strip()]
        if not trimmed:
            continue
        if _should_drop_block(trimmed):
            continue
        cleaned_blocks.append(trimmed)
    return _dedupe_blocks(cleaned_blocks)


def sanitize_content(content: str) -> str:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned: list[str] = []
    skip_fence = False
    for line in lines:
        stripped = line.strip()
        if skip_fence:
            if stripped.startswith("```"):
                skip_fence = False
            continue
        if METADATA_BLOCK_RE.match(stripped):
            skip_fence = True
            continue
        if SESSION_METADATA_RE.match(stripped):
            continue
        if HEARTBEAT_NOISE_RE.match(stripped):
            continue
        if TOOL_NOISE_RE.match(stripped):
            continue
        if SYSTEM_NOISE_RE.match(stripped):
            continue
        cleaned.append(line)
    if cleaned and cleaned[0].startswith("# Session:"):
        cleaned = cleaned[1:]
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    blocks = _sanitize_blocks(collapse_blank_lines(cleaned))
    if not blocks:
        return ""
    rendered: list[str] = []
    for block in blocks:
        if rendered:
            rendered.append("")
        rendered.extend(block)
    return "\n".join(rendered).strip()


def should_import_content(content: str) -> bool:
    sanitized = sanitize_content(content)
    if not sanitized:
        return False
    lines = [line for line in sanitized.splitlines() if line.strip()]
    if not lines:
        return False
    return not _is_heartbeat_only_block(lines)


def build_import_block(filename: str, content: str) -> str:
    marker = import_marker(filename, content)
    body = sanitize_content(content)
    return "\n".join(
        [
            marker,
            f"## Imported Session Summary: {filename}",
            "",
            body,
            "",
        ]
    )


def append_import(target: Path, *, date: str, filename: str, content: str) -> bool:
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    marker = import_marker(filename, content)
    if marker in existing:
        return False
    body = sanitize_content(content)
    if not body:
        return False
    if not existing:
        existing = canonical_header(date) + "\n"
    elif not existing.endswith("\n"):
        existing += "\n"
    updated = existing + "\n".join(
        [
            marker,
            f"## Imported Session Summary: {filename}",
            "",
            body,
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(updated, encoding="utf-8")
    return True


def archive_source(source: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / source.name
    if dest.exists():
        if dest.read_text(encoding="utf-8") == source.read_text(encoding="utf-8"):
            source.unlink()
            return dest
        stem = source.stem
        suffix = source.suffix
        counter = 2
        while True:
            candidate = archive_dir / f"{stem}.{counter}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
            counter += 1
    shutil.move(str(source), str(dest))
    return dest


def archive_root_for(memory_dir: Path) -> Path:
    repo = memory_dir.parent
    return repo / "tasks" / "WORK" / "artifacts" / "session-memory-archive"


def parse_import_blocks(text: str) -> list[dict[str, str]]:
    matches = list(IMPORT_MARKER_RE.finditer(text))
    blocks: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[body_start:body_end].lstrip("\n")
        header = f"## Imported Session Summary: {match.group('filename')}"
        if block.startswith(header):
            block = block[len(header) :].lstrip("\n")
        blocks.append(
            {
                "filename": match.group("filename"),
                "digest": match.group("digest"),
                "body": block.rstrip(),
            }
        )
    return blocks


def rebuild_canonical_daily(date: str, blocks: list[dict[str, str]]) -> str:
    parts = [canonical_header(date).rstrip(), ""]
    for block in blocks:
        body = sanitize_content(block["body"])
        if not body:
            continue
        marker = f"{IMPORT_MARKER_PREFIX} {block['filename']} sha256={block['digest']} -->"
        parts.extend(
            [
                marker,
                f"## Imported Session Summary: {block['filename']}",
                "",
                body,
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def rewrite_existing_daily_files(memory_dir: Path) -> dict[str, Any]:
    rewritten = 0
    unchanged = 0
    rewritten_paths: list[str] = []
    if not memory_dir.is_dir():
        return {"rewritten": 0, "unchanged": 0, "paths": []}
    for target in sorted(memory_dir.glob("*.md")):
        if not CANONICAL_DAILY_RE.match(target.name):
            continue
        existing = target.read_text(encoding="utf-8")
        blocks = parse_import_blocks(existing)
        if not blocks:
            unchanged += 1
            continue
        updated = rebuild_canonical_daily(target.stem, blocks)
        if updated == existing:
            unchanged += 1
            continue
        target.write_text(updated, encoding="utf-8")
        rewritten += 1
        rewritten_paths.append(str(target))
    return {"rewritten": rewritten, "unchanged": unchanged, "paths": rewritten_paths}


def plan_consolidation(memory_dir: Path) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    if not memory_dir.is_dir():
        return plans
    archive_root = archive_root_for(memory_dir)
    for source in sorted(memory_dir.glob("*.md")):
        name = source.name
        if CANONICAL_DAILY_RE.match(name):
            continue
        match = SLUGGED_SESSION_MEMORY_RE.match(name)
        if not match:
            continue
        date = match.group("date")
        content = source.read_text(encoding="utf-8")
        target = memory_dir / f"{date}.md"
        marker = import_marker(name, content)
        target_text = target.read_text(encoding="utf-8") if target.exists() else ""
        importable = should_import_content(content)
        plans.append(
            {
                "date": date,
                "source": str(source),
                "target": str(target),
                "archive": str(archive_root / date / name),
                "alreadyImported": marker in target_text,
                "importable": importable,
            }
        )
    return plans


def apply_consolidation(memory_dir: Path) -> dict[str, Any]:
    plans = plan_consolidation(memory_dir)
    archive_root = archive_root_for(memory_dir)
    merged = 0
    archived = 0
    skipped = 0
    archive_paths: list[str] = []
    for item in plans:
        source = Path(item["source"])
        target = Path(item["target"])
        content = source.read_text(encoding="utf-8")
        imported = False
        if item.get("importable", True):
            imported = append_import(
                target,
                date=str(item["date"]),
                filename=source.name,
                content=content,
            )
        if imported:
            merged += 1
        else:
            skipped += 1
        archived_path = archive_source(source, archive_root / str(item["date"]))
        archive_paths.append(str(archived_path))
        archived += 1
    return {
        "planned": len(plans),
        "merged": merged,
        "archived": archived,
        "skipped": skipped,
        "archivePaths": archive_paths,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Consolidate slugged session-memory notes into canonical daily memory files.")
    ap.add_argument("--repo-root", help="Workspace root. Defaults to repo root from this script.")
    ap.add_argument("--memory-dir", help="Override memory directory. Defaults to <repo-root>/memory.")
    ap.add_argument("--apply", action="store_true", help="Apply consolidation and archive the source files.")
    ap.add_argument(
        "--rewrite-existing",
        action="store_true",
        help="Rewrite existing canonical daily files with sanitized imported content.",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    memory_dir = Path(args.memory_dir).expanduser().resolve() if args.memory_dir else root / "memory"
    planned = plan_consolidation(memory_dir)
    payload: dict[str, Any] = {
        "memoryDir": str(memory_dir),
        "planned": len(planned),
        "candidates": planned,
        "applied": False,
    }
    if args.apply:
        payload["applied"] = True
        payload["result"] = apply_consolidation(memory_dir)
    if args.rewrite_existing:
        payload["rewriteExisting"] = rewrite_existing_daily_files(memory_dir)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            "SESSION_MEMORY_CONSOLIDATION "
            f"planned={payload['planned']} applied={int(bool(payload['applied']))} memory_dir={memory_dir}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
