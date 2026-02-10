#!/usr/bin/env python3
"""
Scan tasks/INBOX/*.md for newly-added `Result:` blocks under TASK_PACKET v1 entries,
and send a concise Telegram DM to Cory (single-bot mode) when new results appear.

Design goals:
- Cheap: markdown scan + small state file under tmp/
- Non-spammy: max N results per run, compact messages
- Safe: no secrets; no tool logs; user-facing text only

This is intended to be invoked by OpenClaw cron/heartbeat, not as a daemon.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")


@dataclasses.dataclass(frozen=True)
class PacketResult:
    inbox_path: Path
    display_path: str
    packet_start_line: int
    owner: str
    objective: str
    notify: str  # "telegram" | "none" | ""
    result_hash: str
    result_preview_lines: list[str]


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _split_packets(lines: list[str], start_line_offset: int) -> list[tuple[int, list[str]]]:
    """
    Return list of (start_line_number, packet_lines) for TASK_PACKET v1 blocks.
    Ignores fenced blocks (```).
    """
    packets: list[tuple[int, list[str]]] = []
    in_fence = False
    cur: list[str] | None = None
    cur_start: int | None = None

    for idx, raw in enumerate(lines, start=1 + start_line_offset):
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_fence = not in_fence

        if not in_fence and RE_PACKET_HEADER.match(line):
            if cur is not None and cur_start is not None:
                packets.append((cur_start, cur))
            cur = [line]
            cur_start = idx
            continue

        if cur is not None:
            cur.append(line)

    if cur is not None and cur_start is not None:
        packets.append((cur_start, cur))

    return packets


def _parse_top_level_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    # Skip header line; stop collecting once we enter a section like "Success Criteria:"
    for line in packet_lines[1:]:
        m = RE_KV.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        value = m.group("value").strip()
        # Always record; later keys override earlier ones (rare but fine).
        fields[key] = value
    return fields


def _extract_result_block(packet_lines: list[str]) -> list[str] | None:
    """
    If a packet has a `Result:` line, return lines from that line through end of packet.
    """
    start = None
    for i, line in enumerate(packet_lines):
        if line.strip() == "Result:":
            start = i
            break
    if start is None:
        return None
    return packet_lines[start:]


def _preview_result_lines(result_block: list[str], *, max_lines: int = 12, max_chars: int = 900) -> list[str]:
    """
    Produce a compact preview for Telegram.

    Note: we bias toward including the "Next step" content if present, since truncating
    right after the "Next step:" header is confusing.
    """
    non_empty: list[tuple[int, str]] = []
    for idx, raw in enumerate(result_block[1:], start=1):  # skip "Result:" header itself
        line = raw.rstrip()
        if not line.strip():
            continue
        non_empty.append((idx, line))

    if not non_empty:
        return ["(Result present, but empty.)"]

    out: list[str] = []
    chars = 0
    cut = 0
    for _, line in non_empty:
        out.append(line)
        chars += len(line) + 1
        cut += 1
        if cut >= max_lines or chars >= max_chars:
            break

    # If we ended on a "Next step" header, try to include the next non-empty line too.
    if out:
        last = out[-1].strip().lower()
        if last in {"next step:", "next step (if any):"}:
            if cut < len(non_empty):
                nxt = non_empty[cut][1]
                if chars + len(nxt) + 1 <= max_chars:
                    out.append(nxt)

    return out


def _sha256_text(lines: list[str]) -> str:
    h = hashlib.sha256()
    for ln in lines:
        h.update(ln.encode("utf-8", errors="replace"))
        h.update(b"\n")
    return h.hexdigest()


def _load_state(state_path: Path) -> dict[str, float]:
    if not state_path.exists():
        return {}
    try:
        obj = json.loads(_read_text(state_path))
        if not isinstance(obj, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in obj.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                out[k] = float(v)
        return out
    except Exception:
        return {}


def _save_state(state_path: Path, state: dict[str, float]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(state_path)


def _get_openclaw_cfg_path() -> Path:
    raw = os.environ.get("OPENCLAW_CONFIG_PATH", "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    return Path.home() / ".openclaw" / "openclaw.json"


def _get_telegram_chat_id() -> str:
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if chat:
        return chat

    cfg_path = _get_openclaw_cfg_path()
    try:
        cfg = json.loads(_read_text(cfg_path))
        chat = (
            cfg.get("channels", {})
            .get("telegram", {})
            .get("allowFrom", [None])[0]
        )
        if isinstance(chat, (int, float)):
            chat = str(int(chat))
        if isinstance(chat, str) and chat.strip():
            return chat.strip()
    except Exception:
        pass

    raise RuntimeError("Could not determine TELEGRAM_CHAT_ID (env TELEGRAM_CHAT_ID or channels.telegram.allowFrom[0]).")


def _get_telegram_bot_token() -> str:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if tok:
        return tok
    p = Path.home() / ".openclaw" / "secrets" / "telegram.token"
    try:
        return _read_text(p).replace("\r", "").replace("\n", "").strip()
    except Exception:
        return ""


def _telegram_send_message(*, chat_id: str, token: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        # Drain for keep-alive correctness; ignore body.
        resp.read()


def _find_new_results(repo_root: Path) -> list[PacketResult]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    out: list[PacketResult] = []
    if not inbox_dir.exists():
        return out

    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue

        txt = _read_text(inbox)
        all_lines = txt.splitlines()

        # Only scan packets appended under "## Packets" to avoid examples.
        start_idx = 0
        for i, line in enumerate(all_lines):
            if line.strip() == "## Packets":
                start_idx = i + 1
                break

        packets = _split_packets(all_lines[start_idx:], start_line_offset=start_idx)
        for start_line, pkt_lines in packets:
            fields = _parse_top_level_fields(pkt_lines)
            result_block = _extract_result_block(pkt_lines)
            if not result_block:
                continue

            notify = fields.get("Notify", "").strip().lower()
            owner = fields.get("Owner", "").strip() or inbox.stem.upper()
            objective = fields.get("Objective", "").strip() or "(no objective)"
            rh = _sha256_text(result_block)
            preview = _preview_result_lines(result_block)

            try:
                disp = str(inbox.relative_to(repo_root))
            except Exception:
                # Fall back to a resolved absolute path for clarity when cwd is a symlinked workspace.
                disp = inbox.resolve().as_posix()

            out.append(
                PacketResult(
                    inbox_path=inbox,
                    display_path=disp,
                    packet_start_line=start_line,
                    owner=owner,
                    objective=objective,
                    notify=notify,
                    result_hash=rh,
                    result_preview_lines=preview,
                )
            )

    return out


def _format_message(items: list[PacketResult]) -> str:
    lines: list[str] = []
    lines.append("Inbox results:")
    lines.append("")

    for i, it in enumerate(items, start=1):
        head = f"{i}. [{it.owner}] {it.objective}"
        lines.append(head)
        for pl in it.result_preview_lines:
            lines.append(pl)
        lines.append(f"file: {it.display_path}:{it.packet_start_line}")
        lines.append("")

    msg = "\n".join(lines).rstrip() + "\n"
    # Telegram practical limit is 4096 chars; keep margin.
    if len(msg) <= 3800:
        return msg

    clipped: list[str] = []
    chars = 0
    for ln in msg.splitlines():
        if chars + len(ln) + 1 > 3750:
            clipped.append("…")
            break
        clipped.append(ln)
        chars += len(ln) + 1
    return "\n".join(clipped).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Notify Cory on Telegram when new Task Packet Result blocks appear.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--state-path",
        default="tmp/inbox_notify_state.json",
        help="State file path (default: tmp/inbox_notify_state.json)",
    )
    ap.add_argument("--max-per-run", type=int, default=3, help="Max results to notify per run (default: 3)")
    ap.add_argument(
        "--require-notify-telegram",
        action="store_true",
        help="Only notify packets with `Notify: telegram` (recommended for non-lab use).",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    state = _load_state(state_path)

    candidates = _find_new_results(repo_root)

    # Only allow user-facing notifications when explicitly opted in, unless overridden.
    if args.require_notify_telegram:
        candidates = [c for c in candidates if c.notify == "telegram"]

    new_items: list[PacketResult] = [c for c in candidates if c.result_hash not in state]
    if not new_items:
        print("NOTIFY_IDLE")
        return 0

    new_items = new_items[: max(1, int(args.max_per_run))]

    dry = os.environ.get("NOTIFY_DRY_RUN", "").strip() == "1"
    if dry:
        print(_format_message(new_items))
    else:
        chat_id = _get_telegram_chat_id()
        token = _get_telegram_bot_token()
        if not token:
            print("ERROR: Missing Telegram bot token (~/.openclaw/secrets/telegram.token or TELEGRAM_BOT_TOKEN).", file=sys.stderr)
            return 2

        msg = _format_message(new_items)
        try:
            _telegram_send_message(chat_id=chat_id, token=token, text=msg)
        except urllib.error.HTTPError as e:
            print(f"ERROR: Telegram HTTP error: {e.code}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"ERROR: Telegram send failed: {e}", file=sys.stderr)
            return 2

    now = time.time()
    for it in new_items:
        state[it.result_hash] = now

    # Bound state size to avoid unbounded growth.
    if len(state) > 5000:
        # Keep newest N based on timestamp values.
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:4000])

    _save_state(state_path, state)
    print("NOTIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
