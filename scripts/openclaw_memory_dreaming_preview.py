#!/usr/bin/env python3
"""Non-destructive OpenClaw memory/dreaming preview for ORION."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CommandResult:
    command: str
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    note: str = ""


def _run(argv: list[str], timeout: int = 60) -> CommandResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=" ".join(shlex.quote(part) for part in argv),
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=(proc.stdout or "").strip(),
            stderr=(proc.stderr or "").strip(),
        )
    except FileNotFoundError:
        return CommandResult(
            command=" ".join(shlex.quote(part) for part in argv),
            ok=False,
            exit_code=None,
            stdout="",
            stderr=f"command not found: {argv[0]}",
            note="missing-command",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=" ".join(shlex.quote(part) for part in argv),
            ok=False,
            exit_code=None,
            stdout=(exc.stdout or "").strip(),
            stderr=(exc.stderr or "").strip(),
            note="timeout",
        )


def _safe_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = text.strip()
        for line_idx, line in enumerate(stripped.splitlines()):
            trimmed = line.lstrip()
            if not trimmed.startswith(("{", "[")):
                continue
            candidate = "\n".join(stripped.splitlines()[line_idx:])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None


def _short_term_recall_summary(*, repo_root: Path) -> dict[str, Any]:
    recall_path = repo_root / "memory" / ".dreams" / "short-term-recall.json"
    if not recall_path.exists():
        return {
            "path": str(recall_path),
            "exists": False,
            "size_bytes": 0,
            "entry_count": 0,
        }

    try:
        raw = json.loads(recall_path.read_text(encoding="utf-8"))
    except Exception:
        raw = None

    entry_count = 0
    if isinstance(raw, list):
        entry_count = len(raw)
    elif isinstance(raw, dict):
        for key in ("entries", "items", "recalls", "records"):
            value = raw.get(key)
            if isinstance(value, list):
                entry_count = len(value)
                break

    return {
        "path": str(recall_path),
        "exists": True,
        "size_bytes": recall_path.stat().st_size,
        "entry_count": entry_count,
    }


def build_report(*, limit: int) -> dict[str, Any]:
    status = _run(["openclaw", "memory", "status", "--deep", "--json"])
    harness = _run(["openclaw", "memory", "rem-harness", "--json"])
    promote = _run(["openclaw", "memory", "promote", "--limit", str(limit)])

    status_json = _safe_json(status.stdout) if status.ok else None
    harness_json = _safe_json(harness.stdout) if harness.ok else None
    recall = _short_term_recall_summary(repo_root=ROOT)

    provider_ready = None
    if isinstance(status_json, dict):
        provider = status_json.get("provider") or status_json.get("embeddingProvider") or {}
        if isinstance(provider, dict):
            provider_ready = provider.get("ready")

    if not recall["exists"]:
        next_step = "build-recall-store"
    elif status.ok and provider_ready is False:
        next_step = "fix-memory-backend"
    elif status.ok and harness.ok:
        next_step = "review-rem-harness"
    else:
        next_step = "inspect-command-failures"

    return {
        "repo_root": str(ROOT),
        "limit": limit,
        "commands": [asdict(status), asdict(harness), asdict(promote)],
        "status": status_json,
        "rem_harness": harness_json,
        "short_term_recall": recall,
        "summary": {
            "status_ok": status.ok,
            "rem_harness_ok": harness.ok,
            "promote_preview_ok": promote.ok,
            "provider_ready": provider_ready,
            "recall_store_exists": recall["exists"],
            "recall_entry_count": recall["entry_count"],
            "recommended_next_step": next_step,
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# OpenClaw Memory Dreaming Preview",
        "",
        "Non-destructive ORION dreaming readiness preview.",
        "",
        "## Summary",
        "",
        f"- `status_ok`: `{summary['status_ok']}`",
        f"- `rem_harness_ok`: `{summary['rem_harness_ok']}`",
        f"- `promote_preview_ok`: `{summary['promote_preview_ok']}`",
        f"- `provider_ready`: `{summary['provider_ready']}`",
        f"- `recall_store_exists`: `{summary['recall_store_exists']}`",
        f"- `recall_entry_count`: `{summary['recall_entry_count']}`",
        f"- `recommended_next_step`: `{summary['recommended_next_step']}`",
        "",
        "## Commands",
        "",
    ]
    for item in report["commands"]:
        lines.extend(
            [
                f"- `{item['command']}`",
                f"  - ok: `{item['ok']}`",
                f"  - exit_code: `{item['exit_code']}`",
            ]
        )
    recall = report["short_term_recall"]
    lines.extend(
        [
            "",
            "## Recall Store",
            "",
            f"- `path`: `{recall['path']}`",
            f"- `exists`: `{recall['exists']}`",
            f"- `size_bytes`: `{recall['size_bytes']}`",
            f"- `entry_count`: `{recall['entry_count']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Preview OpenClaw dreaming readiness without writing memory.")
    ap.add_argument("--limit", type=int, default=10, help="Promotion preview limit (default: 10)")
    ap.add_argument("--output-json", help="Optional JSON output path")
    ap.add_argument("--output-md", help="Optional markdown output path")
    args = ap.parse_args()

    report = build_report(limit=max(1, args.limit))
    payload = json.dumps(report, indent=2, sort_keys=True)
    markdown = _render_markdown(report)

    if args.output_json:
        Path(args.output_json).write_text(payload + "\n", encoding="utf-8")
    if args.output_md:
        Path(args.output_md).write_text(markdown, encoding="utf-8")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
