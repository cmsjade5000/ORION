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
    preview: dict[str, Any],
    apply_requested: bool,
    apply_reason: str,
    applied: bool,
    apply_result: dict[str, Any] | None,
    post_preview: dict[str, Any] | None,
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
        "## Preview",
        f"- beforeCount: `{before}`",
        f"- afterCount: `{after}`",
        f"- missing: `{missing}`",
        f"- reclaimable: `{reclaim}`",
        f"- wouldMutate: `{str(bool(preview.get('wouldMutate'))).lower()}`",
    ]
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

    if args.apply and apply_allowed:
        apply_result, _ = cleanup_apply(args.agent, args.fix_missing)
        applied = True
        if args.doctor:
            doctor_result = maybe_doctor(True)
        post_preview, _ = cleanup_preview(args.agent, args.fix_missing)
    else:
        post_preview = preview

    write_report(
        report_path,
        agent=args.agent,
        preview=preview,
        apply_requested=args.apply,
        apply_reason=apply_reason,
        applied=applied,
        apply_result=apply_result,
        post_preview=post_preview,
        doctor_result=doctor_result,
    )

    payload = {
        "agent": args.agent,
        "preview": preview,
        "apply_requested": args.apply,
        "apply_allowed": apply_allowed,
        "apply_reason": apply_reason,
        "applied": applied,
        "apply_result": apply_result,
        "post_preview": post_preview,
        "doctor_exit_code": doctor_result.returncode if doctor_result is not None else None,
        "report_path": str(report_path.relative_to(root)),
        "preview_stdout": preview_proc.stdout.strip(),
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"SESSION_MAINTENANCE agent={args.agent} applied={int(applied)} reason={apply_reason}")
        print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
