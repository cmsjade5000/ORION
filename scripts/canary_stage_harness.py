#!/usr/bin/env python3
"""
Run a one-shot staged canary harness.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

SHELL_META_RE = re.compile(r"(\|\||&&|[|;`]|[<>]|\$\()")


def _sanitize_candidate(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return safe or "candidate"


def _resolve_output_json(repo_root: Path, output_json: str | None, candidate: str, ts: str) -> Path:
    if output_json:
        candidate_path = Path(output_json)
        if candidate_path.is_absolute():
            return candidate_path
        return repo_root / candidate_path
    safe_candidate = _sanitize_candidate(candidate)
    return repo_root / "eval" / "history" / f"canary-stage-{safe_candidate}-{ts}.json"


def _parse_command_string(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("command is empty")
    try:
        argv = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError(f"invalid quoting: {exc}") from exc
    if not argv:
        raise ValueError("command is empty")
    for part in argv:
        if SHELL_META_RE.search(part):
            raise ValueError("shell metacharacters are not allowed; pass a direct argv-style command")
    return argv


def _run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    started = dt.datetime.now(dt.timezone.utc)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ended = dt.datetime.now(dt.timezone.utc)

    display = " ".join(shlex.quote(part) for part in command)

    return {
        "cmd": display,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _load_enabled_channels(config_path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "config_path": str(config_path),
        "enabled": [],
        "configured": [],
        "source": "missing",
    }
    if not config_path.exists():
        return out

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - best effort parsing
        out["source"] = "invalid_json"
        out["error"] = str(exc)
        return out

    channels = config.get("channels")
    if not isinstance(channels, dict):
        out["source"] = "no_channels_object"
        return out

    configured = sorted(name for name, value in channels.items() if isinstance(value, dict))
    explicit_enabled = sorted(
        name for name, value in channels.items() if isinstance(value, dict) and value.get("enabled") is True
    )

    out["configured"] = configured
    if explicit_enabled:
        out["enabled"] = explicit_enabled
        out["source"] = "explicit_enabled"
    else:
        # Fallback keeps the harness usable for channel configs without explicit booleans.
        out["enabled"] = configured
        out["source"] = "configured_fallback"
    return out


def _delivery_queue_snapshot(queue_dir: Path) -> dict[str, Any]:
    if not queue_dir.exists():
        return {"queue_dir": str(queue_dir), "files": 0, "by_channel": {}, "invalid_json": 0}

    files = sorted(queue_dir.glob("*.json"))
    by_channel: Counter[str] = Counter()
    invalid_json = 0

    for path in files:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            invalid_json += 1
            continue
        channel = str(item.get("channel") or "unknown")
        by_channel[channel] += 1

    return {
        "queue_dir": str(queue_dir),
        "files": len(files),
        "by_channel": dict(sorted(by_channel.items())),
        "invalid_json": invalid_json,
    }


def _queue_delta(pre_channels: dict[str, int], post_channels: dict[str, int]) -> dict[str, int]:
    delta: dict[str, int] = {}
    for channel in sorted(set(pre_channels) | set(post_channels)):
        change = int(post_channels.get(channel, 0)) - int(pre_channels.get(channel, 0))
        if change != 0:
            delta[channel] = change
    return delta


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run staged canary harness with pre/post checks.")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--stage-cmd", required=True, help="Command for staged install/enable (shlex split; no shell operators).")
    parser.add_argument("--rollback-cmd", default=None, help="Command to rollback if stage fails (shlex split; no shell operators).")
    parser.add_argument("--skip-eval", action="store_true", default=False)
    parser.add_argument("--skip-reliability", action="store_true", default=False)
    parser.add_argument("--skip-side-effects", action="store_true", default=False)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        stage_argv = _parse_command_string(args.stage_cmd)
    except ValueError as exc:
        print(f"invalid --stage-cmd: {exc}")
        return 2

    rollback_argv: list[str] | None = None
    if args.rollback_cmd:
        try:
            rollback_argv = _parse_command_string(args.rollback_cmd)
        except ValueError as exc:
            print(f"invalid --rollback-cmd: {exc}")
            return 2

    now_utc = dt.datetime.now(dt.timezone.utc)
    ts = now_utc.strftime("%Y%m%d-%H%M%S")

    output_json = _resolve_output_json(repo_root, args.output_json, args.candidate, ts)
    canary_output_json = repo_root / "eval" / "history" / f"canary-check-{_sanitize_candidate(args.candidate)}-{ts}.json"

    config_path = Path.home() / ".openclaw" / "openclaw.json"
    queue_dir = Path.home() / ".openclaw" / "delivery-queue"

    pre_state = {
        "timestamp_utc": now_utc.isoformat(),
        "channels": _load_enabled_channels(config_path),
        "delivery_queue": _delivery_queue_snapshot(queue_dir),
    }

    steps: dict[str, dict[str, Any]] = {}
    if not args.skip_eval:
        steps["pre_eval"] = _run_command(["make", "eval-run"], repo_root)
    if not args.skip_reliability:
        steps["pre_reliability"] = _run_command(["make", "eval-reliability-daily"], repo_root)

    steps["stage"] = _run_command(stage_argv, repo_root)

    if steps["stage"]["returncode"] != 0 and rollback_argv:
        steps["rollback"] = _run_command(rollback_argv, repo_root)

    if steps["stage"]["returncode"] == 0:
        if not args.skip_eval:
            steps["post_eval"] = _run_command(["make", "eval-run"], repo_root)
        if not args.skip_reliability:
            steps["post_reliability"] = _run_command(["make", "eval-reliability-daily"], repo_root)

    steps["canary_health_check"] = _run_command(
        [
            "python3",
            "scripts/canary_health_check.py",
            "--candidate",
            args.candidate,
            "--history-dir",
            "eval/history",
            "--compare",
            "eval/latest_compare.json",
            "--output-json",
            str(canary_output_json),
        ],
        repo_root,
    )

    post_state = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "delivery_queue": _delivery_queue_snapshot(queue_dir),
    }

    side_effects: dict[str, Any] = {"skipped": bool(args.skip_side_effects)}
    unauthorized_channels: list[str] = []
    if not args.skip_side_effects:
        enabled = set(pre_state["channels"]["enabled"])
        post_by_channel = post_state["delivery_queue"]["by_channel"]
        unauthorized_channels = sorted(ch for ch in post_by_channel if ch not in enabled)
        side_effects.update(
            {
                "enabled_channels": sorted(enabled),
                "unauthorized_channels": unauthorized_channels,
                "queue_growth_delta": post_state["delivery_queue"]["files"] - pre_state["delivery_queue"]["files"],
                "queue_growth_by_channel": _queue_delta(
                    pre_state["delivery_queue"]["by_channel"],
                    post_state["delivery_queue"]["by_channel"],
                ),
            }
        )

    canary_payload = _load_json(canary_output_json)
    canary_decision = str(canary_payload.get("decision", "unknown"))

    reasons: list[str] = []
    pre_eval_rc = steps.get("pre_eval", {}).get("returncode")
    if pre_eval_rc is not None and pre_eval_rc != 0:
        reasons.append(f"pre eval command failed (rc={pre_eval_rc})")

    pre_rel_rc = steps.get("pre_reliability", {}).get("returncode")
    if pre_rel_rc is not None and pre_rel_rc != 0:
        reasons.append(f"pre reliability command failed (rc={pre_rel_rc})")

    if steps["stage"]["returncode"] != 0:
        reasons.append(f"stage command failed (rc={steps['stage']['returncode']})")

    post_eval_rc = steps.get("post_eval", {}).get("returncode")
    if post_eval_rc is not None and post_eval_rc != 0:
        reasons.append(f"post eval command failed (rc={post_eval_rc})")

    post_rel_rc = steps.get("post_reliability", {}).get("returncode")
    if post_rel_rc is not None and post_rel_rc != 0:
        reasons.append(f"post reliability command failed (rc={post_rel_rc})")

    if not args.skip_side_effects and unauthorized_channels:
        reasons.append(f"unauthorized queue channels: {', '.join(unauthorized_channels)}")
    if not args.skip_side_effects and side_effects.get("queue_growth_delta", 0) > 0:
        reasons.append(f"delivery queue grew by {side_effects['queue_growth_delta']} file(s)")

    if steps["canary_health_check"]["returncode"] != 0:
        reasons.append(f"canary health check command failed (rc={steps['canary_health_check']['returncode']})")
    elif canary_decision == "hold":
        reasons.append("canary decision is hold")

    verdict = {"status": "pass" if not reasons else "fail", "reasons": reasons}

    report = {
        "kind": "canary_stage_harness",
        "timestamp_utc": now_utc.isoformat(),
        "candidate": args.candidate,
        "repo_root": str(repo_root),
        "pre_state": pre_state,
        "steps": steps,
        "post_state": post_state,
        "side_effects": side_effects,
        "canary_health_artifact": str(canary_output_json),
        "canary_health": canary_payload,
        "verdict": verdict,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("CANARY_STAGE_HARNESS")
    print(f"candidate: {args.candidate}")
    print(f"stage_rc: {steps['stage']['returncode']}")
    if post_eval_rc is None:
        print("post_eval_rc: skipped")
    else:
        print(f"post_eval_rc: {post_eval_rc}")
    if args.skip_side_effects:
        print("queue_growth_delta: skipped")
        print("unauthorized_channels: skipped")
    else:
        print(f"queue_growth_delta: {side_effects['queue_growth_delta']}")
        print(f"unauthorized_channels: {side_effects['unauthorized_channels']}")
    print(f"canary_decision: {canary_decision}")
    print(f"verdict: {verdict['status'].upper()}")
    print(f"artifact: {output_json}")
    if verdict["reasons"]:
        print("reasons:")
        for reason in verdict["reasons"]:
            print(f"- {reason}")

    return 0 if verdict["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
