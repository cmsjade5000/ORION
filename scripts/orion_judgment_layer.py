#!/usr/bin/env python3
"""Build a repo-first ORION judgment layer verdict from existing incident bundle signals."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aegis_incident_score import score_signals


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[progress] {message}", file=sys.stderr, flush=True)


def load_bundle(root: Path, bundle_path: str | None, *, verbose: bool = False) -> dict[str, Any]:
    if bundle_path:
        _progress(verbose, f"loading existing bundle: {bundle_path}")
        return json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    _progress(verbose, "running orion_incident_bundle.py")
    latest_bundle = root / "tmp" / "orion_incident_bundle_latest.json"
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "orion_incident_bundle.py"), "--json", "--write-latest", "--verbose"],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "incident bundle failed")
    if latest_bundle.exists():
        _progress(verbose, f"loading latest bundle artifact: {latest_bundle}")
        return json.loads(latest_bundle.read_text(encoding="utf-8"))
    return json.loads(proc.stdout)


def normalize_signals(bundle: dict[str, Any]) -> dict[str, Any]:
    gateway = bundle.get("gateway") if isinstance(bundle.get("gateway"), dict) else {}
    channels = bundle.get("channels") if isinstance(bundle.get("channels"), dict) else {}
    signals = bundle.get("signals") if isinstance(bundle.get("signals"), dict) else {}
    tasks = bundle.get("tasks") if isinstance(bundle.get("tasks"), dict) else {}
    normalized = {
        "incident_id": f"ORION-JUDGMENT-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "detected_utc": bundle.get("generated_at_utc"),
        "gateway_health_ok": bool(gateway.get("health_ok", True)),
        "gateway_health_note": str(gateway.get("health_message") or "").strip(),
        "config_integrity_ok": bool(gateway.get("config_audit_ok", True)),
        "channels_degraded_count": int(channels.get("degraded") or 0),
        "approval_timeouts": int(signals.get("approval_timeouts") or 0),
        "stale_task_runs": int(signals.get("stale_task_runs") or 0),
        "discord_restart_indicators": int(signals.get("discord_stale_socket_restarts") or 0),
        "telegram_fallback_indicators": int(signals.get("telegram_ipv4_fallbacks") or 0),
        "exec_elevation_failures": int(signals.get("exec_elevation_failures") or 0),
        "codex_ready": bool(bundle.get("codex_ready", True)),
        "user_reports": False,
        "task_audit_ok": bool(tasks.get("audit_ok", True)),
        "task_list_ok": bool(tasks.get("list_ok", True)),
    }
    if not normalized["task_audit_ok"]:
        normalized["stale_task_runs"] = max(normalized["stale_task_runs"], 1)
    return normalized


def render_summary(verdict: dict[str, Any]) -> str:
    score = verdict["score"]
    lines = [
        "# ORION Judgment Layer",
        "",
        f"- Overall status: `{verdict['overall_status']}`",
        f"- Severity: `{score['severity']}`",
        f"- Score: `{score['score_value']}`",
        f"- Recommendation: `{score['recommendation']}`",
        "",
        "## Reasons",
    ]
    for reason in score["reasons"] or ["(none)"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Evidence"])
    for item in score["evidence"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Actions"])
    for item in score["recommended_actions"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Judge ORION runtime health and recommend alert/digest/log-only.")
    ap.add_argument("--repo-root", help="Override repo root.")
    ap.add_argument("--bundle", help="Existing incident bundle JSON path. If omitted, generate one.")
    ap.add_argument("--write-latest", action="store_true", help="Write latest JSON and markdown artifacts.")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    ap.add_argument("--verbose", action="store_true", help="Print progress to stderr.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    try:
        bundle = load_bundle(root, args.bundle, verbose=args.verbose)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _progress(args.verbose, "normalizing signals")
    normalized = normalize_signals(bundle)
    _progress(args.verbose, "scoring signals")
    score = score_signals(normalized)
    overall_status = "ok"
    if score.severity == "S1":
        overall_status = "fail"
    elif score.severity in {"S2", "S3"}:
        overall_status = "degraded"

    verdict = {
        "schema_version": "orion.judgment.v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_status": overall_status,
        "score": asdict(score),
        "normalized_signals": normalized,
        "source_bundle": bundle.get("artifacts", {}).get("summary_json") or bundle.get("bundle_dir"),
    }

    if args.write_latest:
        _progress(args.verbose, "writing latest judgment artifacts")
        latest_json = root / "tmp" / "orion_judgment_latest.json"
        latest_md = root / "tasks" / "NOTES" / "orion-judgment.md"
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        latest_md.parent.mkdir(parents=True, exist_ok=True)
        latest_json.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
        latest_md.write_text(render_summary(verdict), encoding="utf-8")

    _progress(args.verbose, "rendering output")
    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(render_summary(verdict), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
