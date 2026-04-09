#!/usr/bin/env python3
"""Non-destructive ORION runtime baseline audit."""

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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _template_memory_defaults() -> dict[str, Any]:
    template = _load_json(ROOT / "openclaw.json.example")
    plugins = template.get("plugins", {})
    entries = plugins.get("entries", {})
    return {
        "memory_slot": (plugins.get("slots") or {}).get("memory"),
        "memory_core_enabled": bool((entries.get("memory-core") or {}).get("enabled")),
        "dreaming_enabled": bool((((entries.get("memory-core") or {}).get("config") or {}).get("dreaming") or {}).get("enabled")),
        "dreaming_frequency": ((((entries.get("memory-core") or {}).get("config") or {}).get("dreaming") or {}).get("frequency")),
    }


def _runtime_rows(plugins_config: Any, plugins_inventory: Any, skills_list: str) -> list[dict[str, str]]:
    plugin_allow = list((plugins_config or {}).get("allow") or [])
    memory_slot = ((plugins_config or {}).get("slots") or {}).get("memory", "unset")
    entries = (plugins_config or {}).get("entries") or {}
    dreaming_enabled = bool((((entries.get("memory-core") or {}).get("config") or {}).get("dreaming") or {}).get("enabled"))

    inventory_by_id = {}
    if isinstance(plugins_inventory, dict):
        for item in plugins_inventory.get("plugins", []):
            if isinstance(item, dict) and item.get("id"):
                inventory_by_id[item["id"]] = item

    def runtime_status(plugin_id: str) -> str:
        item = inventory_by_id.get(plugin_id) or {}
        status = item.get("status", "unknown")
        reason = item.get("activationReason")
        if reason:
            return f"{status} ({reason})"
        return status

    clawhub_ready = "clawhub" in skills_list.lower()
    return [
        {
            "area": "OpenClaw runtime",
            "documented": "repo history still references the 2026.3.13 upgrade tranche",
            "runtime_actual": "OpenClaw 2026.4.5",
            "recommended": "treat 2026.4.5 as the current baseline and keep 2026.3.13 docs as historical context",
        },
        {
            "area": "Memory slot",
            "documented": "checked-in templates default to memory-lancedb",
            "runtime_actual": memory_slot,
            "recommended": "document template-vs-runtime split explicitly; do not silently rewrite the template default",
        },
        {
            "area": "Dreaming",
            "documented": "repo templates keep dreaming disabled",
            "runtime_actual": "enabled" if dreaming_enabled else "disabled",
            "recommended": "keep pilot framing; do not imply dreaming is trusted durable memory",
        },
        {
            "area": "ClawHub skill workflow",
            "documented": "March docs treat ClawHub as intake/pilot territory",
            "runtime_actual": "available via openclaw skills list" if clawhub_ready else "not proven",
            "recommended": "adopt as the standard skill discovery/update workflow with repo curation",
        },
        {
            "area": "ACPX",
            "documented": "not part of checked-in workflow",
            "runtime_actual": runtime_status("acpx"),
            "recommended": "pilot candidate only; do not promote to default async orchestration",
        },
        {
            "area": "Browser plugin",
            "documented": "current posture relies on managed-browser/operator-pack guidance",
            "runtime_actual": runtime_status("browser"),
            "recommended": "defer unless it materially improves over current managed-browser flows",
        },
        {
            "area": "Firecrawl plugin",
            "documented": "March docs list it as a candidate",
            "runtime_actual": runtime_status("firecrawl"),
            "recommended": "strongest retrieval pilot candidate for WIRE",
        },
        {
            "area": "OpenProse",
            "documented": "enabled and available",
            "runtime_actual": runtime_status("open-prose"),
            "recommended": "keep as optional workflow formalization, not the durable default async primitive",
        },
        {
            "area": "Task Packet vs sessions_yield",
            "documented": "some orchestration docs still mention sessions_yield preference",
            "runtime_actual": "repo follow-through model remains packet-backed reconciliation",
            "recommended": "keep Task Packets as the durable async default",
        },
        {
            "area": "Channels/plugins",
            "documented": "template allowlist is conservative",
            "runtime_actual": ", ".join(plugin_allow),
            "recommended": "document live allowlist separately from checked-in templates",
        },
    ]


