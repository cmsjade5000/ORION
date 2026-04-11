#!/usr/bin/env python3
"""
Bounded runtime reconciliation for ORION/OpenClaw background execution integrity.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def state_path(root: Path, override: str | None) -> Path:
    if override:
        return (root / override).resolve()
    return (root / "tmp" / "runtime_reconcile_state.json").resolve()


def report_path(root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (root / "tasks" / "NOTES" / "runtime-reconcile.md").resolve()


def _safe_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        stripped = (text or "").strip()
        if not stripped:
            return None
        for opener, closer in (("{", "}"), ("[", "]")):
            start = stripped.find(opener)
            end = stripped.rfind(closer)
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start : end + 1])
                except Exception:
                    continue
        return None


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str], *, cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=merged_env,
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "json": _safe_json(proc.stdout) or _safe_json(proc.stderr),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"cmd": cmd, "exit_code": 99, "stdout": "", "stderr": str(exc), "json": None}


def _task_summary(tasks_payload: Any, audit_payload: Any) -> dict[str, Any]:
    tasks = tasks_payload if isinstance(tasks_payload, list) else (tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else [])
    findings = audit_payload.get("findings", []) if isinstance(audit_payload, dict) else []
    summary = audit_payload.get("summary", {}) if isinstance(audit_payload, dict) else {}
    lost_backing_session = 0
    stale_running = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if str(task.get("status") or "") == "lost" and "backing session missing" in str(task.get("error") or "").lower():
            lost_backing_session += 1
    for finding in findings:
        if isinstance(finding, dict) and str(finding.get("code") or "") == "stale_running":
            stale_running += 1
    return {
        "lost_backing_session": lost_backing_session,
        "stale_running": stale_running,
        "inconsistent_timestamps": int((summary.get("byCode", {}) if isinstance(summary, dict) else {}).get("inconsistent_timestamps") or 0),
    }


def _discord_summary(channels_payload: Any) -> dict[str, Any]:
    channels = channels_payload.get("channels", {}) if isinstance(channels_payload, dict) else {}
    channel_accounts = channels_payload.get("channelAccounts", {}) if isinstance(channels_payload, dict) else {}
    discord = channels.get("discord", {}) if isinstance(channels, dict) else {}
    accounts = channel_accounts.get("discord", []) if isinstance(channel_accounts, dict) else []
    account = accounts[0] if isinstance(accounts, list) and accounts else {}
    reconnect_attempts = int(account.get("reconnectAttempts") or 0) if isinstance(account, dict) else 0
    last_error = str((discord.get("lastError") if isinstance(discord, dict) else "") or "").strip()
    running = bool(discord.get("running")) if isinstance(discord, dict) else False
    probe = discord.get("probe", {}) if isinstance(discord, dict) else {}
    probe_ok = bool(probe.get("ok")) if isinstance(probe, dict) else False
    return {
        "configured": bool(discord.get("configured")) if isinstance(discord, dict) else False,
        "running": running,
        "probe_ok": probe_ok,
        "last_error": last_error,
        "reconnect_attempts": reconnect_attempts,
        "needs_restart": (not running) and (
            "unknown system error -11" in last_error.lower()
            or "stale socket" in last_error.lower()
            or reconnect_attempts >= 5
        ),
    }


def _allowed(state: dict[str, Any], key: str, *, cooldown_s: int, now_ts: float) -> bool:
    last = float(state.get(key) or 0.0)
    return (now_ts - last) >= cooldown_s


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tasks = payload["tasks"]
    discord = payload["discord"]
    actions = payload["actions"]
    lines = [
        "# Runtime Reconcile",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Apply requested: `{str(payload['apply_requested']).lower()}`",
        "",
        "## Task Integrity",
        f"- lost backing session tasks: `{tasks['lost_backing_session']}`",
        f"- stale running findings: `{tasks['stale_running']}`",
        f"- inconsistent timestamps: `{tasks['inconsistent_timestamps']}`",
        "",
        "## Discord",
        f"- configured: `{str(discord['configured']).lower()}`",
        f"- running: `{str(discord['running']).lower()}`",
        f"- probe_ok: `{str(discord['probe_ok']).lower()}`",
        f"- reconnect_attempts: `{discord['reconnect_attempts']}`",
        f"- last_error: `{discord['last_error'] or '-'}`",
        f"- needs_restart: `{str(discord['needs_restart']).lower()}`",
        "",
        "## Actions",
    ]
    if actions:
        for item in actions:
            lines.append(f"- `{item['kind']}` -> exit `{item['exit_code']}`")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(root: Path, *, apply: bool, state_file: Path, report_file: Path) -> dict[str, Any]:
    now_ts = time.time()
    state = _load_state(state_file)
    baseline = {
        "tasks_list": _run(["openclaw", "tasks", "list", "--json"], cwd=root, timeout=45),
        "tasks_audit": _run(["openclaw", "tasks", "audit", "--json", "--limit", "200"], cwd=root, timeout=45),
        "channels_status": _run(["openclaw", "channels", "status", "--probe", "--json"], cwd=root, timeout=45),
    }
    tasks = _task_summary(baseline["tasks_list"]["json"], baseline["tasks_audit"]["json"])
    discord = _discord_summary(baseline["channels_status"]["json"])

    actions: list[dict[str, Any]] = []

    if (tasks["lost_backing_session"] > 0 or tasks["stale_running"] > 0) and apply and _allowed(state, "tasks_maintenance_applied_at", cooldown_s=600, now_ts=now_ts):
        result = _run(["openclaw", "tasks", "maintenance", "--apply", "--json"], cwd=root, timeout=120)
        actions.append({"kind": "tasks-maintenance", **result})
        if result["exit_code"] == 0:
            state["tasks_maintenance_applied_at"] = now_ts

    if tasks["lost_backing_session"] > 0 and apply and _allowed(state, "sessions_cleanup_applied_at", cooldown_s=1800, now_ts=now_ts):
        result = _run(
            ["openclaw", "sessions", "cleanup", "--agent", "main", "--enforce", "--fix-missing", "--json"],
            cwd=root,
            timeout=120,
        )
        actions.append({"kind": "sessions-cleanup", **result})
        if result["exit_code"] == 0:
            state["sessions_cleanup_applied_at"] = now_ts

    post_maintenance_tasks = _task_summary(
        _run(["openclaw", "tasks", "list", "--json"], cwd=root, timeout=45)["json"],
        _run(["openclaw", "tasks", "audit", "--json", "--limit", "200"], cwd=root, timeout=45)["json"],
    )
    if (
        apply
        and (
            post_maintenance_tasks["lost_backing_session"] > 0
            or post_maintenance_tasks["stale_running"] > 0
            or post_maintenance_tasks["inconsistent_timestamps"] > 0
        )
        and _allowed(state, "task_registry_repair_applied_at", cooldown_s=1800, now_ts=now_ts)
    ):
        repair = _run(
            ["python3", "scripts/task_registry_repair.py", "--repo-root", str(root), "--apply", "--json"],
            cwd=root,
            timeout=180,
        )
        actions.append({"kind": "task-registry-repair", **repair})
        if repair["exit_code"] == 0:
            state["task_registry_repair_applied_at"] = now_ts
            baseline["tasks_list"] = _run(["openclaw", "tasks", "list", "--json"], cwd=root, timeout=45)
            baseline["tasks_audit"] = _run(["openclaw", "tasks", "audit", "--json", "--limit", "200"], cwd=root, timeout=45)
            tasks = _task_summary(baseline["tasks_list"]["json"], baseline["tasks_audit"]["json"])

    if discord["needs_restart"]:
        logs = _run(["openclaw", "channels", "logs", "--channel", "discord", "--json", "--lines", "200"], cwd=root, timeout=45)
        actions.append({"kind": "discord-logs", **logs})
        if apply and _allowed(state, "gateway_restart_applied_at", cooldown_s=1800, now_ts=now_ts):
            restart = _run(["openclaw", "gateway", "restart", "--json"], cwd=root, timeout=120)
            actions.append({"kind": "gateway-restart", **restart})
            if restart["exit_code"] == 0:
                state["gateway_restart_applied_at"] = now_ts

    state["last_run_at"] = now_ts
    _save_state(state_file, state)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
        "apply_requested": apply,
        "tasks": tasks,
        "discord": discord,
        "actions": actions,
        "baseline": baseline,
        "state_path": str(state_file),
        "report_path": str(report_file),
    }
    _write_report(report_file, payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile lost/stale runtime state and bounded transport incidents.")
    ap.add_argument("--repo-root", help="Override repo root.")
    ap.add_argument("--apply", action="store_true", help="Apply safe runtime reconciliations.")
    ap.add_argument("--state-path", help="Relative or absolute state file path.")
    ap.add_argument("--report", help="Markdown report path.")
    ap.add_argument("--json", action="store_true", help="Print machine-readable payload.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    payload = run(
        root,
        apply=args.apply,
        state_file=state_path(root, args.state_path),
        report_file=report_path(root, args.report),
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("RUNTIME_RECONCILE_OK")
        print(f"report: {payload['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
