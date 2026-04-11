#!/usr/bin/env python3
"""Non-destructive OpenClaw memory/dreaming preview for ORION."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
            if isinstance(value, dict):
                entry_count = len(value)
                break

    return {
        "path": str(recall_path),
        "exists": True,
        "size_bytes": recall_path.stat().st_size,
        "entry_count": entry_count,
        "updated_at": raw.get("updatedAt") if isinstance(raw, dict) else None,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _main_status_entry(status_json: Any) -> dict[str, Any] | None:
    if isinstance(status_json, list):
        for item in status_json:
            if isinstance(item, dict) and item.get("agentId") == "main":
                return item
        return None
    if isinstance(status_json, dict):
        return status_json
    return None


def _canonical_memory_summary(*, repo_root: Path) -> dict[str, Any]:
    memory_dir = repo_root / "memory"
    newest: Path | None = None
    newest_mtime = -1.0
    count = 0
    if memory_dir.is_dir():
        for path in sorted(memory_dir.glob("*.md")):
            if not path.name[:10].count("-") == 2:
                continue
            if len(path.stem) != 10:
                continue
            count += 1
            mtime = path.stat().st_mtime
            if mtime > newest_mtime:
                newest = path
                newest_mtime = mtime
    newest_dt = datetime.fromtimestamp(newest_mtime, tz=timezone.utc) if newest is not None else None
    return {
        "file_count": count,
        "newest_path": str(newest) if newest is not None else None,
        "newest_mtime": _isoformat(newest_dt),
    }


def _promotion_blockers(*, harness_json: Any) -> dict[str, Any]:
    if not isinstance(harness_json, dict):
        return {
            "candidate_count": 0,
            "top_failures": [],
            "failure_keys": [],
        }
    deep = harness_json.get("deep") or {}
    deep_config = harness_json.get("deepConfig") or {}
    candidates = deep.get("candidates") or []
    candidate_count = int(deep.get("candidateCount") or len(candidates) or 0)
    thresholds = {
        "score": float(deep_config.get("minScore") or 0),
        "recallCount": int(deep_config.get("minRecallCount") or 0),
        "uniqueQueries": int(deep_config.get("minUniqueQueries") or 0),
    }
    failures: list[str] = []
    details: list[dict[str, Any]] = []
    for candidate in candidates[:3]:
        candidate_failures: list[str] = []
        if float(candidate.get("score") or 0) < thresholds["score"]:
            candidate_failures.append(
                f"score {float(candidate.get('score') or 0):.2f} < {thresholds['score']:.2f}"
            )
            failures.append("score")
        if int(candidate.get("recallCount") or 0) < thresholds["recallCount"]:
            candidate_failures.append(
                f"recallCount {int(candidate.get('recallCount') or 0)} < {thresholds['recallCount']}"
            )
            failures.append("recallCount")
        if int(candidate.get("uniqueQueries") or 0) < thresholds["uniqueQueries"]:
            candidate_failures.append(
                f"uniqueQueries {int(candidate.get('uniqueQueries') or 0)} < {thresholds['uniqueQueries']}"
            )
            failures.append("uniqueQueries")
        if candidate_failures:
            details.append(
                {
                    "key": candidate.get("key"),
                    "path": candidate.get("path"),
                    "failures": candidate_failures,
                }
            )
    ordered_failure_keys = [key for key in ("score", "recallCount", "uniqueQueries") if key in failures]
    return {
        "candidate_count": candidate_count,
        "top_failures": details,
        "failure_keys": ordered_failure_keys,
        "thresholds": thresholds,
    }


def build_report(*, limit: int) -> dict[str, Any]:
    status = _run(["openclaw", "memory", "status", "--deep", "--json"])
    harness = _run(["openclaw", "memory", "rem-harness", "--json"])
    promote = _run(["openclaw", "memory", "promote", "--limit", str(limit)])

    status_json = _safe_json(status.stdout) if status.ok else None
    harness_json = _safe_json(harness.stdout) if harness.ok else None
    recall = _short_term_recall_summary(repo_root=ROOT)

    main_status = _main_status_entry(status_json)
    provider_ready = None
    if isinstance(main_status, dict):
        embedding_probe = main_status.get("embeddingProbe") or {}
        if isinstance(embedding_probe, dict) and "ok" in embedding_probe:
            provider_ready = embedding_probe.get("ok")
        else:
            provider = main_status.get("provider") or main_status.get("embeddingProvider") or {}
            if isinstance(provider, dict):
                provider_ready = provider.get("ready")

    canonical_memory = _canonical_memory_summary(repo_root=ROOT)
    blockers = _promotion_blockers(harness_json=harness_json)
    recall_updated_at = _parse_timestamp(recall.get("updated_at"))
    canonical_updated_at = _parse_timestamp(canonical_memory.get("newest_mtime"))
    canonical_newer_than_recall = bool(
        recall["exists"]
        and canonical_updated_at is not None
        and (recall_updated_at is None or canonical_updated_at > recall_updated_at)
    )

    if not recall["exists"]:
        next_step = "build-recall-store"
    elif status.ok and provider_ready is False:
        next_step = "fix-memory-backend"
    elif blockers["failure_keys"]:
        next_step = "improve-memory-signal"
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
        "canonical_memory": canonical_memory,
        "promotion_blockers": blockers,
        "summary": {
            "status_ok": status.ok,
            "rem_harness_ok": harness.ok,
            "promote_preview_ok": promote.ok,
            "provider_ready": provider_ready,
            "recall_store_exists": recall["exists"],
            "recall_entry_count": recall["entry_count"],
            "recall_updated_at": recall.get("updated_at"),
            "candidate_count": blockers["candidate_count"],
            "blocker_keys": blockers["failure_keys"],
            "canonical_memory_newer_than_recall": canonical_newer_than_recall,
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
        f"- `recall_updated_at`: `{summary['recall_updated_at']}`",
        f"- `candidate_count`: `{summary['candidate_count']}`",
        f"- `blocker_keys`: `{', '.join(summary['blocker_keys']) if summary['blocker_keys'] else 'none'}`",
        f"- `canonical_memory_newer_than_recall`: `{summary['canonical_memory_newer_than_recall']}`",
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
            f"- `updated_at`: `{recall.get('updated_at')}`",
        ]
    )
    canonical = report["canonical_memory"]
    blockers = report["promotion_blockers"]
    lines.extend(
        [
            "",
            "## Freshness",
            "",
            f"- `canonical_file_count`: `{canonical['file_count']}`",
            f"- `newest_canonical_path`: `{canonical['newest_path']}`",
            f"- `newest_canonical_mtime`: `{canonical['newest_mtime']}`",
            f"- `canonical_memory_newer_than_recall`: `{summary['canonical_memory_newer_than_recall']}`",
            "",
            "## Promotion Blockers",
            "",
            f"- `candidate_count`: `{blockers['candidate_count']}`",
            f"- `failure_keys`: `{', '.join(blockers['failure_keys']) if blockers['failure_keys'] else 'none'}`",
        ]
    )
    for item in blockers["top_failures"]:
        joined = "; ".join(item["failures"])
        lines.append(f"- `{item['path'] or item['key']}`: {joined}")
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
