#!/usr/bin/env python3
"""Thin mcporter wrapper for ORION's optional Primeta avatar layer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "mcporter.json"
DEFAULT_SERVER_REF = "primeta"


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _run(argv: list[str]) -> CommandResult:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return CommandResult(argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _selector(server_ref: str, tool_name: str) -> str:
    return f"{server_ref}.{tool_name}"


def _base_argv(config_path: Path) -> list[str]:
    return ["mcporter", "--config", str(config_path)]


def _call(config_path: Path, server_ref: str, tool_name: str, payload: dict[str, Any] | None = None) -> CommandResult:
    argv = _base_argv(config_path) + [
        "call",
        _selector(server_ref, tool_name),
        "--output",
        "json",
    ]
    if payload is not None:
        argv.extend(["--args", json.dumps(payload)])
    return _run(argv)


def _auth(config_path: Path, server_ref: str, reset: bool) -> CommandResult:
    argv = _base_argv(config_path) + ["auth", server_ref]
    if reset:
        argv.append("--reset")
    return _run(argv)


def _parse_json_output(result: CommandResult) -> Any:
    text = result.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _print_payload(command: str, payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"command": command, "payload": payload}, indent=2, sort_keys=True))
        return

    if command == "status":
        active = payload.get("active_persona") or payload.get("persona") or {}
        conversation = payload.get("conversation_url") or payload.get("url") or "n/a"
        name = active.get("name") if isinstance(active, dict) else payload.get("persona_name", "n/a")
        print(f"Primeta status: persona={name or 'n/a'} conversation={conversation}")
        return

    if command == "connect":
        print("Primeta session connected.")
        return

    if command == "send":
        print("Sent text to Primeta avatar.")
        return

    if command == "set-persona":
        print("Active Primeta persona updated.")
        return

    if command == "list-personas":
        personas = payload.get("personas") if isinstance(payload, dict) else payload
        if not personas:
            print("No Primeta personas returned.")
            return
        for item in personas:
            if isinstance(item, dict):
                print(f"{item.get('id', '?')}: {item.get('name', item.get('slug', 'unknown'))}")
            else:
                print(str(item))
        return

    if command == "hook-config":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="ORION Primeta avatar wrapper via mcporter")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to mcporter config")
    ap.add_argument(
        "--server-ref",
        default=DEFAULT_SERVER_REF,
        help="Configured mcporter server name or full MCP URL",
    )
    ap.add_argument("--json", action="store_true", help="Print JSON output")
    sub = ap.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Complete Primeta OAuth through mcporter")
    auth.add_argument("--reset", action="store_true", help="Reset cached auth first")

    sub.add_parser("status", help="Get Primeta status")

    connect = sub.add_parser("connect", help="Connect Primeta session")
    connect.add_argument("--connection-name", default="orion", help="Primeta session label")

    send = sub.add_parser("send", help="Speak text through Primeta")
    send.add_argument("--text", required=True, help="Text to send to Primeta")

    sub.add_parser("list-personas", help="List Primeta personas")

    set_persona = sub.add_parser("set-persona", help="Set active Primeta persona")
    set_persona.add_argument("--persona-id", required=True, type=int, help="Primeta persona id")

    sub.add_parser("hook-config", help="Get Primeta hook configuration")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.config).expanduser()
    server_ref = args.server_ref

    if args.command == "auth":
        result = _auth(config_path, server_ref, reset=args.reset)
        if result.ok:
            if args.json:
                print(json.dumps({"command": "auth", "ok": True, "stdout": result.stdout.strip()}, indent=2))
            else:
                print("Primeta OAuth flow started or refreshed successfully.")
            return 0
        sys.stderr.write(result.stderr or result.stdout)
        return result.returncode

    payload: dict[str, Any] | None
    tool_name: str
    if args.command == "status":
        tool_name = "primeta_get_status"
        payload = None
    elif args.command == "connect":
        tool_name = "primeta_connect"
        payload = {"connection_name": args.connection_name}
    elif args.command == "send":
        tool_name = "primeta_send"
        payload = {"text": args.text}
    elif args.command == "list-personas":
        tool_name = "primeta_list_personas"
        payload = None
    elif args.command == "set-persona":
        tool_name = "primeta_set_persona"
        payload = {"persona_id": args.persona_id}
    elif args.command == "hook-config":
        tool_name = "primeta_get_hook_config"
        payload = None
    else:
        raise AssertionError(f"unsupported command: {args.command}")

    result = _call(config_path, server_ref, tool_name, payload)
    if not result.ok:
        sys.stderr.write(result.stderr or result.stdout)
        return result.returncode

    parsed = _parse_json_output(result)
    _print_payload(args.command, parsed, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
