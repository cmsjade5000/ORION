#!/usr/bin/env python3
"""
Standard operator health bundle for ORION / OpenClaw.

Checks:
- gateway status
- models status (optional live probe)
- memory status
- memory rem-harness
- optional live main-agent smoke turn

The bundle is intentionally JSON-first so operators can pipe it into tooling.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Any


SMOKE_MESSAGE = "Reply with exactly: operator-health-bundle-ok"
EXPECTED_SMOKE_TEXT = "operator-health-bundle-ok"


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def extract_json_payload(proc: subprocess.CompletedProcess[str]) -> Any:
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "command failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"could not parse JSON: {exc}") from exc


def default_openclaw_cmd(root: Path) -> list[str]:
    if shutil.which("openclaw"):
        return ["openclaw"]
    wrapper = (root / "scripts" / "openclaww.sh").resolve()
    if wrapper.exists():
        return [str(wrapper)]
    return ["openclaw"]


def parse_gateway_status(payload: dict[str, Any]) -> dict[str, Any]:
    service = payload.get("service") or {}
    runtime = service.get("runtime") or {}
    rpc = payload.get("rpc") or {}
    config_audit = service.get("configAudit") or {}
    config_issues = config_audit.get("issues") or []
    loaded = bool(service.get("loaded"))
    runtime_status = str(runtime.get("status") or "").strip().lower()
    rpc_ok = rpc.get("ok")
    config_ok = config_audit.get("ok")
    ok = loaded and runtime_status == "running" and rpc_ok is True
    return {
        "ok": ok,
        "loaded": loaded,
        "runtime_status": runtime_status or "unknown",
        "rpc_ok": rpc_ok,
        "config_audit_ok": config_ok,
        "warnings": [str(issue.get("message") or "").strip() for issue in config_issues if str(issue.get("message") or "").strip()],
        "service": service,
        "rpc": rpc,
    }


def check_gateway(cmd: list[str]) -> dict[str, Any]:
    proc = run_cmd(cmd + ["gateway", "status", "--json"])
    payload = extract_json_payload(proc)
    return {
        "name": "gateway",
        "command": cmd + ["gateway", "status", "--json"],
        "returncode": proc.returncode,
        "stdout": payload,
        "stderr": proc.stderr.strip(),
        **parse_gateway_status(payload),
    }


def check_models(cmd: list[str], probe_max_tokens: int, *, allow_live_probe: bool) -> dict[str, Any]:
    argv = cmd + ["models", "status"]
    if allow_live_probe:
        argv.extend(["--probe", "--probe-max-tokens", str(probe_max_tokens)])
    argv.append("--json")
    proc = run_cmd(argv)
    payload = extract_json_payload(proc)
    auth = payload.get("auth") or {}
    probes = auth.get("probes") or {}
    results = probes.get("results") or []
    default_model = str(payload.get("defaultModel") or payload.get("resolvedDefault") or "").strip()
    selected_probe = None
    for result in results:
        model = str((result or {}).get("model") or "").strip()
        if default_model and model == default_model:
            selected_probe = result
            break
    if selected_probe is None and results:
        selected_probe = results[0]
    selected_status = (selected_probe or {}).get("status")
    ok = proc.returncode == 0 and (selected_status == "ok" if allow_live_probe else True)
    return {
        "name": "models",
        "command": argv,
        "returncode": proc.returncode,
        "stdout": payload,
        "stderr": proc.stderr.strip(),
        "ok": ok,
        "live_probe_enabled": allow_live_probe,
        "live_probe_skipped": not allow_live_probe,
        "default_model": default_model or None,
        "selected_probe": selected_probe,
        "probe_count": len(results),
    }


def check_memory(cmd: list[str], agent: str) -> dict[str, Any]:
    proc = run_cmd(cmd + ["memory", "status", "--agent", agent, "--json"])
    payload = extract_json_payload(proc)
    entry = payload[0] if isinstance(payload, list) and payload else {}
    status = entry.get("status") or {}
    audit = entry.get("audit") or {}
    ok = bool(audit.get("exists")) and int(audit.get("entryCount") or 0) > 0 and int(audit.get("invalidEntryCount") or 0) == 0
    return {
        "name": "memory",
        "command": cmd + ["memory", "status", "--agent", agent, "--json"],
        "returncode": proc.returncode,
        "stdout": payload,
        "stderr": proc.stderr.strip(),
        "ok": ok,
        "warnings": (["memory index dirty; reindex recommended"] if bool(status.get("dirty")) else [])
        + [str(issue) for issue in (audit.get("issues") or []) if str(issue).strip()],
        "audit": audit,
        "status": status,
    }


def check_rem_harness(cmd: list[str], agent: str) -> dict[str, Any]:
    proc = run_cmd(cmd + ["memory", "rem-harness", "--agent", agent, "--json"])
    payload = extract_json_payload(proc)
    rem = payload.get("rem") or {}
    deep = payload.get("deep") or {}
    source_entry_count = int(rem.get("sourceEntryCount") or 0)
    candidate_count = int(deep.get("candidateCount") or 0)
    ok = proc.returncode == 0 and source_entry_count > 0 and candidate_count > 0
    return {
        "name": "rem-harness",
        "command": cmd + ["memory", "rem-harness", "--agent", agent, "--json"],
        "returncode": proc.returncode,
        "stdout": payload,
        "stderr": proc.stderr.strip(),
        "ok": ok,
        "source_entry_count": source_entry_count,
        "candidate_count": candidate_count,
        "deep": deep,
    }


def check_smoke_turn(
    cmd: list[str],
    agent: str,
    thinking: str,
    timeout_s: int,
    message: str,
    *,
    allow_live_smoke: bool,
) -> dict[str, Any]:
    argv = cmd + [
        "agent",
        "--agent",
        agent,
        "--message",
        message,
        "--thinking",
        thinking,
        "--timeout",
        str(timeout_s),
        "--json",
    ]
    if not allow_live_smoke:
        return {
            "name": "smoke-turn",
            "command": argv,
            "returncode": 0,
            "stdout": None,
            "stderr": "",
            "ok": True,
            "skipped": True,
            "skip_reason": "live smoke disabled; pass --allow-live-smoke to run this check",
            "smoke_text": None,
            "provider": None,
            "model": None,
            "session_id": None,
        }
    proc = run_cmd(argv)
    payload = extract_json_payload(proc)
    result = ((payload.get("result") or {}).get("payloads") or [])
    smoke_text = ""
    if result:
        smoke_text = str((result[0] or {}).get("text") or "").strip()
    meta = ((payload.get("result") or {}).get("meta") or {})
    agent_meta = meta.get("agentMeta") or {}
    ok = proc.returncode == 0 and smoke_text == EXPECTED_SMOKE_TEXT
    return {
        "name": "smoke-turn",
        "command": argv,
        "returncode": proc.returncode,
        "stdout": payload,
        "stderr": proc.stderr.strip(),
        "ok": ok,
        "skipped": False,
        "smoke_text": smoke_text or None,
        "provider": agent_meta.get("provider"),
        "model": agent_meta.get("model"),
        "session_id": agent_meta.get("sessionId"),
    }


def build_report(
    *,
    repo_root: Path,
    agent: str,
    probe_max_tokens: int,
    smoke_message: str,
    smoke_thinking: str,
    smoke_timeout_s: int,
    allow_live_model_probe: bool,
    allow_live_smoke: bool,
) -> dict[str, Any]:
    cmd = default_openclaw_cmd(repo_root)
    gateway = check_gateway(cmd)
    models = check_models(cmd, probe_max_tokens, allow_live_probe=allow_live_model_probe)
    memory = check_memory(cmd, agent)
    rem_harness = check_rem_harness(cmd, agent)
    smoke = check_smoke_turn(
        cmd,
        agent,
        smoke_thinking,
        smoke_timeout_s,
        smoke_message,
        allow_live_smoke=allow_live_smoke,
    )

    checks = [gateway, models, memory, rem_harness, smoke]
    failed = [check["name"] for check in checks if not check["ok"]]
    report = {
        "repoRoot": str(repo_root),
        "agent": agent,
        "probeMaxTokens": probe_max_tokens,
        "smokeMessage": smoke_message,
        "allowLiveModelProbe": allow_live_model_probe,
        "allowLiveSmoke": allow_live_smoke,
        "checks": checks,
        "summary": {
            "overall_ok": not failed,
            "failed_checks": failed,
            "gateway_ok": gateway["ok"],
            "models_ok": models["ok"],
            "memory_ok": memory["ok"],
            "rem_harness_ok": rem_harness["ok"],
            "smoke_ok": smoke["ok"],
        },
        "next_step": "none" if not failed else "investigate-" + failed[0],
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    checks = report.get("checks") or []
    lines = [
        "# OpenClaw Operator Health Bundle",
        "",
        f"- Repo root: `{report.get('repoRoot')}`",
        f"- Agent: `{report.get('agent')}`",
        f"- Probe max tokens: `{report.get('probeMaxTokens')}`",
        f"- Live model probe: `{str(bool(report.get('allowLiveModelProbe'))).lower()}`",
        f"- Live smoke turn: `{str(bool(report.get('allowLiveSmoke'))).lower()}`",
        f"- Overall OK: `{str(bool(summary.get('overall_ok'))).lower()}`",
        f"- Failed checks: `{', '.join(summary.get('failed_checks') or []) or '-'}`",
        "",
        "## Checks",
    ]
    for check in checks:
        lines.append(f"- `{check.get('name')}`: `{ 'ok' if check.get('ok') else 'fail' }`")
        warnings = check.get("warnings") or []
        if warnings:
            lines.append(f"- `{check.get('name')}` warnings: `{'; '.join(warnings)}`")
    lines.extend(
        [
            "",
            f"## Next Step",
            f"- `{report.get('next_step')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the standard ORION operator health bundle.")
    ap.add_argument("--repo-root", help="Repo root. Defaults to the workspace root.")
    ap.add_argument("--agent", default="main", help="Agent id for memory and smoke checks (default: main).")
    ap.add_argument("--probe-max-tokens", type=int, default=16, help="Probe token budget for models status (default: 16).")
    ap.add_argument("--smoke-message", default=SMOKE_MESSAGE, help="Exact smoke-turn message to send.")
    ap.add_argument("--thinking", default="low", help="Thinking level for the live smoke turn.")
    ap.add_argument("--timeout", type=int, default=120, help="Timeout in seconds for the smoke turn.")
    ap.add_argument("--allow-live-model-probe", action="store_true", help="Run models status with a live provider probe.")
    ap.add_argument("--allow-live-smoke", action="store_true", help="Run a live main-agent smoke turn.")
    ap.add_argument("--output-json", help="Write the bundle JSON report to this path.")
    ap.add_argument("--output-md", help="Write a markdown summary to this path.")
    ap.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    report = build_report(
        repo_root=root,
        agent=args.agent,
        probe_max_tokens=args.probe_max_tokens,
        smoke_message=args.smoke_message,
        smoke_thinking=args.thinking,
        smoke_timeout_s=args.timeout,
        allow_live_model_probe=args.allow_live_model_probe,
        allow_live_smoke=args.allow_live_smoke,
    )

    if args.output_json:
        out_json = Path(args.output_json).expanduser().resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_md:
        out_md = Path(args.output_md).expanduser().resolve()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(report), encoding="utf-8")

    if args.json or not args.output_md:
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if bool((report.get("summary") or {}).get("overall_ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
