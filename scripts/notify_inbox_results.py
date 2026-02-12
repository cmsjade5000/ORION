#!/usr/bin/env python3
"""
Scan tasks/INBOX/*.md for newly-added `Result:` blocks under TASK_PACKET v1 entries,
and send a concise notification to Cory (Telegram and/or Discord) when new results appear.

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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    # Optional dependency: Mini App dashboard progress visibility.
    # When executed as `python3 scripts/notify_inbox_results.py`, sys.path[0] is `scripts/`,
    # so `miniapp_ingest` is importable as a sibling module.
    from miniapp_ingest import emit as miniapp_emit
except Exception:  # pragma: no cover
    try:  # pragma: no cover
        from scripts.miniapp_ingest import emit as miniapp_emit  # type: ignore
    except Exception:  # pragma: no cover
        def miniapp_emit(*args, **kwargs):  # type: ignore[no-redef]
            return False


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")


@dataclasses.dataclass(frozen=True)
class PacketResult:
    inbox_path: Path
    display_path: str
    packet_start_line: int
    owner: str
    objective: str
    notify: str  # "telegram" | "discord" | "none" | "" | "telegram,discord"
    result_hash: str
    result_preview_lines: list[str]


@dataclasses.dataclass(frozen=True)
class PacketQueued:
    inbox_path: Path
    display_path: str
    packet_start_line: int
    owner: str
    objective: str
    notify: str  # "telegram" | "discord" | "none" | "" | "telegram,discord"
    queued_hash: str


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _env_truthy(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def _parse_notify_channels(raw: str) -> set[str]:
    """
    Parse `Notify:` values.

    Supported:
    - "telegram"
    - "discord"
    - "telegram,discord" (comma/space/plus separated)
    - "none" / empty -> no notifications
    """
    s = (raw or "").strip().lower()
    if not s or s == "none":
        return set()
    parts = [p.strip() for p in re.split(r"[,+\\s]+", s) if p.strip()]
    # Keep only known channels (future-proof: ignore unknown tokens).
    return {p for p in parts if p in {"telegram", "discord"}}


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
    block = packet_lines[start:]
    # Treat an empty placeholder Result as "no result yet" so we don't spam or misclassify queued packets.
    has_content = any(ln.strip() for ln in block[1:])
    if not has_content:
        return None
    return block


def _extract_packet_before_result(packet_lines: list[str]) -> list[str]:
    """
    Return packet lines excluding the `Result:` section, if present.

    Important: This hash is used to dedupe "queued" notifications even after a Result is appended.
    """
    out: list[str] = []
    for ln in packet_lines:
        if ln.strip() == "Result:":
            break
        out.append(ln)
    return out


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

def _get_openclaw_cmd(repo_root: Path) -> list[str]:
    """
    Prefer repo-local wrapper so automation environments with a minimal PATH still work.
    """
    wrapper = (repo_root / "scripts" / "openclaww.sh").resolve()
    if wrapper.exists():
        return [str(wrapper)]
    return ["openclaw"]


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

def _get_discord_default_target(repo_root: Path) -> str:
    """
    Resolve the Discord target used for notifier sends.

    Priority:
    1) env DISCORD_DEFAULT_POST_TARGET (examples: "user:123", "channel:456")
    2) channels.discord.dm.allowFrom[0] -> "user:<id>" (best-effort)
    """
    t = os.environ.get("DISCORD_DEFAULT_POST_TARGET", "").strip()
    if t:
        return t

    cfg_path = _get_openclaw_cfg_path()
    try:
        cfg = json.loads(_read_text(cfg_path))
        allow_from = (
            (cfg.get("channels", {}) or {})
            .get("discord", {})
            .get("dm", {})
            .get("allowFrom", [])
        )
        if isinstance(allow_from, list) and allow_from:
            first = str(allow_from[0]).strip()
            if first:
                return f"user:{first}"
    except Exception:
        pass

    raise RuntimeError(
        "Could not determine Discord target (set env DISCORD_DEFAULT_POST_TARGET or configure channels.discord.dm.allowFrom[0])."
    )


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

def _discord_send_message(*, repo_root: Path, target: str, text: str) -> None:
    """
    Send via OpenClaw's Discord channel plugin so we never touch raw Discord credentials here.
    """
    cmd = _get_openclaw_cmd(repo_root)
    argv = cmd + ["message", "send", "--channel", "discord", "--target", target, "--message", text]
    r = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "discord send failed").strip())


def _find_packets(repo_root: Path) -> tuple[list[PacketQueued], list[PacketResult]]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    queued: list[PacketQueued] = []
    results: list[PacketResult] = []
    if not inbox_dir.exists():
        return queued, results

    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue

        txt = _read_text(inbox)
        all_lines = txt.splitlines()

        # Only scan packets appended under "## Packets" to avoid examples/notes.
        packets_header_idx = None
        for i, line in enumerate(all_lines):
            if line.strip() == "## Packets":
                packets_header_idx = i
                break
        if packets_header_idx is None:
            continue
        start_idx = packets_header_idx + 1

        packets = _split_packets(all_lines[start_idx:], start_line_offset=start_idx)
        for start_line, pkt_lines in packets:
            fields = _parse_top_level_fields(pkt_lines)
            result_block = _extract_result_block(pkt_lines)

            notify = fields.get("Notify", "").strip().lower()
            owner = fields.get("Owner", "").strip() or inbox.stem.upper()
            objective = fields.get("Objective", "").strip() or "(no objective)"
            before = _extract_packet_before_result(pkt_lines)
            qh = _sha256_text(before)

            try:
                disp = str(inbox.relative_to(repo_root))
            except Exception:
                # Fall back to a resolved absolute path for clarity when cwd is a symlinked workspace.
                disp = inbox.resolve().as_posix()

            if result_block:
                rh = _sha256_text(result_block)
                preview = _preview_result_lines(result_block)
                results.append(
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
            else:
                queued.append(
                    PacketQueued(
                        inbox_path=inbox,
                        display_path=disp,
                        packet_start_line=start_line,
                        owner=owner,
                        objective=objective,
                        notify=notify,
                        queued_hash=qh,
                    )
                )

    return queued, results


def _format_message(*, queued: list[PacketQueued], results: list[PacketResult], max_len: int | None = None) -> str:
    lines: list[str] = []
    lines.append("Inbox update:")
    lines.append("")

    if queued:
        lines.append("Queued:")
        for i, it in enumerate(queued, start=1):
            lines.append(f"{i}. [{it.owner}] {it.objective}")
            lines.append(f"file: {it.display_path}:{it.packet_start_line}")
        lines.append("")

    if results:
        lines.append("Results:")
        lines.append("")
        for i, it in enumerate(results, start=1):
            head = f"{i}. [{it.owner}] {it.objective}"
            lines.append(head)
            for pl in it.result_preview_lines:
                lines.append(pl)
            lines.append(f"file: {it.display_path}:{it.packet_start_line}")
            lines.append("")

    msg = "\n".join(lines).rstrip() + "\n"
    if max_len is None or len(msg) <= max_len:
        return msg

    clipped: list[str] = []
    chars = 0
    for ln in msg.splitlines():
        if chars + len(ln) + 1 > max_len - 50:
            clipped.append("…")
            break
        clipped.append(ln)
        chars += len(ln) + 1
    return "\n".join(clipped).rstrip() + "\n"


def _sanitize_outbound(text: str) -> str:
    # Prevent accidental mass-mentions in Discord (and keep Telegram clean too).
    # We keep it simple: break the "@" token.
    return (
        text.replace("@everyone", "@ everyone")
        .replace("@here", "@ here")
    )


def _infer_result_ok(preview_lines: list[str]) -> bool | None:
    for ln in preview_lines:
        s = ln.strip()
        if not s.lower().startswith("status:"):
            continue
        tail = s.split(":", 1)[1].strip().upper()
        if tail.startswith("OK"):
            return True
        if tail.startswith("FAILED") or tail.startswith("FAIL"):
            return False
    return None


def _miniapp_emit_queued(items: list[PacketQueued]) -> None:
    for it in items:
        # Feed-only: queued is not a first-class state, but this provides "after the fact" visibility.
        key = f"{it.inbox_path.resolve().as_posix()}:{it.packet_start_line}"
        qid = f"pktq_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"
        miniapp_emit(
            "response.created",
            agentId=it.owner.upper(),
            id=qid,
            text=f"[{it.owner.upper()}] queued: {it.objective}",
            extra={"source": "inbox_notifier", "kind": "queued"},
        )


def _miniapp_emit_results(items: list[PacketResult]) -> None:
    for it in items:
        owner = it.owner.upper()
        ok = _infer_result_ok(it.result_preview_lines)
        if ok is True:
            miniapp_emit("task.completed", agentId=owner, extra={"source": "inbox_notifier"})
        elif ok is False:
            miniapp_emit("task.failed", agentId=owner, extra={"source": "inbox_notifier"})

        key = f"{it.inbox_path.resolve().as_posix()}:{it.packet_start_line}"
        rid = f"pktres_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"
        status_txt = "OK" if ok is True else ("FAILED" if ok is False else "DONE")
        miniapp_emit(
            "response.created",
            agentId=owner,
            id=rid,
            text=f"[{owner}] {it.objective} -> {status_txt}",
            extra={"source": "inbox_notifier", "kind": "result"},
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Notify Cory on Telegram and/or Discord when new Task Packet Result blocks appear."
    )
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
    ap.add_argument(
        "--require-notify-discord",
        action="store_true",
        help="Only notify packets with `Notify: discord` (recommended for non-lab use).",
    )
    ap.add_argument(
        "--notify-queued",
        action="store_true",
        help="Also send one-time notifications when new packets are queued (Notify: <channel>, but no Result yet).",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    state = _load_state(state_path)

    queued, results = _find_packets(repo_root)

    # Only allow user-facing notifications when explicitly opted in, unless overridden.
    if args.require_notify_telegram:
        queued = [c for c in queued if "telegram" in _parse_notify_channels(c.notify)]
        results = [c for c in results if "telegram" in _parse_notify_channels(c.notify)]
    if args.require_notify_discord:
        queued = [c for c in queued if "discord" in _parse_notify_channels(c.notify)]
        results = [c for c in results if "discord" in _parse_notify_channels(c.notify)]

    def _state_has_result(channel: str, h: str) -> bool:
        if f"{channel}:{h}" in state:
            return True
        # Back-compat: older versions stored Telegram result hashes without a prefix.
        if channel == "telegram" and h in state:
            return True
        return False

    def _state_has_queued(channel: str, h: str) -> bool:
        if f"queued:{channel}:{h}" in state:
            return True
        # Back-compat: queued notifications were historically Telegram-only and channel-agnostic.
        if channel == "telegram" and f"queued:{h}" in state:
            return True
        return False

    queued_tg = [q for q in queued if "telegram" in _parse_notify_channels(q.notify)]
    queued_dc = [q for q in queued if "discord" in _parse_notify_channels(q.notify)]
    results_tg = [r for r in results if "telegram" in _parse_notify_channels(r.notify)]
    results_dc = [r for r in results if "discord" in _parse_notify_channels(r.notify)]

    new_queued_tg: list[PacketQueued] = []
    new_queued_dc: list[PacketQueued] = []
    if args.notify_queued:
        for q in queued_tg:
            if not _state_has_queued("telegram", q.queued_hash):
                new_queued_tg.append(q)
        for q in queued_dc:
            if not _state_has_queued("discord", q.queued_hash):
                new_queued_dc.append(q)

    new_results_tg: list[PacketResult] = [r for r in results_tg if not _state_has_result("telegram", r.result_hash)]
    new_results_dc: list[PacketResult] = [r for r in results_dc if not _state_has_result("discord", r.result_hash)]

    if not new_queued_tg and not new_results_tg and not new_queued_dc and not new_results_dc:
        print("NOTIFY_IDLE")
        return 0

    # Cap items per channel per run.
    cap = max(1, int(args.max_per_run))
    def _cap_lists(qs: list[PacketQueued], rs: list[PacketResult]) -> tuple[list[PacketQueued], list[PacketResult]]:
        if len(qs) + len(rs) <= cap:
            return qs, rs
        rs2 = rs[:cap]
        if len(rs2) < cap:
            qs2 = qs[: (cap - len(rs2))]
        else:
            qs2 = []
        return qs2, rs2

    new_queued_tg, new_results_tg = _cap_lists(new_queued_tg, new_results_tg)
    new_queued_dc, new_results_dc = _cap_lists(new_queued_dc, new_results_dc)

    dry_all = os.environ.get("NOTIFY_DRY_RUN", "").strip() == "1"
    suppress_tg = dry_all or _env_truthy("ORION_SUPPRESS_TELEGRAM") or _env_truthy("TELEGRAM_SUPPRESS")
    suppress_dc = dry_all or _env_truthy("ORION_SUPPRESS_DISCORD") or _env_truthy("DISCORD_SUPPRESS")

    if dry_all:
        if new_queued_tg or new_results_tg:
            print("TELEGRAM:")
            print(_format_message(queued=new_queued_tg, results=new_results_tg, max_len=3800))
        if new_queued_dc or new_results_dc:
            print("DISCORD:")
            print(_format_message(queued=new_queued_dc, results=new_results_dc, max_len=1900))
    else:
        if (new_queued_tg or new_results_tg) and not suppress_tg:
            chat_id = _get_telegram_chat_id()
            token = _get_telegram_bot_token()
            if not token:
                print(
                    "ERROR: Missing Telegram bot token (~/.openclaw/secrets/telegram.token or TELEGRAM_BOT_TOKEN).",
                    file=sys.stderr,
                )
                return 2

            msg = _sanitize_outbound(_format_message(queued=new_queued_tg, results=new_results_tg, max_len=3800))
            try:
                _telegram_send_message(chat_id=chat_id, token=token, text=msg)
            except urllib.error.HTTPError as e:
                print(f"ERROR: Telegram HTTP error: {e.code}", file=sys.stderr)
                return 2
            except Exception as e:
                print(f"ERROR: Telegram send failed: {e}", file=sys.stderr)
                return 2

        if (new_queued_dc or new_results_dc) and not suppress_dc:
            try:
                target = _get_discord_default_target(repo_root)
                msg = _sanitize_outbound(_format_message(queued=new_queued_dc, results=new_results_dc, max_len=1900))
                _discord_send_message(repo_root=repo_root, target=target, text=msg)
            except Exception as e:
                print(f"ERROR: Discord send failed: {e}", file=sys.stderr)
                return 2

    # Always emit Mini App events best-effort (even in dry-run mode).
    # This enables local loop testing without spamming Telegram.
    all_new_queued = new_queued_tg + [q for q in new_queued_dc if q not in new_queued_tg]
    all_new_results = new_results_tg + [r for r in new_results_dc if r not in new_results_tg]
    _miniapp_emit_queued(all_new_queued)
    _miniapp_emit_results(all_new_results)

    now = time.time()
    # In dry-run / suppression mode, we still advance state to avoid spamming during local loop testing.
    if new_results_tg or new_queued_tg:
        for it in new_results_tg:
            state[f"telegram:{it.result_hash}"] = now
            # Back-compat: keep the legacy Telegram key so older runs remain quiet.
            state[it.result_hash] = now
        for it in new_queued_tg:
            state[f"queued:telegram:{it.queued_hash}"] = now
            state[f"queued:{it.queued_hash}"] = now

    if new_results_dc or new_queued_dc:
        for it in new_results_dc:
            state[f"discord:{it.result_hash}"] = now
        for it in new_queued_dc:
            state[f"queued:discord:{it.queued_hash}"] = now

    # Bound state size to avoid unbounded growth.
    if len(state) > 5000:
        # Keep newest N based on timestamp values.
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:4000])

    _save_state(state_path, state)
    print("NOTIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
