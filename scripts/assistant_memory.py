#!/usr/bin/env python3
"""
Small local assistant-memory helper.

This is a repo-local fallback layer that complements OpenClaw memory hooks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def _memory_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return (Path(__file__).resolve().parents[1] / "memory" / "assistant_memory.jsonl").resolve()


def _normalize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]


def _load_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _append_entry(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def cmd_remember(args: argparse.Namespace) -> int:
    path = _memory_path(args.path)
    text = args.text.strip()
    if not text:
        raise SystemExit("memory text must not be empty")
    entry = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": args.kind,
        "text": text,
        "tokens": _normalize(text),
    }
    _append_entry(path, entry)
    if args.json:
        print(json.dumps({"ok": True, "path": str(path), "text": text}))
    else:
        print(f"remembered: {text}")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    path = _memory_path(args.path)
    query_tokens = set(_normalize(args.query))
    matches: list[dict] = []
    for entry in reversed(_load_entries(path)):
        tokens = set(entry.get("tokens") or [])
        score = len(query_tokens & tokens)
        if query_tokens and score == 0:
            continue
        matches.append({"score": score, **entry})
        if len(matches) >= args.limit:
            break

    if args.json:
        print(json.dumps({"matches": matches}, indent=2))
        return 0

    if not matches:
        print("No memory matches.")
        return 0

    for item in matches:
        created_at = str(item.get("created_at", "")).strip()
        text = str(item.get("text", "")).strip()
        print(f"- {text}" + (f" ({created_at})" if created_at else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repo-local assistant memory helper.")
    parser.add_argument("--path", help="Override memory jsonl path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    remember = sub.add_parser("remember", help="Persist a memory item.")
    remember.add_argument("--text", required=True, help="Memory text to store.")
    remember.add_argument("--kind", default="note", help="Memory kind label.")
    remember.add_argument("--json", action="store_true", help="Emit JSON.")
    remember.set_defaults(func=cmd_remember)

    recall = sub.add_parser("recall", help="Search stored memory items.")
    recall.add_argument("--query", required=True, help="Search query.")
    recall.add_argument("--limit", type=int, default=3, help="Maximum results to return.")
    recall.add_argument("--json", action="store_true", help="Emit JSON.")
    recall.set_defaults(func=cmd_recall)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
