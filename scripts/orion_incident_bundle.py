#!/usr/bin/env python3
"""
Build a read-only ORION operations incident bundle for review.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


@dataclass
class CommandResult:
    name: str
    argv: list[str]
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    note: str = ""


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _artifact_name(command_name: str) -> str:
    return {
        "gateway_health": "gateway.health.txt",
        "gateway_status": "gateway.status.json",
        "channels_status": "channels.status.json",
        "doctor": "doctor.txt",
        "tasks_list": "tasks.list.json",
        "tasks_audit": "tasks.audit.json",
        "codex_version": "codex.version.txt",
    }.get(command_name, f"{command_name}.txt")


def _progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[bundle] {message}", file=sys.stderr, flush=True)


def _run(name: str, argv: list[str], *, cwd: Path, timeout: int = 45) -> CommandResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=timeout,
        )
        return CommandResult(
            name=name,
            argv=argv,
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=_trim_output((proc.stdout or "").strip()),
            stderr=_trim_output((proc.stderr or "").strip()),
        )
    except FileNotFoundError:
        return CommandResult(
            name=name,
            argv=argv,
            ok=False,
            exit_code=None,
            stdout="",
            stderr=f"command not found: {argv[0]}",
            note="missing-command",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            argv=argv,
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
        if not stripped:
            return None
        lines = stripped.splitlines()
        for idx, line in enumerate(lines):
            trimmed = line.lstrip()
            if not trimmed.startswith(("{", "[")):
                continue
            try:
                return json.loads("\n".join(lines[idx:]))
            except json.JSONDecodeError:
                pass
        for opener, closer in (("{", "}"), ("[", "]")):
            start = stripped.find(opener)
            end = stripped.rfind(closer)
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start : end + 1])
                except json.JSONDecodeError:
                    continue
        return None


def _json_payload(result: CommandResult) -> Any | None:
    return _safe_json(result.stdout) or _safe_json(result.stderr)


def _trim_output(text: str, limit: int = 20000) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    return head + "\n...[truncated]...\n" + tail


def _first_line(text: str) -> str:
    lines = text.splitlines()
    return lines[0].strip() if lines else ""


def _json_count(text: str, keys: tuple[str, ...] = ()) -> int | None:
    data = _safe_json(text)
    if isinstance(data, list):
        return len(data)
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            for nested_key in ("items", "runs", "warnings", "issues", "errors", "tasks", "findings"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return len(nested)
    count = data.get("count")
    if isinstance(count, int):
        return count
    findings = data.get("findings")
    return len(findings) if isinstance(findings, list) else None


def _result_json_count(result: CommandResult, keys: tuple[str, ...] = ()) -> int | None:
    data = _json_payload(result)
    if isinstance(data, list):
        return len(data)
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            for nested_key in ("items", "runs", "warnings", "issues", "errors", "tasks", "findings"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return len(nested)
    count = data.get("count")
    if isinstance(count, int):
        return count
    findings = data.get("findings")
    return len(findings) if isinstance(findings, list) else None


def _parse_gateway_status(text: str) -> dict[str, Any]:
    data = _safe_json(text)
    if not isinstance(data, dict):
        return {
            "parsed": False,
            "service_loaded": None,
            "runtime_status": None,
            "rpc_ok": None,
            "config_audit_ok": None,
            "overall": "unknown",
        }

    service = data.get("service") if isinstance(data.get("service"), dict) else {}
    runtime = service.get("runtime") if isinstance(service.get("runtime"), dict) else {}
    rpc = data.get("rpc") if isinstance(data.get("rpc"), dict) else {}
    config_audit = service.get("configAudit") if isinstance(service.get("configAudit"), dict) else {}

    service_loaded = bool(service.get("loaded")) if "loaded" in service else None
    runtime_status = str(runtime.get("status")).strip().lower() if runtime.get("status") is not None else None
    rpc_ok = rpc.get("ok") if isinstance(rpc.get("ok"), bool) else None
    config_audit_ok = config_audit.get("ok") if isinstance(config_audit.get("ok"), bool) else None

    overall = "ok"
    if not service_loaded or runtime_status != "running" or rpc_ok is False or config_audit_ok is False:
        overall = "degraded"

    return {
        "parsed": True,
        "service_loaded": service_loaded,
        "runtime_status": runtime_status,
        "rpc_ok": rpc_ok,
        "config_audit_ok": config_audit_ok,
        "overall": overall,
    }


def _parse_gateway_status_result(result: CommandResult) -> dict[str, Any]:
    data = _json_payload(result)
    if not isinstance(data, dict):
        return {
            "parsed": False,
            "service_loaded": None,
            "runtime_status": None,
            "rpc_ok": None,
            "config_audit_ok": None,
            "overall": "unknown",
        }

    service = data.get("service") if isinstance(data.get("service"), dict) else {}
    runtime = service.get("runtime") if isinstance(service.get("runtime"), dict) else {}
    rpc = data.get("rpc") if isinstance(data.get("rpc"), dict) else {}
    config_audit = service.get("configAudit") if isinstance(service.get("configAudit"), dict) else {}

    service_loaded = bool(service.get("loaded")) if "loaded" in service else None
    runtime_status = str(runtime.get("status")).strip().lower() if runtime.get("status") is not None else None
    rpc_ok = rpc.get("ok") if isinstance(rpc.get("ok"), bool) else None
    config_audit_ok = config_audit.get("ok") if isinstance(config_audit.get("ok"), bool) else None

    overall = "ok"
    if not service_loaded or runtime_status != "running" or rpc_ok is False or config_audit_ok is False:
        overall = "degraded"

    return {
        "parsed": True,
        "service_loaded": service_loaded,
        "runtime_status": runtime_status,
        "rpc_ok": rpc_ok,
        "config_audit_ok": config_audit_ok,
        "overall": overall,
    }


def _parse_channels_status_result(result: CommandResult) -> dict[str, Any]:
    data = _json_payload(result)
    if not isinstance(data, dict):
        return {
            "parsed": False,
            "configured": 0,
            "degraded": 0,
            "states": {},
            "alerts": [],
        }

    channels = data.get("channels") if isinstance(data.get("channels"), dict) else {}
    states: dict[str, str] = {}
    alerts: list[str] = []
    configured = 0
    degraded = 0
    for channel_id in ("telegram", "discord", "slack", "mochat"):
        channel = channels.get(channel_id, {}) if isinstance(channels, dict) else {}
        if not isinstance(channel, dict):
            continue
        if not channel.get("configured"):
            states[channel_id] = "off"
            continue
        configured += 1
        probe = channel.get("probe") if isinstance(channel.get("probe"), dict) else {}
        probe_ok = probe.get("ok") if isinstance(probe, dict) else None
        running = bool(channel.get("running"))
        last_error = str(channel.get("lastError") or "").strip()
        if running and (probe_ok is True or probe_ok is None):
            states[channel_id] = "ok"
            continue
        if last_error == "disabled":
            states[channel_id] = "disabled"
            continue
        states[channel_id] = "degraded"
        degraded += 1
        detail = last_error or str(probe.get("error") or "probe failed")
        alerts.append(f"{channel_id}: {detail}")

    return {
        "parsed": True,
        "configured": configured,
        "degraded": degraded,
        "states": states,
        "alerts": alerts[:6],
    }


def _count_matches(lines: list[str], pattern: str) -> int:
    regex = re.compile(pattern)
    return sum(1 for line in lines if regex.search(line))


def _tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def _write_command_artifacts(bundle_dir: Path, commands: list[CommandResult]) -> None:
    commands_dir = bundle_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for result in commands:
        text = [
            f"name: {result.name}",
            f"command: {' '.join(result.argv)}",
            f"ok: {str(result.ok).lower()}",
            f"exit_code: {result.exit_code}",
        ]
        if result.note:
            text.append(f"note: {result.note}")
        text.extend(
            [
                "",
                "stdout:",
                result.stdout,
                "",
                "stderr:",
                result.stderr,
                "",
            ]
        )
        (commands_dir / _artifact_name(result.name)).write_text("\n".join(text), encoding="utf-8")


def _build_summary(
    *,
    command_map: dict[str, CommandResult],
    gateway_log_tail: list[str],
    gateway_err_tail: list[str],
    bundle_dir: Path,
) -> dict[str, Any]:
    gateway_status = _parse_gateway_status_result(command_map["gateway_status"])
    channels_status = _parse_channels_status_result(command_map["channels_status"])
    tasks_list_count = _result_json_count(command_map["tasks_list"], keys=("tasks", "items", "runs"))
    tasks_audit_count = _result_json_count(command_map["tasks_audit"], keys=("warnings", "issues", "errors", "tasks"))
    tasks_audit_payload = _json_payload(command_map["tasks_audit"])
    findings = tasks_audit_payload.get("findings", []) if isinstance(tasks_audit_payload, dict) else []
    signals = {
        "discord_stale_socket_restarts": _count_matches(gateway_log_tail, r"stale-socket|auto-restart attempt"),
        "telegram_ipv4_fallbacks": _count_matches(gateway_err_tail, r"sticky IPv4-only dispatcher"),
        "approval_timeouts": _count_matches(
            gateway_log_tail + gateway_err_tail,
            r"no approval client was available|timed out waiting for authorization|approval timeout",
        ),
        "kimi_rate_limits": _count_matches(gateway_err_tail, r"rate limit reached|429 status code"),
        "stale_task_runs": sum(
            1
            for finding in findings
            if isinstance(finding, dict) and str(finding.get("code") or "") == "stale_running"
        ),
        "exec_elevation_failures": _count_matches(gateway_err_tail, r"elevated is not available right now"),
    }

    core_ok = all(
        command_map[name].ok
        for name in ("gateway_health", "gateway_status", "channels_status", "doctor", "tasks_list", "tasks_audit")
    )
    status = "ok" if core_ok and gateway_status["overall"] == "ok" and channels_status["degraded"] == 0 and not any(signals.values()) else "degraded"

    return {
        "status": status,
        "health_ok": status == "ok",
        "generated_at_et": None,
        "generated_at_utc": None,
        "gateway": {
            "health_ok": command_map["gateway_health"].ok,
            "health_message": _first_line(command_map["gateway_health"].stdout),
            "status_ok": gateway_status["overall"] == "ok",
            "status_message": _first_line(command_map["gateway_status"].stdout),
            **gateway_status,
        },
        "channels": {
            "status_ok": command_map["channels_status"].ok and channels_status["degraded"] == 0,
            **channels_status,
        },
        "tasks": {
            "list_ok": command_map["tasks_list"].ok,
            "list_count": tasks_list_count,
            "audit_ok": command_map["tasks_audit"].ok,
            "audit_count": tasks_audit_count,
            "audit_message": _first_line(command_map["tasks_audit"].stdout),
        },
        "codex_ready": command_map["codex_version"].ok,
        "signals": signals,
        "artifacts": {
            "bundle_dir": str(bundle_dir),
            "summary_json": str(bundle_dir / "summary.json"),
            "summary_md": str(bundle_dir / "summary.md"),
            "gateway_log_tail": str(bundle_dir / "gateway.log.tail.txt"),
            "gateway_err_log_tail": str(bundle_dir / "gateway.err.log.tail.txt"),
            "commands_dir": str(bundle_dir / "commands"),
            "command_outputs": {name: str(bundle_dir / "commands" / _artifact_name(name)) for name in command_map},
        },
    }


def _render_markdown(summary: dict[str, Any], commands: list[CommandResult], root: Path, bundle_dir: Path) -> str:
    gateway = summary["gateway"]
    channels = summary["channels"]
    tasks = summary["tasks"]
    signals = summary["signals"]
    lines = [
        "# ORION Incident Bundle",
        "",
        f"- Status: `{summary['status']}`",
        f"- Repo root: `{root}`",
        f"- Bundle dir: `{bundle_dir}`",
        f"- Health OK: `{summary['health_ok']}`",
        f"- Codex ready: `{summary['codex_ready']}`",
        "",
        "## Gateway",
        f"- Health message: `{gateway['health_message'] or 'n/a'}`",
        f"- Runtime status: `{gateway['runtime_status'] or 'unknown'}`",
        f"- RPC OK: `{gateway['rpc_ok']}`",
        f"- Config audit OK: `{gateway['config_audit_ok']}`",
        "",
        "## Channels",
        f"- Channel status OK: `{channels['status_ok']}`",
        f"- States: `{' | '.join(f'{key}={value}' for key, value in channels['states'].items()) if channels['states'] else 'n/a'}`",
        "",
        "## Tasks",
        f"- Task list OK: `{tasks['list_ok']}`",
        f"- Task list count: `{tasks['list_count']}`",
        f"- Task audit OK: `{tasks['audit_ok']}`",
        f"- Task audit count: `{tasks['audit_count']}`",
        "",
        "## Signals",
        f"- Discord restart indicators: `{signals['discord_stale_socket_restarts']}`",
        f"- Telegram IPv4 fallback indicators: `{signals['telegram_ipv4_fallbacks']}`",
        f"- Approval timeout indicators: `{signals['approval_timeouts']}`",
        f"- Kimi rate-limit indicators: `{signals['kimi_rate_limits']}`",
        f"- Stale task-ledger indicators: `{signals['stale_task_runs']}`",
        f"- Exec elevation failure indicators: `{signals['exec_elevation_failures']}`",
        "",
        "## Commands",
    ]
    for result in commands:
        lines.append(
            f"- `{result.name}`: `{'ok' if result.ok else 'fail'}`"
            + (f" ({result.note})" if result.note else "")
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "- `commands/*.txt|json`",
            "- `gateway.log.tail.txt`",
            "- `gateway.err.log.tail.txt`",
            "- `summary.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only ORION incident bundle.")
    parser.add_argument("--repo-root", help="Override repo root.")
    parser.add_argument("--bundle-root", help="Bundle root. Default: tmp/incidents under repo root.")
    parser.add_argument("--log-dir", help="Gateway log dir. Default: ~/.openclaw/logs")
    parser.add_argument("--tail-lines", type=int, default=120, help="How many log lines to capture.")
    parser.add_argument("--write-latest", action="store_true", help="Write latest summary artifacts in stable paths.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    parser.add_argument("--verbose", action="store_true", help="Print collector progress to stderr.")
    args = parser.parse_args()

    root = repo_root(args.repo_root)
    now = dt.datetime.now(tz=ET)
    stamp = now.strftime("%Y%m%dT%H%M%S%z")
    bundle_root = Path(args.bundle_root).expanduser().resolve() if args.bundle_root else root / "tmp" / "incidents"
    bundle_dir = bundle_root / stamp
    bundle_dir.mkdir(parents=True, exist_ok=True)

    log_dir = Path(args.log_dir).expanduser().resolve() if args.log_dir else Path.home() / ".openclaw" / "logs"
    gateway_log = log_dir / "gateway.log"
    gateway_err_log = log_dir / "gateway.err.log"

    command_specs = [
        ("gateway_health", ["openclaw", "gateway", "health"], 45),
        ("gateway_status", ["openclaw", "gateway", "status", "--json"], 45),
        ("channels_status", ["openclaw", "channels", "status", "--probe", "--json"], 45),
        ("doctor", ["openclaw", "doctor", "--non-interactive"], 90),
        ("tasks_list", ["openclaw", "tasks", "list", "--json"], 45),
        ("tasks_audit", ["openclaw", "tasks", "audit", "--json", "--limit", "200"], 45),
        ("codex_version", ["codex", "--version"], 45),
    ]
    commands = []
    for name, argv, timeout in command_specs:
        _progress(args.verbose, f"running {name}")
        commands.append(_run(name, argv, cwd=root, timeout=timeout))
    command_map = {result.name: result for result in commands}

    gateway_log_tail = _tail_lines(gateway_log, args.tail_lines)
    gateway_err_tail = _tail_lines(gateway_err_log, args.tail_lines)
    _write_command_artifacts(bundle_dir, commands)
    (bundle_dir / "gateway.log.tail.txt").write_text("\n".join(gateway_log_tail) + ("\n" if gateway_log_tail else ""), encoding="utf-8")
    (bundle_dir / "gateway.err.log.tail.txt").write_text(
        "\n".join(gateway_err_tail) + ("\n" if gateway_err_tail else ""),
        encoding="utf-8",
    )

    summary = {
        "generated_at_et": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "generated_at_utc": now.astimezone(dt.timezone.utc).isoformat(),
        "repo_root": str(root),
        "bundle_dir": str(bundle_dir),
        **_build_summary(
            command_map=command_map,
            gateway_log_tail=gateway_log_tail,
            gateway_err_tail=gateway_err_tail,
            bundle_dir=bundle_dir,
        ),
        "commands": [asdict(result) for result in commands],
    }
    (bundle_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown = _render_markdown(summary, commands, root, bundle_dir)
    (bundle_dir / "summary.md").write_text(markdown, encoding="utf-8")

    if args.write_latest:
        latest_json = root / "tmp" / "orion_incident_bundle_latest.json"
        latest_md = root / "tasks" / "NOTES" / "orion-ops-status.md"
        latest_json.parent.mkdir(parents=True, exist_ok=True)
        latest_md.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle_dir / "summary.json", latest_json)
        shutil.copyfile(bundle_dir / "summary.md", latest_md)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
