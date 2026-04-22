#!/usr/bin/env python3
"""
Run an ORION turn and enforce runtime policy gate before optional outbound delivery.

Recommended usage for enforceable delivery control:
- run the model turn on a non-delivery channel (for example `local`)
- set `--deliver-channel` so this wrapper can block/permit send after policy check
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from orion_policy_gate import evaluate_policy, load_rule_set, render_markdown
except Exception:  # pragma: no cover
    from scripts.orion_policy_gate import evaluate_policy, load_rule_set, render_markdown  # type: ignore

try:
    from outbound_text_guard import sanitize_outbound_text
except Exception:  # pragma: no cover
    from scripts.outbound_text_guard import sanitize_outbound_text  # type: ignore

try:
    from delegation_delivery_rules import is_internal_specialist_owner
except Exception:  # pragma: no cover
    from scripts.delegation_delivery_rules import is_internal_specialist_owner  # type: ignore


def _extract_response_text(run_obj: dict[str, Any]) -> str:
    payloads = (((run_obj or {}).get("result") or {}).get("payloads") or [])
    parts: list[str] = []
    for payload in payloads:
        txt = (payload or {}).get("text")
        if isinstance(txt, str) and txt.strip():
            parts.append(txt.strip())
    return sanitize_outbound_text("\n\n".join(parts).strip())


def _parse_openclaw_json_output(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("empty openclaw output")

    try:
        return json.loads(text)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except Exception:
            continue
        if text[idx + end :].strip():
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("could not locate final JSON object in openclaw output")


def _run_openclaw_agent(*, cmd: list[str], agent: str, channel: str, message: str, thinking: str, timeout_s: int, session_id: str | None) -> tuple[int, str, str]:
    normalized_channel = str(channel or "").strip().lower()
    argv = cmd + ["agent", "--agent", agent]
    if normalized_channel and normalized_channel not in {"local", "embedded", "default"}:
        argv += ["--channel", channel]
    if session_id:
        argv += ["--session-id", session_id]
    argv += [
        "--message",
        message,
        "--thinking",
        thinking,
        "--timeout",
        str(timeout_s),
        "--json",
    ]

    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if proc.returncode != 0:
        return proc.returncode, "", (proc.stderr or proc.stdout or "openclaw agent failed").strip()

    try:
        obj = _parse_openclaw_json_output(proc.stdout)
    except Exception as e:
        return 1, "", f"could not parse openclaw JSON output: {e}"

    text = _extract_response_text(obj)
    return 0, text, ""


def _dreaming_cmd_from_message(message: str) -> str | None:
    trimmed = str(message or "").strip()
    if not trimmed.lower().startswith("/dreaming"):
        return None

    parts = trimmed.split()
    action = str(parts[1] if len(parts) > 1 else "status").strip().lower()
    if action == "on":
        return "dreaming-on"
    if action == "off":
        return "dreaming-off"
    if action == "help":
        return "dreaming-help"
    return "dreaming-status"


def _run_deterministic_operator_command(*, repo_root: Path, message: str, timeout_s: int) -> tuple[bool, tuple[int, str, str]]:
    dreaming_cmd = _dreaming_cmd_from_message(message)
    if not dreaming_cmd:
        return False, (0, "", "")

    script_path = (repo_root / "scripts" / "assistant_status.py").resolve()
    if not script_path.exists():
        script_path = (Path(__file__).resolve().parent / "assistant_status.py").resolve()

    argv = [
        sys.executable,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--cmd",
        dreaming_cmd,
        "--json",
    ]
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=max(1, timeout_s))
    if proc.returncode != 0:
        return True, (proc.returncode, "", (proc.stderr or proc.stdout or "deterministic operator command failed").strip())

    try:
        obj = json.loads(proc.stdout)
    except Exception as e:
        return True, (1, "", f"could not parse deterministic command output: {e}")

    text = str(obj.get("message") or "").strip()
    if not text:
        return True, (1, "", "deterministic operator command returned no message")
    return True, (0, text, "")


def _write_policy_artifacts(*, repo_root: Path, output_dir: str, report: dict[str, Any], response_text: str) -> tuple[Path, Path]:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(response_text.encode("utf-8", errors="replace")).hexdigest()[:10]
    out_dir = (repo_root / output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"policy-gate-turn-{ts}-{digest}"

    out_json = out_dir / f"{stem}.json"
    out_md = out_dir / f"{stem}.md"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")
    return out_json, out_md


def _send_message(*, cmd: list[str], channel: str, message: str, target: str) -> tuple[int, str]:
    argv = cmd + ["message", "send", "--channel", channel, "--message", message]
    if target:
        argv += ["--target", target]

    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if proc.returncode != 0:
        return proc.returncode, (proc.stderr or proc.stdout or "openclaw message send failed").strip()
    return 0, ""


def _default_openclaw_cmd(repo_root: Path) -> list[str]:
    wrapper = (repo_root / "scripts" / "openclaww.sh").resolve()
    if wrapper.exists():
        return [str(wrapper)]
    return ["openclaw"]


def _resolve_rules_path(repo_root: Path, configured_path: str) -> Path:
    raw = Path(configured_path)
    if raw.is_absolute():
        return raw.resolve()
    primary = (repo_root / raw).resolve()
    if primary.exists():
        return primary
    return (Path(__file__).resolve().parent.parent / raw).resolve()


def main() -> int:
    env_policy_mode = os.environ.get("ORION_POLICY_MODE", "audit").strip().lower()
    if env_policy_mode not in {"audit", "block"}:
        env_policy_mode = "audit"

    ap = argparse.ArgumentParser(description="Run guarded ORION turn with policy enforcement.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--agent", default="main")
    ap.add_argument("--runtime-channel", default="local", help="OpenClaw channel used for model turn (default: local)")
    ap.add_argument("--message", required=True)
    ap.add_argument("--thinking", default="high")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--session-id", default="")
    ap.add_argument("--rules", default="config/orion_policy_rules.json")
    ap.add_argument("--policy-mode", choices=["audit", "block"], default=env_policy_mode)
    ap.add_argument("--policy-output-dir", default="eval/history")
    ap.add_argument("--deliver-channel", default="", help="Optional channel for gated outbound send (for example telegram/discord)")
    ap.add_argument("--deliver-target", default="", help="Optional target for outbound send")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    rules_path = _resolve_rules_path(repo_root, args.rules)

    try:
        rule_set = load_rule_set(rules_path)
    except Exception as e:
        print(f"ERROR: failed to load rules ({rules_path}): {e}", file=sys.stderr)
        return 2

    openclaw_cmd = _default_openclaw_cmd(repo_root)
    intercepted, result = _run_deterministic_operator_command(
        repo_root=repo_root,
        message=args.message,
        timeout_s=max(1, int(args.timeout)),
    )
    if intercepted:
        rc, response_text, err = result
    else:
        rc, response_text, err = _run_openclaw_agent(
            cmd=openclaw_cmd,
            agent=args.agent,
            channel=args.runtime_channel,
            message=args.message,
            thinking=args.thinking,
            timeout_s=max(1, int(args.timeout)),
            session_id=(args.session_id.strip() or None),
        )
    if rc != 0:
        print(f"ERROR: {err}", file=sys.stderr)
        return rc

    payload = {
        "scope": "orion_reply",
        "request_text": args.message,
        "response_text": response_text,
        "tags": ["guarded_turn"],
        "metadata": {
            "source": "openclaw_guarded_turn",
            "runtime_channel": args.runtime_channel,
            "has_specialist_result": "result:" in response_text.lower(),
            "executed_in_turn": False,
        },
    }

    report = evaluate_policy(payload=payload, rule_set=rule_set, run_mode=args.policy_mode)
    out_json, out_md = _write_policy_artifacts(
        repo_root=repo_root,
        output_dir=args.policy_output_dir,
        report=report,
        response_text=response_text,
    )

    violations = int((report.get("summary") or {}).get("violations") or 0)
    blocked = bool((report.get("summary") or {}).get("blocked"))
    if violations:
        print(
            f"POLICY_GUARD violations={violations} blocked={blocked} report={out_json}",
            file=sys.stderr,
        )

    # Print assistant output so this wrapper can be piped/read by operators.
    if response_text:
        print(response_text)

    if blocked:
        print(f"BLOCKED: outbound delivery suppressed by policy gate ({out_json})", file=sys.stderr)
        return 2

    deliver_channel = args.deliver_channel.strip().lower()
    if deliver_channel == "telegram" and is_internal_specialist_owner(args.agent):
        print(
            f"BLOCKED: {args.agent} is an internal specialist and cannot deliver directly to Telegram ({out_json})",
            file=sys.stderr,
        )
        return 2

    if args.deliver_channel.strip():
        send_rc, send_err = _send_message(
            cmd=openclaw_cmd,
            channel=args.deliver_channel.strip(),
            message=response_text,
            target=args.deliver_target.strip(),
        )
        if send_rc != 0:
            print(f"ERROR: {send_err}", file=sys.stderr)
            return send_rc
        print(f"DELIVERED: channel={args.deliver_channel.strip()} policy_report={out_md}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
