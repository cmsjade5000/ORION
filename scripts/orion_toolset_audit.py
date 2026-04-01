#!/usr/bin/env python3
"""Non-destructive ORION toolset adoption audit."""

from __future__ import annotations

import argparse
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


def _run(argv: list[str], timeout: int = 30) -> CommandResult:
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
        lines = stripped.splitlines()
        for idx, line in enumerate(lines):
            trimmed = line.lstrip()
            if not trimmed.startswith(("{", "[")):
                continue
            candidate = "\n".join(lines[idx:])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        candidates: list[tuple[int, str]] = []
        for opener, closer in (("[", "]"), ("{", "}")):
            start = stripped.find(opener)
            end = stripped.rfind(closer)
            if start == -1 or end == -1 or end <= start:
                continue
            candidates.append((start, stripped[start : end + 1]))
        for _, candidate in sorted(candidates, key=lambda item: item[0]):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None


def _readme_warning_tools() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    return [
        tool_name
        for tool_name in ("apply_patch", "memory_search", "memory_get", "cron")
        if tool_name in readme
    ]


def _tool_gap_rows(
    readme_warning_tools: list[str],
    openclaw_help: str,
    plugins_json: Any,
) -> list[dict[str, str]]:
    plugin_allow = []
    if isinstance(plugins_json, dict):
        plugin_allow = list((plugins_json.get("allow") or []))

    return [
        {
            "tool": "apply_patch",
            "documented": "repo warns current runtime may not expose it",
            "available": "Codex CLI exposes `apply`; OpenClaw agent-tool availability is not directly enumerable here",
            "blocked": "reported in README warning" if "apply_patch" in readme_warning_tools else "not reported",
            "action_needed": "run one live ORION turn smoke test that requires patch application and record the result",
        },
        {
            "tool": "memory_search",
            "documented": "repo warns current runtime may not expose it",
            "available": (
                "OpenClaw memory CLI exists and memory-lancedb is enabled"
                if "memory-lancedb" in plugin_allow and "memory *" in openclaw_help
                else "insufficient local evidence"
            ),
            "blocked": "reported in README warning" if "memory_search" in readme_warning_tools else "not reported",
            "action_needed": "run one live ORION retrieval turn that explicitly uses memory search and capture evidence",
        },
        {
            "tool": "memory_get",
            "documented": "repo warns current runtime may not expose it",
            "available": (
                "OpenClaw memory CLI exists and memory-lancedb is enabled"
                if "memory-lancedb" in plugin_allow and "memory *" in openclaw_help
                else "insufficient local evidence"
            ),
            "blocked": "reported in README warning" if "memory_get" in readme_warning_tools else "not reported",
            "action_needed": "run one live ORION retrieval turn that explicitly reads memory and capture evidence",
        },
        {
            "tool": "cron",
            "documented": "repo warns current runtime may not expose the agent-level cron tool",
            "available": "OpenClaw CLI exposes `cron`; gateway scheduler surface is installed",
            "blocked": "reported in README warning" if "cron" in readme_warning_tools else "not reported",
            "action_needed": "split docs between gateway cron support and agent-tool allowlist support, then run a live ORION cron-tool smoke test",
        },
    ]


