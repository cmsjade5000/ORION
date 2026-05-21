#!/usr/bin/env python3
"""Read-only ORION machine status digest.

This script intentionally avoids repairs, restarts, Telegram sends, provider
probes, and LaunchAgent changes. It composes local evidence into one compact
operator-readable status object.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _run(argv: list[str], *, cwd: Path | None = None, timeout: int = 15) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _resolve_binary(name: str, warnings: list[str]) -> dict[str, Any]:
    path_result = _run(["/bin/zsh", "-lc", f"command -v {name}"])
    path = path_result["stdout"].strip().splitlines()[0] if path_result["ok"] and path_result["stdout"].strip() else None
    version = None
    version_result = _run([name, "--version"], timeout=20)
    if version_result["ok"] and version_result["stdout"].strip():
        version = version_result["stdout"].strip().splitlines()[0]
    elif path is None:
        _warn(warnings, f"{name} binary not found")
    else:
        _warn(warnings, f"{name} version check failed")
    return {"path": path, "version": version}


def _read_gateway_guard(logs_dir: Path, warnings: list[str]) -> dict[str, Any]:
    log_path = logs_dir / "orion_resurrector.log"
    if not log_path.exists():
        _warn(warnings, f"gateway guard log missing: {log_path}")
        return {
            "status": "unknown",
            "log_path": str(log_path),
            "last_classification": None,
            "last_line": None,
        }

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    last_line = next((line for line in reversed(lines) if line.strip()), None)
    last_classification = None
    for line in reversed(lines):
        match = re.search(r"classification=([a-z]+)", line)
        if match:
            last_classification = match.group(1)
            break

    status = "unknown"
    if last_classification == "healthy":
        status = "ok"
    elif last_classification == "degraded":
        status = "warn"
        _warn(warnings, "gateway guard last classified gateway as degraded")
    elif last_classification == "failed":
        status = "warn"
        _warn(warnings, "gateway guard last classified gateway as failed")
    else:
        _warn(warnings, "gateway guard log has no classification")

    return {
        "status": status,
        "log_path": str(log_path),
        "last_classification": last_classification,
        "last_line": last_line,
    }


def _read_operator_health_bundle(repo_root: Path, warnings: list[str]) -> dict[str, Any]:
    candidates = [
        repo_root / "tmp" / "openclaw_operator_health_bundle_latest.json",
        repo_root / "tmp" / "operator-health-bundle.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            _warn(warnings, f"operator health bundle unreadable: {path}: {exc}")
            return {"status": "warn", "path": str(path), "summary": None}
        status = payload.get("status")
        if status is None and isinstance(payload.get("summary"), dict):
            overall_ok = payload["summary"].get("overall_ok")
            if overall_ok is True:
                status = "ok"
            elif overall_ok is False:
                status = "warn"
        status = str(status or "unknown")
        if status not in {"ok", "healthy"}:
            _warn(warnings, f"operator health bundle status is {status}")
        return {
            "status": status,
            "path": str(path),
            "summary": {
                "gateway": payload.get("gateway"),
                "channels": payload.get("channels"),
            },
        }
    _warn(warnings, "operator health bundle not found")
    return {"status": "unknown", "path": None, "summary": None}


def _read_launchagents(launch_agents_dir: Path, warnings: list[str]) -> dict[str, Any]:
    list_result = _run(["launchctl", "list"], timeout=20)
    entries: list[dict[str, Any]] = []
    if list_result["ok"]:
        for raw in list_result["stdout"].splitlines():
            parts = raw.split(None, 2)
            if len(parts) != 3:
                continue
            pid, status, label = parts
            if "orion" not in label and "openclaw" not in label and "remodex" not in label:
                continue
            entry = {"pid": pid, "last_exit": status, "label": label}
            entries.append(entry)
            if pid == "-" and status not in {"0", "-"}:
                _warn(warnings, f"LaunchAgent {label} last exited with {status}")
    else:
        _warn(warnings, "launchctl list unavailable")

    drift: list[str] = []
    if launch_agents_dir.exists():
        for path in sorted(launch_agents_dir.glob("*.plist")):
            name = path.name
            if "orion" not in name and "openclaw" not in name:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "/Desktop/ORION" in text and "/Desktop/ORION ->" not in text:
                drift.append(str(path))
                _warn(warnings, f"LaunchAgent references Desktop/ORION: {path.name}")
    else:
        _warn(warnings, f"LaunchAgents dir missing: {launch_agents_dir}")

    return {
        "status": "warn" if drift or any(e["pid"] == "-" and e["last_exit"] not in {"0", "-"} for e in entries) else "ok",
        "entries": entries,
        "path_drift": drift,
    }


def _read_storage(storage_watch: Path | None, warnings: list[str]) -> dict[str, Any]:
    if storage_watch is None or not storage_watch.exists():
        return {"status": "unknown", "headline": None, "alerts": []}
    result = _run([str(storage_watch)], timeout=60)
    if not result["ok"]:
        _warn(warnings, "storage watcher failed")
        return {"status": "warn", "headline": None, "alerts": []}
    lines = [_strip_ansi(line).strip() for line in result["stdout"].splitlines() if line.strip()]
    alerts = [line for line in lines if "ALERT" in line or "WARN" in line]
    if alerts:
        _warn(warnings, "storage watcher reported warnings")
    return {
        "status": "warn" if alerts else "ok",
        "headline": lines[0] if lines else None,
        "alerts": alerts,
    }


def _read_remodex(warnings: list[str]) -> dict[str, Any]:
    result = _run(["remodex", "status"], timeout=20)
    if not result["ok"]:
        return {"status": "unknown", "headline": None}
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    text = "\n".join(lines).lower()
    status = "ok" if "connected" in text or "running" in text else "warn"
    if status == "warn":
        _warn(warnings, "remodex status is not clearly connected/running")
    return {"status": status, "headline": lines[0] if lines else None}


def collect_status(
    repo_root: Path,
    *,
    logs_dir: Path,
    launch_agents_dir: Path,
    storage_watch: Path | None,
) -> dict[str, Any]:
    warnings: list[str] = []
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repo_root": str(repo_root),
        "status": "ok",
        "warnings": warnings,
        "gateway_guard": _read_gateway_guard(logs_dir, warnings),
        "operator_health_bundle": _read_operator_health_bundle(repo_root, warnings),
        "launchagents": _read_launchagents(launch_agents_dir, warnings),
        "binaries": {
            "codex": _resolve_binary("codex", warnings),
            "openclaw": _resolve_binary("openclaw", warnings),
        },
        "storage": _read_storage(storage_watch, warnings),
        "remodex": _read_remodex(warnings),
    }
    payload["status"] = "warn" if warnings else "ok"
    return payload


def _print_text(payload: dict[str, Any]) -> None:
    print(f"ORION machine status: {payload['status']}")
    for warning in payload["warnings"]:
        print(f"- {warning}")
    print(f"Gateway guard: {payload['gateway_guard']['status']} ({payload['gateway_guard']['last_classification']})")
    print(f"Operator bundle: {payload['operator_health_bundle']['status']}")
    print(f"LaunchAgents: {payload['launchagents']['status']}")
    print(f"Codex: {payload['binaries']['codex']['version'] or 'unknown'}")
    print(f"OpenClaw: {payload['binaries']['openclaw']['version'] or 'unknown'}")
    print(f"Storage: {payload['storage']['status']} {payload['storage']['headline'] or ''}".rstrip())
    print(f"Remodex: {payload['remodex']['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--logs-dir", default=str(Path.home() / "Library" / "Logs"))
    parser.add_argument("--launch-agents-dir", default=str(Path.home() / "Library" / "LaunchAgents"))
    parser.add_argument("--storage-watch", default=str(Path.home() / "bin" / "storage-watch.sh"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    storage_watch = Path(args.storage_watch).expanduser() if args.storage_watch else None
    payload = collect_status(
        Path(args.repo_root).expanduser().resolve(),
        logs_dir=Path(args.logs_dir).expanduser(),
        launch_agents_dir=Path(args.launch_agents_dir).expanduser(),
        storage_watch=storage_watch,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