def build_report() -> dict[str, Any]:
    openclaw_version = _run(["openclaw", "--version"])
    openclaw_validate = _run(["openclaw", "config", "validate", "--json"])
    openclaw_plugins = _run(["openclaw", "config", "get", "plugins"])
    openclaw_plugins_list = _run(["openclaw", "plugins", "list", "--json"], timeout=60)
    openclaw_skills_list = _run(["openclaw", "skills", "list"], timeout=60)
    openclaw_bindings = _run(["openclaw", "agents", "bindings", "--json"])
    openclaw_agents = _run(["openclaw", "config", "get", "agents"])

    codex_version = _run(["codex", "--version"])
    codex_mcp_list = _run(["codex", "mcp", "list"])

    plugins_json = _safe_json(openclaw_plugins.stdout) if openclaw_plugins.ok else None
    plugins_inventory_json = _safe_json(openclaw_plugins_list.stdout) if openclaw_plugins_list.ok else None
    bindings_json = _safe_json(openclaw_bindings.stdout) if openclaw_bindings.ok else None
    validate_json = _safe_json(openclaw_validate.stdout) if openclaw_validate.ok else None
    agents_json = _safe_json(openclaw_agents.stdout) if openclaw_agents.ok else None
    template_defaults = _template_memory_defaults()

    return {
        "repo_root": str(ROOT),
        "runtime": {
            "openclaw_version": openclaw_version.stdout,
            "codex_version": codex_version.stdout,
            "config_valid": validate_json,
            "plugins_config": plugins_json,
            "plugins_inventory": plugins_inventory_json,
            "agents_config": agents_json,
            "bindings": bindings_json,
            "clawhub_available": "clawhub" in openclaw_skills_list.stdout.lower(),
            "codex_mcp_servers_configured": "No MCP servers configured yet" not in codex_mcp_list.stdout,
            "docs_mcp_configured": "openaiDeveloperDocs" in codex_mcp_list.stdout,
        },
        "template_defaults": template_defaults,
        "commands": [
            asdict(result)
            for result in (
                openclaw_version,
                openclaw_validate,
                openclaw_plugins,
                openclaw_plugins_list,
                openclaw_skills_list,
                openclaw_bindings,
                openclaw_agents,
                codex_version,
                codex_mcp_list,
            )
        ],
        "baseline_rows": _runtime_rows(
            plugins_config=plugins_json,
            plugins_inventory=plugins_inventory_json,
            skills_list=openclaw_skills_list.stdout,
        ),
        "pilot_recommendations": {
            "clawhub": "adopt for workflow",
            "firecrawl": "pilot next",
            "acpx": "pilot next",
            "browser": "defer",
            "github_structured_workflow": "pilot next",
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    runtime = report["runtime"]
    rows = report["baseline_rows"]
    plugins_config = runtime.get("plugins_config") or {}
    bindings = runtime.get("bindings") or []
    template_defaults = report.get("template_defaults") or {}

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
        f"- Live memory slot: `{(plugins_config.get('slots') or {}).get('memory', 'unknown')}`",
        f"- Template memory slot: `{template_defaults.get('memory_slot', 'unknown')}`",
        f"- Live ClawHub availability: `{runtime.get('clawhub_available')}`",
        f"- Docs MCP configured in Codex: `{runtime.get('docs_mcp_configured')}`",
        f"- Any Codex MCP servers configured: `{runtime.get('codex_mcp_servers_configured')}`",
        "",
        "## Live Plugin Allowlist",
        "",
        f"- Allowed plugins: `{', '.join((plugins_config.get('allow') or []))}`",
        f"- Agent bindings: `{json.dumps(bindings)}`",
        "",
        "## Baseline Matrix",
        "",
        "| Area | Documented | Runtime actual | Recommended |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['area']}` | {row['documented']} | {row['runtime_actual']} | {row['recommended']} |"
        )

    lines.extend(
        [
            "",
            "## Pilot Recommendations",
            "",
            f"- ClawHub workflow: `{report['pilot_recommendations']['clawhub']}`",
            f"- Firecrawl: `{report['pilot_recommendations']['firecrawl']}`",
            f"- ACPX: `{report['pilot_recommendations']['acpx']}`",
            f"- Browser plugin: `{report['pilot_recommendations']['browser']}`",
            f"- GitHub structured workflow: `{report['pilot_recommendations']['github_structured_workflow']}`",
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