def build_report() -> dict[str, Any]:
    openclaw_version = _run(["openclaw", "--version"])
    openclaw_help = _run(["openclaw", "--help"])
    openclaw_validate = _run(["openclaw", "config", "validate", "--json"])
    openclaw_tools = _run(["openclaw", "config", "get", "tools"])
    openclaw_plugins = _run(["openclaw", "config", "get", "plugins"])
    openclaw_bindings = _run(["openclaw", "agents", "bindings", "--json"])
    openclaw_cron = _run(["openclaw", "cron", "--help"])
    openclaw_memory = _run(["openclaw", "memory", "--help"])

    codex_version = _run(["codex", "--version"])
    codex_help = _run(["codex", "--help"])
    codex_mcp_list = _run(["codex", "mcp", "list"])
    codex_mcp_server = _run(["codex", "mcp-server", "--help"])
    codex_app_server = _run(["codex", "app-server", "--help"])

    plugins_json = _safe_json(openclaw_plugins.stdout) if openclaw_plugins.ok else None
    tools_json = _safe_json(openclaw_tools.stdout) if openclaw_tools.ok else None
    bindings_json = _safe_json(openclaw_bindings.stdout) if openclaw_bindings.ok else None
    validate_json = _safe_json(openclaw_validate.stdout) if openclaw_validate.ok else None
    warning_tools = _readme_warning_tools()

    return {
        "repo_root": str(ROOT),
        "runtime": {
            "openclaw_version": openclaw_version.stdout,
            "codex_version": codex_version.stdout,
            "config_valid": validate_json,
            "tools_config": tools_json,
            "plugins_config": plugins_json,
            "bindings": bindings_json,
            "codex_mcp_servers_configured": "No MCP servers configured yet" not in codex_mcp_list.stdout,
            "docs_mcp_configured": "openaiDeveloperDocs" in codex_mcp_list.stdout,
        },
        "commands": [
            asdict(result)
            for result in (
                openclaw_version,
                openclaw_validate,
                openclaw_tools,
                openclaw_plugins,
                openclaw_bindings,
                openclaw_cron,
                openclaw_memory,
                codex_version,
                codex_help,
                codex_mcp_list,
                codex_mcp_server,
                codex_app_server,
            )
        ],
        "tool_gap_rows": _tool_gap_rows(
            readme_warning_tools=warning_tools,
            openclaw_help=openclaw_help.stdout,
            plugins_json=plugins_json,
        ),
        "adoption_recommendation": {
            "t2_worker_surface": "Docs MCP + Codex MCP",
            "t4_trace_default": "Langfuse primary; keep Opik as comparison candidate",
            "t6_product_surface": "No app-server by default; defer until Codex MCP pilot proves sustained value",
            "t8_voice_surface": "Defer voice-call until a concrete escalation or notification requirement exists",
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    runtime = report["runtime"]
    rows = report["tool_gap_rows"]
    tools_config = runtime.get("tools_config") or {}
    plugins_config = runtime.get("plugins_config") or {}
    bindings = runtime.get("bindings") or []

    lines = [
        "# ORION Toolset Audit",
        "",
        "Generated by `python3 scripts/orion_toolset_audit.py`.",
        "",
        "## Runtime Snapshot",
        "",
        f"- OpenClaw: `{runtime.get('openclaw_version') or 'unavailable'}`",
        f"- Codex: `{runtime.get('codex_version') or 'unavailable'}`",
        f"- Config valid: `{json.dumps(runtime.get('config_valid'))}`",
        f"- Tools profile: `{tools_config.get('profile', 'unknown')}`",
        f"- Docs MCP configured in Codex: `{runtime.get('docs_mcp_configured')}`",
        f"- Any Codex MCP servers configured: `{runtime.get('codex_mcp_servers_configured')}`",
        "",
        "## Current Plugin Allowlist",
        "",
        f"- Allowed plugins: `{', '.join((plugins_config.get('allow') or []))}`",
        f"- Memory slot: `{(plugins_config.get('slots') or {}).get('memory', 'unset')}`",
        f"- Agent bindings: `{json.dumps(bindings)}`",
        "",
        "## Runtime Parity Gap Table",
        "",
        "| Tool | Documented | Available | Blocked | Action needed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['tool']}` | {row['documented']} | {row['available']} | {row['blocked']} | {row['action_needed']} |"
        )

    lines.extend(
        [
            "",
            "## Adoption Defaults",
            "",
            f"- T2 worker surface: `{report['adoption_recommendation']['t2_worker_surface']}`",
            f"- T4 trace default: `{report['adoption_recommendation']['t4_trace_default']}`",
            f"- T6 product surface: `{report['adoption_recommendation']['t6_product_surface']}`",
            f"- T8 voice surface: `{report['adoption_recommendation']['t8_voice_surface']}`",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ORION toolset adoption posture.")
    parser.add_argument("--output-json", help="Write the structured audit report to this path.")
    parser.add_argument("--output-md", help="Write a markdown summary to this path.")
    args = parser.parse_args()

    report = build_report()
    payload = json.dumps(report, indent=2) + "\n"
    markdown = _render_markdown(report) + "\n"

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")

    if args.output_md:
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")

    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
