#!/usr/bin/env python3
"""
Deliberate ORION session-store maintenance.

This wraps `openclaw sessions cleanup` with thresholding and a markdown report so
cleanup runs as an explicit maintenance path instead of an opaque side effect.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def extract_json_payload(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("No JSON object found in command output")
    return json.loads(text[start : end + 1])


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def cleanup_preview(agent: str, fix_missing: bool) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    cmd = ["openclaw", "sessions", "cleanup", "--agent", agent, "--dry-run", "--json"]
    if fix_missing:
        cmd.insert(-1, "--fix-missing")
    proc = run_cmd(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "sessions cleanup preview failed")
    return extract_json_payload(proc.stdout), proc


def cleanup_apply(agent: str, fix_missing: bool) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    cmd = ["openclaw", "sessions", "cleanup", "--agent", agent, "--enforce", "--json"]
    if fix_missing:
        cmd.insert(-1, "--fix-missing")
    proc = run_cmd(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "sessions cleanup apply failed")
    return extract_json_payload(proc.stdout), proc


def maybe_doctor(enabled: bool) -> subprocess.CompletedProcess[str] | None:
    if not enabled:
        return None
    return run_cmd(["openclaw", "doctor", "--non-interactive"])


def reindex_memory(agent: str) -> subprocess.CompletedProcess[str]:
    return run_cmd(["openclaw", "memory", "index", "--agent", agent, "--force"])


def dreaming_enabled(root: Path) -> bool:
    proc = run_cmd(["openclaw", "config", "get", "plugins.entries.memory-core.config.dreaming.enabled"])
    if proc.returncode != 0:
        return False
    return (proc.stdout or "").strip().lower() == "true"


def recall_store_missing(root: Path) -> bool:
    return not (root / "memory" / ".dreams" / "short-term-recall.json").exists()


def recall_store_entry_count(root: Path) -> int:
    recall_path = root / "memory" / ".dreams" / "short-term-recall.json"
    if not recall_path.exists():
        return 0
    try:
        raw = json.loads(recall_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(raw, list):
        return len(raw)
    if not isinstance(raw, dict):
        return 0
    for key in ("entries", "items", "recalls", "records"):
        value = raw.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return 0


def recall_store_needs_seed(root: Path, *, min_entries: int = 3) -> bool:
    return recall_store_entry_count(root) < min_entries


def stage_dreaming_recall(root: Path, agent: str) -> subprocess.CompletedProcess[str]:
    return run_cmd(
        [
            "openclaw",
            "memory",
            "rem-backfill",
            "--agent",
            agent,
            "--path",
            str(root / "memory"),
            "--stage-short-term",
            "--json",
        ]
    )


def consolidate_preview(root: Path) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    script_path = Path(__file__).resolve().parent / "consolidate_session_memory.py"
    proc = run_cmd(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(root),
            "--json",
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "session memory consolidation preview failed")
    return json.loads(proc.stdout), proc


def consolidate_apply(root: Path) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    script_path = Path(__file__).resolve().parent / "consolidate_session_memory.py"
    proc = run_cmd(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(root),
            "--apply",
            "--json",
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "session memory consolidation apply failed")
    return json.loads(proc.stdout), proc


def should_apply(preview: dict[str, Any], *, min_missing: int, min_reclaim: int) -> tuple[bool, str]:
    missing = int(preview.get("missing") or 0)
    before = int(preview.get("beforeCount") or 0)
    after = int(preview.get("afterCount") or 0)
    reclaim = max(0, before - after)
    would_mutate = bool(preview.get("wouldMutate"))
    if not would_mutate:
        return False, "preview reports no mutation needed"
    if missing >= min_missing:
        return True, f"missing entries {missing} >= threshold {min_missing}"
    if reclaim >= min_reclaim:
        return True, f"reclaimable entries {reclaim} >= threshold {min_reclaim}"
    return False, (
        f"below thresholds (missing={missing} < {min_missing}, reclaim={reclaim} < {min_reclaim})"
    )


def write_report(
    path: Path,
    *,
    agent: str,
    consolidation_preview: dict[str, Any],
    consolidation_result: dict[str, Any] | None,
    preview: dict[str, Any],
    apply_requested: bool,
    apply_reason: str,
    applied: bool,
    reindex_required: bool,
    dreaming_recall_result: subprocess.CompletedProcess[str] | None,
    apply_result: dict[str, Any] | None,
    post_preview: dict[str, Any] | None,
    reindex_result: subprocess.CompletedProcess[str] | None,
    doctor_result: subprocess.CompletedProcess[str] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    missing = int(preview.get("missing") or 0)
    before = int(preview.get("beforeCount") or 0)
    after = int(preview.get("afterCount") or 0)
    reclaim = max(0, before - after)
    lines = [
        "# Session Maintenance",
        "",
        f"- Agent: `{agent}`",
        f"- Apply requested: `{str(apply_requested).lower()}`",
        f"- Applied: `{str(applied).lower()}`",
        f"- Reason: {apply_reason}",
        "",
        "## Session Memory Consolidation",
        f"- planned: `{int(consolidation_preview.get('planned') or 0)}`",
        f"- applied: `{str(bool(consolidation_result)).lower()}`",
    ]
    if consolidation_result:
        result = consolidation_result.get("result") or {}
        lines.extend(
            [
                f"- merged: `{int(result.get('merged') or 0)}`",
                f"- archived: `{int(result.get('archived') or 0)}`",
                f"- skipped: `{int(result.get('skipped') or 0)}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Memory Reindex",
            f"- required: `{str(reindex_required).lower()}`",
            f"- ran: `{str(reindex_result is not None).lower()}`",
        ]
    )
    if reindex_result is not None:
        lines.extend(
            [
                f"- exit_code: `{reindex_result.returncode}`",
                f"- ok: `{str(reindex_result.returncode == 0).lower()}`",
            ]
        )
        stdout = (reindex_result.stdout or "").strip()
        stderr = (reindex_result.stderr or "").strip()
        if stdout:
            lines.append(f"- stdout: `{stdout}`")
        if stderr:
            lines.append(f"- stderr: `{stderr}`")
    lines.extend(
        [
            "",
            "## Dreaming Recall Store",
            f"- seeded: `{str(dreaming_recall_result is not None).lower()}`",
        ]
    )
    if dreaming_recall_result is not None:
        lines.extend(
            [
                f"- exit_code: `{dreaming_recall_result.returncode}`",
                f"- ok: `{str(dreaming_recall_result.returncode == 0).lower()}`",
            ]
        )
        stdout = (dreaming_recall_result.stdout or "").strip()
        stderr = (dreaming_recall_result.stderr or "").strip()
        if stdout:
            lines.append(f"- stdout: `{stdout}`")
        if stderr:
            lines.append(f"- stderr: `{stderr}`")
    lines.extend(
        [
            "",
        "## Preview",
        f"- beforeCount: `{before}`",
        f"- afterCount: `{after}`",
        f"- missing: `{missing}`",
        f"- reclaimable: `{reclaim}`",
        f"- wouldMutate: `{str(bool(preview.get('wouldMutate'))).lower()}`",
        ]
    )
    if apply_result:
        lines.extend(
            [
                "",
                "## Apply Result",
                f"- beforeCount: `{int(apply_result.get('beforeCount') or 0)}`",
                f"- afterCount: `{int(apply_result.get('afterCount') or 0)}`",
                f"- missing: `{int(apply_result.get('missing') or 0)}`",
            ]
        )
    if post_preview:
        lines.extend(
            [
                "",
                "## Post-Run Preview",
                f"- beforeCount: `{int(post_preview.get('beforeCount') or 0)}`",
                f"- afterCount: `{int(post_preview.get('afterCount') or 0)}`",
                f"- missing: `{int(post_preview.get('missing') or 0)}`",
                f"- wouldMutate: `{str(bool(post_preview.get('wouldMutate'))).lower()}`",
            ]
        )
    if doctor_result is not None:
        lines.extend(
            [
                "",
                "## Doctor",
                f"- exit_code: `{doctor_result.returncode}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Thresholded ORION session-store maintenance.")
    ap.add_argument("--repo-root", help="Workspace root. Defaults to repo root from this script.")
    ap.add_argument("--agent", default="main", help="Agent id to maintain (default: main).")
    ap.add_argument(
        "--report",
        help="Markdown report path. Default: tasks/NOTES/session-maintenance.md under repo root.",
    )
    ap.add_argument("--fix-missing", action="store_true", help="Preview/apply missing-transcript pruning.")
    ap.add_argument("--apply", action="store_true", help="Apply cleanup when thresholds are met.")
    ap.add_argument("--doctor", action="store_true", help="Run openclaw doctor --non-interactive after apply.")
    ap.add_argument(
        "--min-missing",
        type=int,
        default=50,
        help="Minimum missing entries required before cleanup applies (default: 50).",
    )
    ap.add_argument(
        "--min-reclaim",
        type=int,
        default=25,
        help="Minimum reclaimable entries required before cleanup applies (default: 25).",
    )
    ap.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    args = ap.parse_args()

    if args.apply and os.environ.get("AUTO_OK") != "1":
        raise SystemExit("ERROR: Refusing to apply session maintenance without AUTO_OK=1")

    root = repo_root(args.repo_root)
    report_path = Path(args.report).expanduser().resolve() if args.report else root / "tasks" / "NOTES" / "session-maintenance.md"

    consolidation_preview_payload, consolidation_preview_proc = consolidate_preview(root)
    preview, preview_proc = cleanup_preview(args.agent, args.fix_missing)
    apply_allowed, apply_reason = should_apply(
        preview,
        min_missing=args.min_missing,
        min_reclaim=args.min_reclaim,
    )

    applied = False
    apply_result: dict[str, Any] | None = None
    post_preview: dict[str, Any] | None = None
    doctor_result: subprocess.CompletedProcess[str] | None = None
    consolidation_result: dict[str, Any] | None = None
    reindex_result: subprocess.CompletedProcess[str] | None = None
    dreaming_recall_result: subprocess.CompletedProcess[str] | None = None
    reindex_required = False
    maintenance_ok = True
    recall_seed_required = dreaming_enabled(root) and recall_store_needs_seed(root)

    if args.apply and apply_allowed:
        consolidation_result, _ = consolidate_apply(root)
        consolidation_apply_result = consolidation_result.get("result") or {}
        reindex_required = int(consolidation_apply_result.get("merged") or 0) > 0
        if recall_seed_required:
            dreaming_recall_result = stage_dreaming_recall(root, args.agent)
            if dreaming_recall_result.returncode != 0:
                maintenance_ok = False
            reindex_required = True
        if reindex_required:
            reindex_result = reindex_memory(args.agent)
            if reindex_result.returncode != 0:
                maintenance_ok = False
        apply_result, _ = cleanup_apply(args.agent, args.fix_missing)
        applied = True
        if args.doctor:
            doctor_result = maybe_doctor(True)
            if doctor_result is not None and doctor_result.returncode != 0:
                maintenance_ok = False
        post_preview, _ = cleanup_preview(args.agent, args.fix_missing)
    else:
        post_preview = preview

    if args.apply and recall_seed_required and dreaming_recall_result is None:
        dreaming_recall_result = stage_dreaming_recall(root, args.agent)
        if dreaming_recall_result.returncode != 0:
            maintenance_ok = False
        reindex_required = True
        reindex_result = reindex_memory(args.agent)
        if reindex_result.returncode != 0:
            maintenance_ok = False

    write_report(
        report_path,
        agent=args.agent,
        consolidation_preview=consolidation_preview_payload,
        consolidation_result=consolidation_result,
        preview=preview,
        apply_requested=args.apply,
        apply_reason=apply_reason,
        applied=applied,
        reindex_required=reindex_required,
        dreaming_recall_result=dreaming_recall_result,
        apply_result=apply_result,
        post_preview=post_preview,
        reindex_result=reindex_result,
        doctor_result=doctor_result,
    )

    payload = {
        "agent": args.agent,
        "consolidation_preview": consolidation_preview_payload,
        "consolidation_apply": consolidation_result,
        "preview": preview,
        "apply_requested": args.apply,
        "apply_allowed": apply_allowed,
        "apply_reason": apply_reason,
        "applied": applied,
        "maintenance_ok": maintenance_ok,
        "apply_result": apply_result,
        "post_preview": post_preview,
        "memory_reindex": (
            {
                "required": reindex_required,
                "ok": reindex_result.returncode == 0,
                "exit_code": reindex_result.returncode,
                "stdout": (reindex_result.stdout or "").strip(),
                "stderr": (reindex_result.stderr or "").strip(),
            }
            if reindex_result is not None
            else {
                "required": reindex_required,
                "ok": None,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
            }
        ),
        "dreaming_recall": (
            {
                "required": recall_seed_required,
                "ok": dreaming_recall_result.returncode == 0,
                "exit_code": dreaming_recall_result.returncode,
                "stdout": (dreaming_recall_result.stdout or "").strip(),
                "stderr": (dreaming_recall_result.stderr or "").strip(),
            }
            if dreaming_recall_result is not None
            else {
                "required": recall_seed_required,
                "ok": None,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
            }
        ),
        "doctor_exit_code": doctor_result.returncode if doctor_result is not None else None,
        "report_path": str(report_path.relative_to(root)),
        "consolidation_preview_stdout": consolidation_preview_proc.stdout.strip(),
        "preview_stdout": preview_proc.stdout.strip(),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"SESSION_MAINTENANCE agent={args.agent} applied={int(applied)} "
            f"reason={apply_reason} maintenance_ok={str(maintenance_ok).lower()}"
        )
        print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
