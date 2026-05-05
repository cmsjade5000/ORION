#!/usr/bin/env python3
"""Apply and verify ORION's brokered OpenClaw file-transfer policy."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
PLUGIN_ID = "file-transfer"
DEFAULT_NODE_NAME = "Mac Mini"
MAX_BYTES = 16_777_216
FILE_NODE_COMMANDS = ["dir.list", "file.fetch", "dir.fetch", "file.write"]

BROKER_INBOUND = REPO_ROOT / "tmp" / "file-transfer-broker" / "inbound"
BROKER_OUTBOUND = REPO_ROOT / "tmp" / "file-transfer-broker" / "outbound"

ALLOW_READ_PATHS = [
    f"{BROKER_OUTBOUND}/**",
    f"{REPO_ROOT}/tasks/WORK/artifacts/**",
    f"{REPO_ROOT}/tasks/JOBS/**",
    f"{Path.home()}/.openclaw/attachments/**",
]
ALLOW_WRITE_PATHS = [
    f"{BROKER_INBOUND}/**",
]
DENY_PATHS = [
    f"{Path.home()}/.openclaw/secrets/**",
    f"{Path.home()}/.openclaw/.env*",
    f"{Path.home()}/.ssh/**",
    f"{Path.home()}/Library/Keychains/**",
    f"{Path.home()}/Library/**",
    f"{REPO_ROOT}/.git/**",
]


class BrokerError(RuntimeError):
    pass


def broker_policy() -> dict[str, Any]:
    return {
        "ask": "always",
        "allowReadPaths": ALLOW_READ_PATHS,
        "allowWritePaths": ALLOW_WRITE_PATHS,
        "denyPaths": DENY_PATHS,
        "maxBytes": MAX_BYTES,
        "followSymlinks": False,
    }


def plugin_entry(node_key: str, *, enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "config": {
            "nodes": {
                node_key: broker_policy(),
            }
        },
    }


def validate_policy(entry: dict[str, Any]) -> None:
    config = entry.get("config")
    if not isinstance(config, dict):
        raise BrokerError("missing file-transfer config")
    nodes = config.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise BrokerError("missing file-transfer config.nodes")
    if "*" in nodes:
        raise BrokerError("wildcard file-transfer node policy is not allowed")
    for node_key, policy in nodes.items():
        if not isinstance(policy, dict):
            raise BrokerError(f"node policy for {node_key!r} is not an object")
        if policy.get("ask") != "always":
            raise BrokerError(f"node policy for {node_key!r} must use ask=always")
        if policy.get("followSymlinks") is not False:
            raise BrokerError(f"node policy for {node_key!r} must set followSymlinks=false")
        if policy.get("maxBytes") != MAX_BYTES:
            raise BrokerError(f"node policy for {node_key!r} must set maxBytes={MAX_BYTES}")
        if policy.get("allowWritePaths") != ALLOW_WRITE_PATHS:
            raise BrokerError("write policy must be broker inbound staging only")
        deny_paths = policy.get("denyPaths")
        if not isinstance(deny_paths, list):
            raise BrokerError("denyPaths must be a list")
        for required in DENY_PATHS:
            if required not in deny_paths:
                raise BrokerError(f"denyPaths missing {required}")


def run_json(command: list[str]) -> Any:
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise BrokerError(
            f"{' '.join(command)} failed with exit {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BrokerError(f"{' '.join(command)} did not return JSON: {exc}") from exc


def run_checked(command: list[str]) -> str:
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise BrokerError(
            f"{' '.join(command)} failed with exit {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def list_nodes() -> list[dict[str, Any]]:
    payload = run_json(["openclaw", "nodes", "status", "--json"])
    nodes = payload.get("nodes") if isinstance(payload, dict) else None
    if not isinstance(nodes, list):
        raise BrokerError("openclaw nodes status did not include a nodes list")
    return [node for node in nodes if isinstance(node, dict)]


def resolve_node(nodes: list[dict[str, Any]], node_name: str) -> dict[str, Any]:
    matches = [
        node
        for node in nodes
        if node.get("displayName") == node_name
        and node.get("paired") is True
        and node.get("connected") is True
        and isinstance(node.get("nodeId"), str)
        and node.get("nodeId")
    ]
    if not matches:
        raise BrokerError(f"no paired and connected {node_name!r} node found")
    if len(matches) > 1:
        raise BrokerError(f"multiple paired and connected {node_name!r} nodes found")
    return matches[0]


def load_config(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BrokerError(f"config not found: {path}") from exc
    if not isinstance(payload, dict):
        raise BrokerError("OpenClaw config root must be an object")
    return payload


def write_config(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def ensure_staging_dirs() -> None:
    BROKER_INBOUND.mkdir(parents=True, exist_ok=True)
    BROKER_OUTBOUND.mkdir(parents=True, exist_ok=True)


def install_policy(config: dict[str, Any], node_id: str) -> dict[str, Any]:
    gateway = config.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        raise BrokerError("gateway config must be an object")
    nodes_cfg = gateway.setdefault("nodes", {})
    if not isinstance(nodes_cfg, dict):
        raise BrokerError("gateway.nodes config must be an object")
    allow_commands = nodes_cfg.setdefault("allowCommands", [])
    if not isinstance(allow_commands, list):
        raise BrokerError("gateway.nodes.allowCommands must be a list when present")
    for command in FILE_NODE_COMMANDS:
        if command not in allow_commands:
            allow_commands.append(command)

    plugins = config.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise BrokerError("plugins config must be an object")
    allow = plugins.setdefault("allow", [])
    if not isinstance(allow, list):
        raise BrokerError("plugins.allow must be a list when present")
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)
    entries = plugins.setdefault("entries", {})
    if not isinstance(entries, dict):
        raise BrokerError("plugins.entries must be an object")
    entry = plugin_entry(node_id, enabled=True)
    validate_policy(entry)
    entries[PLUGIN_ID] = entry
    return entry


def backup_config(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = path.parent / "backups" / "file-transfer-broker"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"openclaw.json.bak-{stamp}"
    shutil.copy2(path, backup_path)
    return backup_path


def command_render_policy(args: argparse.Namespace) -> int:
    node_key = args.node_key or DEFAULT_NODE_NAME
    entry = plugin_entry(node_key, enabled=args.enabled)
    validate_policy(entry)
    print(json.dumps(entry, indent=2))
    return 0


def command_validate_live(args: argparse.Namespace) -> int:
    node = resolve_node(list_nodes(), args.node_name)
    config = load_config(Path(args.config).expanduser())
    entry = (
        config.get("plugins", {})
        .get("entries", {})
        .get(PLUGIN_ID, plugin_entry(node["nodeId"], enabled=False))
    )
    validate_policy(entry)
    print(
        json.dumps(
            {
                "ok": True,
                "nodeId": node["nodeId"],
                "displayName": node.get("displayName"),
                "configured": PLUGIN_ID in config.get("plugins", {}).get("entries", {}),
            },
            indent=2,
        )
    )
    return 0


def command_apply_live(args: argparse.Namespace) -> int:
    if not args.yes:
        raise BrokerError("apply-live requires --yes")
    config_path = Path(args.config).expanduser()
    node = resolve_node(list_nodes(), args.node_name)
    config = load_config(config_path)
    ensure_staging_dirs()
    entry = install_policy(config, node["nodeId"])
    backup_path = backup_config(config_path)
    write_config(config_path, config)
    run_json(["openclaw", "config", "validate", "--json"])
    run_json(["openclaw", "gateway", "restart", "--wait", "10s", "--json"])
    time.sleep(5)
    status = run_json(["openclaw", "gateway", "status", "--json"])
    print(
        json.dumps(
            {
                "ok": True,
                "config": str(config_path),
                "backup": str(backup_path),
                "nodeId": node["nodeId"],
                "displayName": node.get("displayName"),
                "entry": entry,
                "gatewayRuntime": status.get("service", {}).get("runtime", {}),
                "gatewayRpc": status.get("rpc", {}),
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage ORION's brokered OpenClaw file-transfer policy.")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render-policy", help="Print the intended plugin entry JSON.")
    render.add_argument("--node-key", default=DEFAULT_NODE_NAME)
    render.add_argument("--enabled", action="store_true", help="Render enabled=true instead of the disabled template.")
    render.set_defaults(func=command_render_policy)

    validate = sub.add_parser("validate-live", help="Validate live node presence and broker policy shape.")
    validate.add_argument("--config", default=str(DEFAULT_CONFIG))
    validate.add_argument("--node-name", default=DEFAULT_NODE_NAME)
    validate.set_defaults(func=command_validate_live)

    apply = sub.add_parser("apply-live", help="Back up live config, enable broker policy, restart, and verify.")
    apply.add_argument("--config", default=str(DEFAULT_CONFIG))
    apply.add_argument("--node-name", default=DEFAULT_NODE_NAME)
    apply.add_argument("--yes", action="store_true")
    apply.set_defaults(func=command_apply_live)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
