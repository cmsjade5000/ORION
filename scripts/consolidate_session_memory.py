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
from pathlib import Path
from typing import Any


SLUGGED_SESSION_MEMORY_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")
CANONICAL_DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
IMPORT_MARKER_PREFIX = "<!-- openclaw-session-memory-import:"


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def import_marker(filename: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{IMPORT_MARKER_PREFIX} {filename} sha256={digest} -->"


def canonical_header(date: str) -> str:
    return f"# Memory for {date}\n"


def build_import_block(filename: str, content: str) -> str:
    marker = import_marker(filename, content)
    body = content.rstrip()
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
    if not existing:
        existing = canonical_header(date) + "\n"
    elif not existing.endswith("\n"):
        existing += "\n"
    updated = existing + build_import_block(filename, content)
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
        plans.append(
            {
                "date": date,
                "source": str(source),
                "target": str(target),
                "archive": str(archive_root / date / name),
                "alreadyImported": marker in target_text,
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
