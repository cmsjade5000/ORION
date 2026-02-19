#!/usr/bin/env python3
"""
Mini App command relay worker.

Purpose:
- Claim queued commands from the deployed miniapp API.
- Execute them on the ORION host using local `openclaw`.
- Report completion back so the miniapp UI reflects real execution.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _coalesce(*vals: str) -> str:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _normalize_base_url(raw: str) -> str:
    s = (raw or "").strip().rstrip("/")
    if not s:
        return ""
    if s.endswith("/api/relay/claim"):
        return s[: -len("/api/relay/claim")]
    if s.endswith("/api/ingest"):
        return s[: -len("/api/ingest")]
    return s


def _derive_base_from_miniapp_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    try:
        u = urllib.parse.urlparse(s)
        if not u.scheme or not u.netloc:
            return ""
        return f"{u.scheme}://{u.netloc}"
    except Exception:
        return ""


def get_base_url() -> str:
    explicit = _coalesce(
        os.environ.get("MINIAPP_COMMAND_RELAY_URL", ""),
        os.environ.get("MINIAPP_INGEST_URL", ""),
        os.environ.get("ORION_MINIAPP_INGEST_URL", ""),
    )
    if explicit:
        return _normalize_base_url(explicit)
    return _normalize_base_url(_derive_base_from_miniapp_url(os.environ.get("ORION_MINIAPP_URL", "")))


def get_token() -> str:
    return _coalesce(
        os.environ.get("MINIAPP_COMMAND_RELAY_TOKEN", ""),
        os.environ.get("MINIAPP_INGEST_TOKEN", ""),
        os.environ.get("INGEST_TOKEN", ""),
    )


def http_post_json(url: str, token: str, body: dict[str, Any], timeout_s: float = 12.0) -> tuple[int, dict[str, Any] | None]:
    data = json.dumps(body, ensure_ascii=True).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            try:
                obj = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                obj = None
            return int(resp.status), obj if isinstance(obj, dict) else None
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        obj = None
        if raw:
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(parsed, dict):
                    obj = parsed
            except Exception:
                obj = None
        return int(e.code or 500), obj
    except Exception:
        return 0, None


def short_text(s: str, max_len: int = 500) -> str:
    flat = " ".join(str(s or "").replace("```", "").split())
    if len(flat) <= max_len:
        return flat
    return flat[: max_len - 1] + "…"


def extract_reply_text(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""

    def _try_parse(candidate: str) -> Any:
        try:
            return json.loads(candidate)
        except Exception:
            return None

    obj = _try_parse(s)
    if obj is None:
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            obj = _try_parse(s[first : last + 1])

    if isinstance(obj, dict):
        reply = [
            ((obj.get("reply") or {}).get("text") if isinstance(obj.get("reply"), dict) else None),
            ((obj.get("reply") or {}).get("message") if isinstance(obj.get("reply"), dict) else None),
            ((obj.get("result") or {}).get("reply") or {}).get("text")
            if isinstance(obj.get("result"), dict) and isinstance((obj.get("result") or {}).get("reply"), dict)
            else None,
            ((obj.get("output") or {}).get("text") if isinstance(obj.get("output"), dict) else None),
            obj.get("text"),
        ]
        for item in reply:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return s


def run_openclaw(command: dict[str, Any], timeout_s: float) -> tuple[bool, int | None, str, str]:
    scripts_dir = Path(__file__).resolve().parent
    wrapper = scripts_dir / "openclaww.sh"
    if not wrapper.exists():
        return False, None, "", "missing scripts/openclaww.sh"

    text = str(command.get("text") or "").strip()
    deliver_target = str(command.get("deliverTarget") or "").strip()
    if not text:
        return False, None, "", "empty command text"
    if not deliver_target.isdigit():
        return False, None, "", "invalid Telegram deliver target"

    agent_id = str(command.get("agentId") or os.environ.get("OPENCLAW_AGENT_ID") or "main").strip() or "main"
    args = [
        str(wrapper),
        "agent",
        "--agent",
        agent_id,
        "--message",
        text,
        "--deliver",
        "--channel",
        "telegram",
        "--reply-channel",
        "telegram",
        "--reply-to",
        deliver_target,
        "--json",
    ]

    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=max(5.0, float(timeout_s)),
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        return False, None, "", f"openclaw timeout after {timeout_s:.0f}s"
    except Exception as e:
        return False, None, "", f"openclaw exec error: {e}"

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    ok = int(proc.returncode or 0) == 0
    reply = extract_reply_text(out) if ok else ""
    fail = err or out
    return ok, int(proc.returncode), short_text(reply, 500), short_text(fail, 500)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run miniapp command relay worker on the ORION host.")
    ap.add_argument("--once", action="store_true", help="Claim and process at most one command.")
    ap.add_argument("--idle-sleep", type=float, default=float(os.environ.get("MINIAPP_COMMAND_RELAY_IDLE_S", "2.0")))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("MINIAPP_COMMAND_RELAY_TIMEOUT_S", "90")))
    args = ap.parse_args()

    base = get_base_url()
    token = get_token()
    if not base:
        print("missing relay base URL (set MINIAPP_COMMAND_RELAY_URL or ORION_MINIAPP_URL)", file=sys.stderr)
        return 2
    if not token:
        print("missing relay token (set MINIAPP_COMMAND_RELAY_TOKEN or MINIAPP_INGEST_TOKEN)", file=sys.stderr)
        return 2

    claim_url = f"{base}/api/relay/claim"
    worker_id = short_text(
        os.environ.get("MINIAPP_COMMAND_RELAY_WORKER_ID", f"{socket.gethostname()}:{os.getpid()}"),
        64,
    ) or "relay-worker"

    while True:
        code, payload = http_post_json(claim_url, token, {"workerId": worker_id})
        if code != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
            if args.once:
                return 1
            time.sleep(max(0.5, args.idle_sleep))
            continue

        cmd = payload.get("command")
        if not isinstance(cmd, dict):
            if args.once:
                return 0
            time.sleep(max(0.5, args.idle_sleep))
            continue

        relay_id = str(cmd.get("id") or "").strip()
        if not relay_id:
            if args.once:
                return 1
            time.sleep(max(0.5, args.idle_sleep))
            continue

        ok, rc, response_text, fail_text = run_openclaw(cmd, timeout_s=args.timeout)
        result_url = f"{base}/api/relay/{relay_id}/result"
        result_body = {
            "ok": bool(ok),
            "code": rc,
            "responseText": response_text if ok else "",
            "error": fail_text if not ok else "",
        }
        http_post_json(result_url, token, result_body)

        if args.once:
            return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
