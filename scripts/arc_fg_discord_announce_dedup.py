#!/usr/bin/env python3
"""Send Arc FG updates to Discord only when summary content changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from outbound_text_guard import sanitize_outbound_text
except Exception:  # pragma: no cover
    from scripts.outbound_text_guard import sanitize_outbound_text  # type: ignore

OPENCLAW_BIN = (
    os.environ.get("OPENCLAW_BIN")
    or shutil.which("openclaw")
    or "/Users/corystoner/.npm-global/bin/openclaw"
)


def run_cmd(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": now_iso(), "active_run": None}
    return json.loads(path.read_text())


def save_state(path: Path, state: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(path)


def latest_run(job_id: str) -> dict[str, Any] | None:
    raw = run_cmd([OPENCLAW_BIN, "cron", "runs", "--id", job_id, "--limit", "1"])
    data = json.loads(raw)
    entries = data.get("entries") or []
    return entries[0] if entries else None


def normalize_summary(summary: str) -> str:
    text = summary.strip().lower()
    if not text:
        return ""
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", text)
    text = re.sub(r"\bagent:[a-z0-9:_-]+\b", "<agent_ref>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<date>", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", "<time>", text)
    text = re.sub(r"\b\d{10,13}\b", "<ts>", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Collapse repeated "all complete / no further action" summaries into one signature.
    if (
        "completed" in text
        and "no further action" in text
        and "draft deltas" not in text
        and "links/sources referenced" not in text
    ):
        return "steady_state_complete"
    return text


def summary_signature_hash(summary: str) -> str:
    normalized = normalize_summary(summary)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _extract_messages_from_read_payload(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    payload = data.get("payload") or {}
    return payload.get("messages") or []


def latest_discord_summary_from_channel(target: str) -> str | None:
    try:
        raw = run_cmd(
            [
                OPENCLAW_BIN,
                "message",
                "read",
                "--channel",
                "discord",
                "--target",
                target,
                "--limit",
                "6",
                "--json",
            ]
        )
    except RuntimeError:
        return None

    messages = _extract_messages_from_read_payload(raw)
    for msg in messages:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if content.startswith("ORION Closed-Loop Update"):
            parts = content.split("\n\n", 1)
            return parts[1].strip() if len(parts) == 2 else content
    return None


def format_message(summary: str, run_at_ms: int | None) -> str:
    prefix = "ORION Closed-Loop Update"
    if run_at_ms:
        ts = datetime.fromtimestamp(run_at_ms / 1000).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        prefix = f"{prefix} ({ts})"
    body = sanitize_outbound_text(summary.strip())
    max_len = 1800
    if len(body) > max_len:
        body = body[: max_len - 17].rstrip() + "\n\n[truncated]"
    return f"{prefix}\n\n{body}"


def send_discord(target: str, message: str) -> dict[str, Any]:
    raw = run_cmd(
        [
            OPENCLAW_BIN,
            "message",
            "send",
            "--channel",
            "discord",
            "--target",
            target,
            "--message",
            message,
            "--json",
        ]
    )
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduped Discord announcer for Arc FG rollups.")
    parser.add_argument("--job-id", required=True, help="Cron job ID to read latest run summary from.")
    parser.add_argument("--state", required=True, help="Path to arc_fg_loop_state.json.")
    parser.add_argument("--target", required=True, help="Discord channel target id.")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = load_state(state_path)
    run = latest_run(args.job_id)

    meta = state.setdefault("discord_announce_dedup", {})
    meta["checked_at"] = now_iso()
    meta["job_id"] = args.job_id

    if not run:
        meta["status"] = "skip_no_run"
        state["updated_at"] = meta["checked_at"]
        save_state(state_path, state)
        print(json.dumps({"status": "ok", "action": "skip_no_run"}))
        return 0

    summary = run.get("summary") or ""
    run_at_ms = run.get("runAtMs")
    summary_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    signature_hash = summary_signature_hash(summary)

    last_hash = meta.get("last_sent_summary_hash")
    last_signature_hash = meta.get("last_sent_signature_hash")
    last_run_at_ms = meta.get("last_sent_run_at_ms")

    if not summary.strip():
        meta["status"] = "skip_empty_summary"
        meta["latest_run_at_ms"] = run_at_ms
        state["updated_at"] = meta["checked_at"]
        save_state(state_path, state)
        print(json.dumps({"status": "ok", "action": "skip_empty_summary", "run_at_ms": run_at_ms}))
        return 0

    remote_summary = latest_discord_summary_from_channel(args.target)
    remote_signature_hash = summary_signature_hash(remote_summary or "") if remote_summary else None

    if (
        summary_hash == last_hash
        or signature_hash == last_signature_hash
        or (remote_signature_hash is not None and signature_hash == remote_signature_hash)
        or (last_run_at_ms is not None and run_at_ms is not None and run_at_ms <= last_run_at_ms)
    ):
        meta["status"] = "skip_duplicate"
        meta["latest_run_at_ms"] = run_at_ms
        meta["latest_summary_hash"] = summary_hash
        meta["latest_signature_hash"] = signature_hash
        meta["latest_remote_signature_hash"] = remote_signature_hash
        state["updated_at"] = meta["checked_at"]
        save_state(state_path, state)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "action": "skip_duplicate",
                    "run_at_ms": run_at_ms,
                    "summary_hash": summary_hash,
                    "signature_hash": signature_hash,
                }
            )
        )
        return 0

    message = format_message(summary, run_at_ms)
    send_result = send_discord(args.target, message)

    meta["status"] = "sent"
    meta["last_sent_at"] = now_iso()
    meta["last_sent_run_at_ms"] = run_at_ms
    meta["last_sent_summary_hash"] = summary_hash
    meta["last_sent_signature_hash"] = signature_hash
    meta["last_send_result"] = send_result
    state["updated_at"] = meta["last_sent_at"]
    save_state(state_path, state)

    print(
        json.dumps(
            {
                "status": "ok",
                "action": "sent",
                "run_at_ms": run_at_ms,
                "summary_hash": summary_hash,
                "signature_hash": signature_hash,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
