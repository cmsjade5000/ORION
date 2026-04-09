#!/usr/bin/env python3
"""Build a repo-first ORION judgment layer verdict from existing incident bundle signals."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aegis_incident_score import score_signals


DEFAULT_POLICY_PATH = Path("ops/judgment-policy.v1.json")
DEFAULT_LATEST_JSON = Path("tmp/orion_judgment_latest.json")
DEFAULT_LATEST_MD = Path("tasks/NOTES/orion-judgment.md")
DEFAULT_HISTORY_DIR = Path("eval/history")


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


def load_policy(root: Path, policy_path: str | None) -> dict[str, Any]:
    path = Path(policy_path).expanduser().resolve() if policy_path else (root / DEFAULT_POLICY_PATH)
    return json.loads(path.read_text(encoding="utf-8"))


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


def apply_policy(score: dict[str, Any], policy: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    mapping = policy.get("severity_to_recommendation") or {}
    recommendation = str(mapping.get(score["severity"], score.get("recommendation") or "log-only"))
    should_notify = recommendation == "alert"
    if previous:
        prev_score = previous.get("score") if isinstance(previous.get("score"), dict) else {}
        same_reco = prev_score.get("recommendation") == recommendation
        same_severity = prev_score.get("severity") == score["severity"]
        prev_value = int(prev_score.get("score_value") or 0)
        curr_value = int(score.get("score_value") or 0)
        if same_reco and same_severity and curr_value <= prev_value:
            should_notify = False
    return {
        "recommendation": recommendation,
        "should_notify": should_notify,
        "should_digest": recommendation == "digest" and bool((policy.get("digest_policy") or {}).get("enabled", True)),
    }


def _safe_stem(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "unknown"


def _history_paths(root: Path, verdict: dict[str, Any]) -> tuple[Path, Path]:
    generated = str(verdict.get("generated_at_utc") or "")
    stamp = generated.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")[:15]
    score = verdict.get("score") if isinstance(verdict.get("score"), dict) else {}
    severity = _safe_stem(str(score.get("severity") or "unknown"))
    recommendation = _safe_stem(str((verdict.get("delivery") or {}).get("recommendation") or score.get("recommendation") or "unknown"))
    stem = f"orion-judgment-{stamp}-{severity}-{recommendation}"
    history_dir = root / DEFAULT_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir / f"{stem}.json", history_dir / f"{stem}.md"


def _should_send_notification(*, verdict: dict[str, Any]) -> bool:
    delivery = verdict.get("delivery") if isinstance(verdict.get("delivery"), dict) else {}
    if not bool(delivery.get("should_notify")):
        return False
    recommendation = str(delivery.get("recommendation") or "")
    return recommendation == "alert"


def maybe_emit_notification(root: Path, verdict: dict[str, Any], *, verbose: bool = False) -> dict[str, Any]:
    dry_run = str(os.environ.get("ORION_JUDGMENT_NOTIFY_DRY_RUN", "")).strip().lower() in {"1", "true", "yes", "on"}
    suppress = str(os.environ.get("ORION_SUPPRESS_TELEGRAM", "")).strip().lower() in {"1", "true", "yes", "on"}
    notification = {
        "attempted": False,
        "sent": False,
        "channel": "telegram",
        "suppressed": False,
        "dry_run": dry_run,
        "reason": "not-requested",
        "command": None,
    }
    if not _should_send_notification(verdict=verdict):
        notification["reason"] = "recommendation-not-alert"
        return notification

    notification["attempted"] = True
    msg = render_summary(verdict)
    command = [
        sys.executable,
        str(root / "scripts" / "telegram_send_message.sh"),
        msg,
    ]
    notification["command"] = " ".join(command)

    if dry_run or suppress:
        notification["suppressed"] = True
        notification["reason"] = "dry-run" if dry_run else "suppressed"
        return notification

    _progress(verbose, "sending alert notification")
    proc = subprocess.run(
        command,
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode != 0:
        notification["reason"] = proc.stderr.strip() or proc.stdout.strip() or "send-failed"
        raise RuntimeError(f"judgment notification failed: {notification['reason']}")
    notification["sent"] = True
    notification["reason"] = "sent"
    return notification


def render_summary(verdict: dict[str, Any]) -> str:
    score = verdict["score"]
    lines = [
        "# ORION Judgment Layer",
        "",
        f"- Overall status: `{verdict['overall_status']}`",
        f"- Severity: `{score['severity']}`",
        f"- Score: `{score['score_value']}`",
        f"- Recommendation: `{score['recommendation']}`",
        f"- Should notify now: `{verdict['delivery']['should_notify']}`",
        f"- Should include in digest: `{verdict['delivery']['should_digest']}`",
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
    ap.add_argument("--policy", help="Override policy JSON path.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    try:
        bundle = load_bundle(root, args.bundle, verbose=args.verbose)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _progress(args.verbose, "loading policy")
    policy = load_policy(root, args.policy)
    _progress(args.verbose, "normalizing signals")
    normalized = normalize_signals(bundle)
    _progress(args.verbose, "scoring signals")
    score = score_signals(normalized)
    overall_status = "ok"
    if score.severity == "S1":
        overall_status = "fail"
    elif score.severity in {"S2", "S3"}:
        overall_status = "degraded"

    previous = None
    latest_json = root / DEFAULT_LATEST_JSON
    if latest_json.exists():
        try:
            previous = json.loads(latest_json.read_text(encoding="utf-8"))
        except Exception:
            previous = None
    score_dict = asdict(score)
    delivery = apply_policy(score_dict, policy, previous)
    score_dict["recommendation"] = delivery["recommendation"]

    verdict = {
        "schema_version": "orion.judgment.v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_status": overall_status,
        "score": score_dict,
        "delivery": delivery,
        "policy_path": str((Path(args.policy).expanduser().resolve() if args.policy else (root / DEFAULT_POLICY_PATH))),
        "normalized_signals": normalized,
        "source_bundle": bundle.get("artifacts", {}).get("summary_json") or bundle.get("bundle_dir"),
    }
    notification = maybe_emit_notification(root, verdict, verbose=args.verbose)
    verdict["notification"] = notification

    if args.write_latest:
        _progress(args.verbose, "writing latest judgment artifacts")
        latest_json = root / DEFAULT_LATEST_JSON
        latest_md = root / DEFAULT_LATEST_MD
        history_json, history_md = _history_paths(root, verdict)
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        latest_md.parent.mkdir(parents=True, exist_ok=True)
        latest_json.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
        latest_md.write_text(render_summary(verdict), encoding="utf-8")
        history_json.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
        history_md.write_text(render_summary(verdict), encoding="utf-8")

    _progress(args.verbose, "rendering output")
    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(render_summary(verdict), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
