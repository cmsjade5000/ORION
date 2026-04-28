#!/usr/bin/env python3
"""
Complete low-risk ORION AgentMail reply packets.

This worker is intentionally narrow. It only handles SCRIBE email-draft packets
created by email_triage_router for Cory's trusted address, with no links,
attachments, or risk indicators. It writes a Result block only after AgentMail
returns a concrete sent message id.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from inbox_file_ops import atomic_write_text, ensure_packets_header, locked_file, packet_identity
    from inbox_state import load_kv_state, save_kv_state
    from notify_inbox_results import _get_telegram_bot_token, _get_telegram_chat_id, _telegram_send_message
except Exception:  # pragma: no cover
    from scripts.inbox_file_ops import atomic_write_text, ensure_packets_header, locked_file, packet_identity  # type: ignore
    from scripts.inbox_state import load_kv_state, save_kv_state  # type: ignore
    from scripts.notify_inbox_results import _get_telegram_bot_token, _get_telegram_chat_id, _telegram_send_message  # type: ignore


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")
RE_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

DEFAULT_FROM_INBOX = "orion_gatewaybot@agentmail.to"
DEFAULT_TRUSTED_SENDER = "cory.stoner@icloud.com"
DEFAULT_STUCK_MINUTES = 15.0


@dataclasses.dataclass(frozen=True)
class PacketRef:
    inbox_path: Path
    packet_start_line: int
    packet_end_line: int
    fields: dict[str, str]
    raw_lines: list[str]


@dataclasses.dataclass(frozen=True)
class Eligibility:
    ok: bool
    reason: str


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _split_packets(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    in_fence = False
    starts: list[int] = []
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and RE_PACKET_HEADER.match(line):
            starts.append(idx)

    out: list[tuple[int, int, list[str]]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        out.append((start, end, lines[start:end]))
    return out


def _parse_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key = ""
    for raw in packet_lines[1:]:
        line = raw.rstrip("\n")
        m = RE_KV.match(line)
        if m:
            current_key = m.group("key").strip()
            fields[current_key] = m.group("value").strip()
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            bullet = stripped[2:].strip()
            m = RE_KV.match(bullet)
            if m:
                current_key = m.group("key").strip()
                fields[current_key] = m.group("value").strip()
                continue
        if current_key and line.startswith("- "):
            prev = fields.get(current_key, "")
            item = line[2:].strip()
            fields[current_key] = (prev + "\n" + item).strip() if prev else item
    return fields


def _packet_has_result(packet_lines: list[str]) -> bool:
    start = None
    for idx, line in enumerate(packet_lines):
        if line.strip() == "Result:":
            start = idx
            break
    return start is not None and any(line.strip() for line in packet_lines[start + 1 :])


def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in packet_lines:
        if line.strip() == "Result:":
            break
        out.append(line)
    return out


def _extract_email(value: str) -> str:
    m = re.search(r"<([^>]+@[^>]+)>", value or "")
    if m:
        return m.group(1).strip().lower()
    m = RE_EMAIL.search(value or "")
    return m.group(0).strip().lower() if m else ""


def _norm(value: str) -> str:
    return " ".join((value or "").strip().split())


def _field_none_or_empty(value: str) -> bool:
    return _norm(value).lower() in {"", "(none)", "none", "n/a", "na"}


def _risks_are_low(value: str) -> bool:
    risks = [_norm(part).lower() for part in (value or "").splitlines() if _norm(part)]
    return risks == ["low"]


def _message_id(fields: dict[str, str]) -> str:
    return _norm(fields.get("Message ID", ""))


def _request_summary(fields: dict[str, str]) -> str:
    return _norm(fields.get("Request Summary", ""))


def _subject(fields: dict[str, str]) -> str:
    return _norm(fields.get("Subject", ""))


def _eligible(pref: PacketRef, *, trusted_sender: str) -> Eligibility:
    fields = pref.fields
    if _packet_has_result(pref.raw_lines):
        return Eligibility(False, "has_result")
    if fields.get("Owner", "").strip().upper() != "SCRIBE":
        return Eligibility(False, "owner_not_scribe")
    objective = fields.get("Objective", "").strip().lower()
    if "send-ready draft response" not in objective:
        return Eligibility(False, "objective_not_email_reply")
    if _extract_email(fields.get("Sender", "")) != trusted_sender.lower():
        return Eligibility(False, "sender_not_trusted")
    if fields.get("Sender Domain", "").strip().lower() != trusted_sender.rsplit("@", 1)[-1].lower():
        return Eligibility(False, "sender_domain_not_trusted")
    if not _field_none_or_empty(fields.get("Link Domains", "")):
        return Eligibility(False, "link_domains_present")
    if not _field_none_or_empty(fields.get("Attachment Types", "")):
        return Eligibility(False, "attachments_present")
    if not _risks_are_low(fields.get("Risks", "")):
        return Eligibility(False, "risks_not_low")
    if not _message_id(fields):
        return Eligibility(False, "missing_message_id")
    if not _request_summary(fields):
        return Eligibility(False, "missing_request_summary")
    return Eligibility(True, "eligible")


def _iter_packets(repo_root: Path) -> list[PacketRef]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    if not inbox_dir.exists():
        return []
    refs: list[PacketRef] = []
    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue
        lines = _read_lines(inbox)
        header_idx = None
        for idx, line in enumerate(lines):
            if line.strip() == "## Packets":
                header_idx = idx
                break
        if header_idx is None:
            continue
        for start, end, pkt_lines in _split_packets(lines[header_idx + 1 :]):
            refs.append(
                PacketRef(
                    inbox_path=inbox,
                    packet_start_line=(header_idx + 1) + start + 1,
                    packet_end_line=(header_idx + 1) + end,
                    fields=_parse_fields(pkt_lines),
                    raw_lines=pkt_lines,
                )
            )
    return refs


def _agent_text_from_json(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "message", "output", "summary", "response"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        content = payload.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            if parts:
                return "\n".join(parts)
        payloads = payload.get("payloads")
        if isinstance(payloads, list):
            parts = []
            for item in payloads:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            if parts:
                return "\n".join(parts)
        result = payload.get("result")
        if result is not None:
            return _agent_text_from_json(result)
    return ""


def _compose_prompt(pref: PacketRef) -> str:
    fields = pref.fields
    return "\n".join(
        [
            "You are SCRIBE. Produce only the email reply body, with no preamble.",
            "Keep it short, natural, and safe. Do not mention internal routing or Task Packets.",
            "",
            f"Sender: {fields.get('Sender', '')}",
            f"Subject: {_subject(fields)}",
            f"Request Summary: {_request_summary(fields)}",
            "",
            "Return the exact body text ORION should send.",
        ]
    )


def compose_reply(
    repo_root: Path,
    pref: PacketRef,
    *,
    draft_text: str = "",
    timeout_seconds: int = 180,
) -> str:
    if draft_text.strip():
        return draft_text.strip()

    cmd = [
        "openclaw",
        "agent",
        "--agent",
        "scribe",
        "--thinking",
        "off",
        "--timeout",
        str(max(10, int(timeout_seconds))),
        "--json",
        "--message",
        _compose_prompt(pref),
    ]
    proc = subprocess.run(cmd, cwd=str(repo_root), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "draft command failed").strip())
    text = ""
    try:
        text = _agent_text_from_json(json.loads(proc.stdout))
    except Exception:
        text = proc.stdout
    text = text.strip()
    if not text:
        raise RuntimeError(
            "draft command returned empty reply"
            + (f" stdout={proc.stdout[:300]!r}" if proc.stdout else "")
            + (f" stderr={proc.stderr[:300]!r}" if proc.stderr else "")
        )
    return text


def _latest_received_matches(repo_root: Path, *, from_inbox: str, trusted_sender: str, message_id: str) -> None:
    cmd = ["node", "skills/agentmail/cli.js", "list-messages", from_inbox, "20"]
    proc = subprocess.run(cmd, cwd=str(repo_root), text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "agentmail list failed").strip())
    payload = json.loads(proc.stdout)
    messages = payload.get("messages") if isinstance(payload, dict) else []
    for msg in messages if isinstance(messages, list) else []:
        if not isinstance(msg, dict):
            continue
        labels = {str(label).strip().lower() for label in (msg.get("labels") or [])}
        if "received" not in labels:
            continue
        if _extract_email(str(msg.get("from") or "")) != trusted_sender.lower():
            continue
        latest_id = _norm(str(msg.get("message_id") or msg.get("id") or ""))
        if latest_id != message_id:
            raise RuntimeError(f"latest trusted sender message mismatch: {latest_id or '(none)'}")
        return
    raise RuntimeError("no recent received message found for trusted sender")


def send_reply(
    repo_root: Path,
    *,
    from_inbox: str,
    trusted_sender: str,
    message_id: str,
    body: str,
) -> tuple[str, str]:
    _latest_received_matches(repo_root, from_inbox=from_inbox, trusted_sender=trusted_sender, message_id=message_id)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
        tmp.write(body.rstrip() + "\n")
        body_path = Path(tmp.name)
    try:
        cmd = [
            "node",
            "skills/agentmail/cli.js",
            "reply-last",
            "--from",
            from_inbox,
            "--text-file",
            str(body_path),
            "--from-email",
            trusted_sender,
        ]
        proc = subprocess.run(cmd, cwd=str(repo_root), text=True, capture_output=True, check=False)
    finally:
        try:
            body_path.unlink()
        except FileNotFoundError:
            pass
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "agentmail reply failed").strip())
    payload = json.loads(proc.stdout)
    sent = payload.get("sent") if isinstance(payload, dict) else {}
    replied_to = payload.get("repliedTo") if isinstance(payload, dict) else {}
    sent_id = _norm(str((sent or {}).get("message_id") or ""))
    replied_id = _norm(str((replied_to or {}).get("message_id") or ""))
    if not sent_id:
        raise RuntimeError("AgentMail returned no sent message_id")
    if replied_id and replied_id != message_id:
        raise RuntimeError(f"AgentMail replied_to mismatch: {replied_id}")
    return sent_id, replied_id or message_id


def _short_summary(body: str) -> str:
    text = _norm(body)
    if len(text) > 180:
        return text[:177].rstrip() + "..."
    return text or "(empty)"


def _result_block(*, message_id: str, sent_id: str, replied_to: str, body: str) -> list[str]:
    return [
        "",
        "Result:",
        "Status: OK",
        "What changed / what I found:",
        "  - Auto-sent low-risk AgentMail reply for trusted sender.",
        f"  - Replied-to message id: {replied_to or message_id}",
        f"  - Sent message id: {sent_id}",
        f"  - Reply summary: {_short_summary(body)}",
        "Next step (if any):",
        "  - None.",
        "",
    ]


def _write_result(pref: PacketRef, result_lines: list[str]) -> None:
    identity = packet_identity(fields=pref.fields, packet_before_result=_packet_before_result(pref.raw_lines))
    lock_path = pref.inbox_path.with_suffix(pref.inbox_path.suffix + ".lock")
    with locked_file(lock_path):
        file_lines = ensure_packets_header(_read_lines(pref.inbox_path), owner=pref.inbox_path.stem.upper())
        header_idx = None
        for idx, line in enumerate(file_lines):
            if line.strip() == "## Packets":
                header_idx = idx
                break
        if header_idx is None:
            raise RuntimeError(f"missing packets header: {pref.inbox_path}")
        match: tuple[int, int, list[str]] | None = None
        for start, end, pkt_lines in _split_packets(file_lines[header_idx + 1 :]):
            fields = _parse_fields(pkt_lines)
            candidate = packet_identity(fields=fields, packet_before_result=_packet_before_result(pkt_lines))
            if identity.idempotency_key:
                if candidate.idempotency_key == identity.idempotency_key:
                    match = ((header_idx + 1) + start, (header_idx + 1) + end, pkt_lines)
                    break
            elif candidate.content_hash == identity.content_hash:
                match = ((header_idx + 1) + start, (header_idx + 1) + end, pkt_lines)
                break
        if match is None:
            raise RuntimeError("packet disappeared before result write")
        start, end, pkt_lines = match
        result_idx = None
        for offset, line in enumerate(pkt_lines):
            if line.strip() == "Result:":
                result_idx = start + offset
                break
        if result_idx is None:
            new_lines = file_lines[:end] + result_lines + file_lines[end:]
        else:
            new_lines = file_lines[:result_idx] + result_lines + file_lines[end:]
        atomic_write_text(pref.inbox_path, "\n".join(new_lines).rstrip() + "\n")


def process_replies(
    repo_root: Path,
    *,
    max_packets: int,
    from_inbox: str,
    trusted_sender: str,
    draft_text: str = "",
    dry_run: bool = False,
    compose_timeout_seconds: int = 180,
) -> dict[str, Any]:
    processed: list[dict[str, str]] = []
    skipped: dict[str, int] = {}
    for pref in _iter_packets(repo_root):
        eligibility = _eligible(pref, trusted_sender=trusted_sender)
        if not eligibility.ok:
            skipped[eligibility.reason] = skipped.get(eligibility.reason, 0) + 1
            continue
        message_id = _message_id(pref.fields)
        body = compose_reply(repo_root, pref, draft_text=draft_text, timeout_seconds=compose_timeout_seconds)
        if dry_run:
            processed.append({"message_id": message_id, "sent_message_id": "DRY_RUN", "replied_to": message_id})
        else:
            sent_id, replied_to = send_reply(
                repo_root,
                from_inbox=from_inbox,
                trusted_sender=trusted_sender,
                message_id=message_id,
                body=body,
            )
            _write_result(pref, _result_block(message_id=message_id, sent_id=sent_id, replied_to=replied_to, body=body))
            processed.append({"message_id": message_id, "sent_message_id": sent_id, "replied_to": replied_to})
        if len(processed) >= max(1, int(max_packets)):
            break
    return {"processed": processed, "processed_count": len(processed), "skipped": skipped}


def _parse_ts(raw: str) -> float | None:
    text = _norm(raw)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return None


def _stuck_candidates(repo_root: Path, *, trusted_sender: str, threshold_minutes: float, now_ts: float) -> list[PacketRef]:
    out: list[PacketRef] = []
    for pref in _iter_packets(repo_root):
        eligibility = _eligible(pref, trusted_sender=trusted_sender)
        if not eligibility.ok:
            continue
        ts = _parse_ts(pref.fields.get("Timestamp", ""))
        if ts is None:
            continue
        age_minutes = (now_ts - ts) / 60.0
        if age_minutes >= threshold_minutes:
            out.append(pref)
    return out


def alert_stuck(
    repo_root: Path,
    *,
    trusted_sender: str,
    threshold_minutes: float = DEFAULT_STUCK_MINUTES,
    state_path: Path | None = None,
    dry_run: bool = False,
    now_ts: float | None = None,
) -> dict[str, Any]:
    now = time.time() if now_ts is None else float(now_ts)
    state_path = state_path or (repo_root / "tmp" / "email_reply_worker_state.json")
    state = load_kv_state(state_path)
    alerted: list[dict[str, str]] = []
    for pref in _stuck_candidates(repo_root, trusted_sender=trusted_sender, threshold_minutes=threshold_minutes, now_ts=now):
        msg_id = _message_id(pref.fields)
        key = "stuck:" + msg_id
        if state.get(key, 0.0) > 0:
            continue
        text = (
            "ORION email reply is stuck queued.\n"
            f"Subject: {_subject(pref.fields) or '(none)'}\n"
            f"Message ID: {msg_id}\n"
            f"Packet: {pref.inbox_path.relative_to(repo_root)}:{pref.packet_start_line}"
        )
        if not dry_run:
            chat_id = _get_telegram_chat_id()
            token = _get_telegram_bot_token()
            if not token:
                raise RuntimeError("missing_telegram_bot_token")
            _telegram_send_message(chat_id=chat_id, token=token, text=text)
        state[key] = now
        alerted.append({"message_id": msg_id, "packet": f"{pref.inbox_path.relative_to(repo_root)}:{pref.packet_start_line}"})
    if alerted and not dry_run:
        save_kv_state(state_path, state)
    return {"alerted_count": len(alerted), "alerted": alerted}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Complete low-risk Cory AgentMail reply packets.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--from-inbox", default=DEFAULT_FROM_INBOX)
    ap.add_argument("--trusted-sender", default=DEFAULT_TRUSTED_SENDER)
    ap.add_argument("--max-packets", type=int, default=2)
    ap.add_argument("--draft-text", default=os.environ.get("ORION_EMAIL_REPLY_DRAFT_TEXT", ""))
    ap.add_argument("--compose-timeout-seconds", type=int, default=180)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--alert-stuck", action="store_true")
    ap.add_argument("--stuck-minutes", type=float, default=DEFAULT_STUCK_MINUTES)
    ap.add_argument("--state-path", default="tmp/email_reply_worker_state.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    rc = 0
    try:
        result = process_replies(
            repo_root,
            max_packets=max(1, int(args.max_packets)),
            from_inbox=args.from_inbox,
            trusted_sender=args.trusted_sender,
            draft_text=args.draft_text,
            dry_run=bool(args.dry_run),
            compose_timeout_seconds=max(10, int(args.compose_timeout_seconds)),
        )
    except Exception as exc:
        rc = 1
        result = {"processed": [], "processed_count": 0, "skipped": {}, "error": str(exc)}
    if args.alert_stuck:
        result["stuck_alerts"] = alert_stuck(
            repo_root,
            trusted_sender=args.trusted_sender,
            threshold_minutes=max(1.0, float(args.stuck_minutes)),
            state_path=(repo_root / args.state_path).resolve(),
            dry_run=bool(args.dry_run),
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"EMAIL_REPLY_WORKER processed={result['processed_count']}")
        if result.get("error"):
            print(f"EMAIL_REPLY_ERROR {result['error']}", file=sys.stderr)
        if "stuck_alerts" in result:
            print(f"EMAIL_REPLY_STUCK_ALERTS alerted={result['stuck_alerts']['alerted_count']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
