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
    # When executed as `python3 scripts/notify_inbox_results.py`, sys.path[0] is `scripts/`,
    # so sibling imports work.
    from inbox_state import load_kv_state, parse_notify_channels, save_kv_state
except Exception:  # pragma: no cover
    # When imported as a module (unit tests), prefer package-style import.
    from scripts.inbox_state import load_kv_state, parse_notify_channels, save_kv_state  # type: ignore

try:
    from orion_policy_gate import evaluate_policy, load_rule_set, render_markdown
except Exception:  # pragma: no cover
    from scripts.orion_policy_gate import evaluate_policy, load_rule_set, render_markdown  # type: ignore

try:
    from outbound_text_guard import sanitize_outbound_text
except Exception:  # pragma: no cover
    from scripts.outbound_text_guard import sanitize_outbound_text  # type: ignore


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")
SEND_READY_HEADERS = {
    "TELEGRAM_MESSAGE:",
    "SLACK_MESSAGE:",
    "EMAIL_SUBJECT:",
    "INTERNAL:",
}


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


@dataclasses.dataclass(frozen=True)
class WorkflowAlert:
    workflow_id: str
    state: str
    state_reasons: tuple[str, ...]
    owners: tuple[str, ...]
    job_count: int
    alert_hash: str


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def _env_truthy(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}

def _parse_notify_channels(raw: str) -> set[str]:
    # Back-compat wrapper to keep internal calls stable.
    return parse_notify_channels(raw)


NOTIFY_OUTCOMES = {
    "delivered": "delivered",
    "suppressed": "suppressed",
    "failed": "failed-to-deliver",
}


def _state_has_seen(state: dict[str, float], *, channel: str, kind: str, digest: str) -> bool:
    pref = f"{channel}:{kind}:"
    if f"{pref}delivered:{digest}" in state:
        return True
    if f"{pref}suppressed:{digest}" in state:
        return True
    if f"{pref}failed:{digest}" in state:
        return True

    # Back-compat with legacy keys.
    if kind == "result":
        if channel == "telegram" and digest in state:
            return True
        if f"telegram:{digest}" in state:
            return True
    if kind == "queued":
        if channel == "telegram" and f"queued:{digest}" in state:
            return True
        if f"queued:{channel}:{digest}" in state:
            return True
    if kind == "workflow":
        if f"workflow:{channel}:{digest}" in state:
            return True
    return False


def _mark_delivery_outcome(
    state: dict[str, float],
    *,
    channel: str,
    kind: str,
    digest: str,
    outcome: str,
    now: float,
) -> None:
    attempts_key = f"{channel}:{kind}:attempts:{digest}"
    state[attempts_key] = float(state.get(attempts_key, 0.0) + 1.0)
    state[f"{channel}:{kind}:{outcome}:{digest}"] = now

    if kind == "result":
        if channel == "telegram":
            # Keep legacy telegram result keys so older runs continue to dedupe.
            state[digest] = now
            state[f"{channel}:{digest}"] = now
    elif kind == "queued":
        if channel == "telegram":
            state[f"queued:{digest}"] = now
        state[f"queued:{channel}:{digest}"] = now
    elif kind == "workflow":
        state[f"workflow:{channel}:{digest}"] = now


def _normalize_outcome(reason: str) -> str:
    return reason.replace("-", "_").replace(" ", "_").strip("_").lower()


def _outcome_error_class(err: Exception) -> str:
    if isinstance(err, urllib.error.HTTPError):
        return f"telegram_http_{err.code}"
    if isinstance(err, urllib.error.URLError):
        return "network_unreachable"
    msg = str(err).lower()
    if "no route to host" in msg or "connection refused" in msg:
        return "network_unreachable"
    return _normalize_outcome(err.__class__.__name__)


def _append_dead_letter(path: Path, *, reason_class: str, reason_detail: str, item_record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reason_class": reason_class,
        "reason_detail": reason_detail,
    }
    entry.update(item_record)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, sort_keys=True) + "\n")


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
    return load_kv_state(state_path)


def _save_state(state_path: Path, state: dict[str, float]) -> None:
    save_kv_state(state_path, state)


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
        # Prefer config-defined env vars when present (used by OpenClaw services/cron).
        env_target = (
            (cfg.get("env", {}) or {})
            .get("vars", {})
            .get("DISCORD_DEFAULT_POST_TARGET", "")
        )
        if isinstance(env_target, str) and env_target.strip():
            return env_target.strip()

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


def _find_packets_from_job_summary(repo_root: Path) -> tuple[list[PacketQueued], list[PacketResult]]:
    summary_path = repo_root / "tasks" / "JOBS" / "summary.json"
    if not summary_path.exists():
        return [], []

    try:
        payload = json.loads(_read_text(summary_path))
    except Exception:
        return [], []

    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        return [], []

    queued: list[PacketQueued] = []
    results: list[PacketResult] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue

        inbox = job.get("inbox", {})
        if not isinstance(inbox, dict):
            inbox = {}

        display_path = str(inbox.get("path") or "").strip()
        line_no = int(inbox.get("line") or 0)
        owner = str(job.get("owner") or "").strip() or "UNKNOWN"
        objective = str(job.get("objective") or "").strip() or "(no objective)"
        notify = str(job.get("notify") or "").strip().lower()
        state = str(job.get("state") or "").strip().lower()
        result = job.get("result", {})
        if not isinstance(result, dict):
            result = {}

        path = (repo_root / display_path).resolve() if display_path else repo_root
        if state == "queued":
            digest = str(job.get("queued_digest") or "").strip()
            if not digest:
                continue
            queued.append(
                PacketQueued(
                    inbox_path=path,
                    display_path=display_path or path.as_posix(),
                    packet_start_line=line_no,
                    owner=owner,
                    objective=objective,
                    notify=notify,
                    queued_hash=digest,
                )
            )
            continue

        result_status = str(result.get("status") or "").strip().lower()
        digest = str(job.get("result_digest") or "").strip()
        if result_status in {"ok", "failed", "blocked"} and digest:
            preview = result.get("preview_lines", [])
            if not isinstance(preview, list):
                preview = []
            sanitized_preview = [
                sanitize_outbound_text(str(line).rstrip())
                for line in preview
                if str(line).strip()
            ]
            results.append(
                PacketResult(
                    inbox_path=path,
                    display_path=display_path or path.as_posix(),
                    packet_start_line=line_no,
                    owner=owner,
                    objective=objective,
                    notify=notify,
                    result_hash=digest,
                    result_preview_lines=sanitized_preview or ["(Result present, but empty.)"],
                )
            )

    return queued, results


def _find_workflow_alerts(repo_root: Path) -> list[WorkflowAlert]:
    summary_path = repo_root / "tasks" / "JOBS" / "summary.json"
    if not summary_path.exists():
        return []
    try:
        payload = json.loads(_read_text(summary_path))
    except Exception:
        return []
    workflows = payload.get("workflows", []) if isinstance(payload, dict) else []
    alerts: list[WorkflowAlert] = []
    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        state = str(workflow.get("state") or "").strip().lower()
        if state not in {"blocked", "manual_required", "unsupported"}:
            continue
        workflow_id = str(workflow.get("workflow_id") or "").strip()
        state_reasons = tuple(
            sorted(
                str(reason).strip()
                for reason in workflow.get("state_reasons", [])
                if str(reason).strip()
            )
        ) if isinstance(workflow.get("state_reasons"), list) else ()
        owners = tuple(sorted(str(owner).strip() for owner in workflow.get("owners", []) if str(owner).strip()))
        job_count = int(workflow.get("job_count") or 0)
        digest = hashlib.sha256(
            f"{workflow_id}|{state}|{'|'.join(state_reasons)}|{'|'.join(owners)}|{job_count}".encode("utf-8", errors="replace")
        ).hexdigest()
        alerts.append(
            WorkflowAlert(
                workflow_id=workflow_id,
                state=state,
                state_reasons=state_reasons,
                owners=owners,
                job_count=job_count,
                alert_hash=digest,
            )
        )
    return alerts


def _format_message(
    *,
    queued: list[PacketQueued],
    results: list[PacketResult],
    workflow_alerts: list[WorkflowAlert],
    max_len: int | None = None,
) -> str:
    send_ready = [_extract_send_ready_telegram_message(it.result_preview_lines) for it in results]
    if (
        results
        and not queued
        and not workflow_alerts
        and all(body is not None for body in send_ready)
    ):
        msg = "\n\n".join(str(body).strip() for body in send_ready if body).rstrip() + "\n"
        if max_len is None or len(msg) <= max_len:
            return msg
        return _clip_message(msg, max_len=max_len)

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
            send_ready_body = _extract_send_ready_telegram_message(it.result_preview_lines)
            if send_ready_body is not None:
                lines.extend(send_ready_body.splitlines())
                lines.append("")
                continue

            head = f"{i}. [{it.owner}] {it.objective}"
            lines.append(head)
            for pl in it.result_preview_lines:
                lines.append(pl)
            lines.append(f"file: {it.display_path}:{it.packet_start_line}")
            lines.append("")

    if workflow_alerts:
        lines.append("Workflow alerts:")
        for i, item in enumerate(workflow_alerts, start=1):
            owners = ", ".join(item.owners) if item.owners else "unknown"
            lines.append(f"{i}. state={item.state} owners={owners} jobs={item.job_count}")
            if item.state_reasons:
                lines.append(f"reasons: {', '.join(item.state_reasons)}")
            lines.append(f"workflow: {item.workflow_id}")
        lines.append("")

    msg = "\n".join(lines).rstrip() + "\n"
    if max_len is None or len(msg) <= max_len:
        return msg

    return _clip_message(msg, max_len=max_len)


def _clip_message(msg: str, *, max_len: int) -> str:
    clipped: list[str] = []
    chars = 0
    for ln in msg.splitlines():
        if chars + len(ln) + 1 > max_len - 50:
            clipped.append("…")
            break
        clipped.append(ln)
        chars += len(ln) + 1
    return "\n".join(clipped).rstrip() + "\n"


def _extract_send_ready_telegram_message(preview_lines: list[str]) -> str | None:
    """
    Return the body of a SCRIBE-style Telegram draft, excluding internal handoff
    markers such as `Status: OK` and `TELEGRAM_MESSAGE:`.
    """
    start: int | None = None
    for idx, raw in enumerate(preview_lines):
        if raw.strip() == "TELEGRAM_MESSAGE:":
            start = idx + 1
            break
    if start is None:
        return None

    body: list[str] = []
    for raw in preview_lines[start:]:
        line = raw.rstrip()
        if line.strip() in SEND_READY_HEADERS:
            break
        body.append(line)

    text = "\n".join(body).strip()
    return text or None


def _sanitize_outbound(text: str) -> str:
    # Prevent accidental mass-mentions in Discord (and keep Telegram clean too).
    # We keep it simple: break the "@" token.
    return sanitize_outbound_text(
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


def _policy_history_paths(*, repo_root: Path, output_dir: str, channel: str, msg: str) -> tuple[Path, Path]:
    ts = time.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(msg.encode("utf-8", errors="replace")).hexdigest()[:10]
    out_dir = (repo_root / output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"policy-gate-notify-{channel}-{ts}-{digest}"
    return out_dir / f"{stem}.json", out_dir / f"{stem}.md"


def _gate_message(
    *,
    channel: str,
    message: str,
    rule_set,
    rule_path_output_dir: str,
    policy_mode: str,
    queued_count: int,
    result_count: int,
    workflow_alert_count: int = 0,
    repo_root: Path,
) -> tuple[bool, dict[str, object]]:
    payload = {
        "scope": "automated_summary",
        "request_text": "Automated delegated-result summary notification.",
        "response_text": message,
        "tags": [
            "automated_outbound",
            "delegated_result_summary",
            f"notify_{channel}",
        ],
        "metadata": {
            "source": "notify_inbox_results",
            "channel": channel,
            "queued_count": queued_count,
            "result_count": result_count,
            "workflow_alert_count": workflow_alert_count,
            "has_specialist_result": result_count > 0,
        },
    }

    # NOTE: policy mode for this script is passed in from CLI args (args.policy_mode),
    # and must be in-bounds by parser constraints.
    report = evaluate_policy(
        payload=payload,
        rule_set=rule_set,
        run_mode=policy_mode,
    )
    # Use local helper variables captured from surrounding main() scope.
    out_json, out_md = _policy_history_paths(
        repo_root=repo_root,
        output_dir=rule_path_output_dir,
        channel=channel,
        msg=message,
    )
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")
    blocked = bool((report.get("summary") or {}).get("blocked"))
    violations = int((report.get("summary") or {}).get("violations") or 0)
    if violations > 0:
        print(
            f"POLICY_{channel.upper()} violations={violations} blocked={blocked} report={out_json}",
            file=sys.stderr,
        )
    return blocked, {"json": str(out_json), "md": str(out_md), "report": report}


def _resolve_rules_path(repo_root: Path, configured_path: str) -> Path:
    raw = Path(configured_path)
    if raw.is_absolute():
        return raw.resolve()
    primary = (repo_root / raw).resolve()
    if primary.exists():
        return primary
    fallback = (Path(__file__).resolve().parent.parent / raw).resolve()
    return fallback


def main() -> int:
    env_policy_mode = os.environ.get("ORION_POLICY_MODE", "audit").strip().lower()
    if env_policy_mode not in {"audit", "block"}:
        env_policy_mode = "audit"

    ap = argparse.ArgumentParser(
        description="Notify Cory on Telegram and/or Discord when new Task Packet Result blocks appear."
    )
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--state-path",
        default="tmp/inbox_notify_state.json",
        help="State file path (default: tmp/inbox_notify_state.json)",
    )
    ap.add_argument(
        "--dead-letter-path",
        default="tmp/inbox_notify_dead_letters.jsonl",
        help="Dead-letter path for failed deliveries (default: tmp/inbox_notify_dead_letters.jsonl)",
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
    ap.add_argument(
        "--policy-rules",
        default="config/orion_policy_rules.json",
        help="Policy rules JSON path (default: config/orion_policy_rules.json)",
    )
    ap.add_argument(
        "--policy-mode",
        choices=["audit", "block"],
        default=env_policy_mode,
        help="Policy gate mode (default: ORION_POLICY_MODE or audit).",
    )
    ap.add_argument(
        "--policy-output-dir",
        default="eval/history",
        help="Directory for policy gate artifacts (default: eval/history)",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    dead_letter_path = (repo_root / args.dead_letter_path).resolve()
    state = _load_state(state_path)

    queued, results = _find_packets_from_job_summary(repo_root)
    if not queued and not results:
        queued, results = _find_packets(repo_root)
    workflow_alerts = _find_workflow_alerts(repo_root)

    if args.require_notify_telegram:
        queued = [c for c in queued if "telegram" in _parse_notify_channels(c.notify)]
        results = [c for c in results if "telegram" in _parse_notify_channels(c.notify)]
    if args.require_notify_discord:
        queued = [c for c in queued if "discord" in _parse_notify_channels(c.notify)]
        results = [c for c in results if "discord" in _parse_notify_channels(c.notify)]

    queued_tg = [q for q in queued if "telegram" in _parse_notify_channels(q.notify)]
    queued_dc = [q for q in queued if "discord" in _parse_notify_channels(q.notify)]
    results_tg = [r for r in results if "telegram" in _parse_notify_channels(r.notify)]
    results_dc = [r for r in results if "discord" in _parse_notify_channels(r.notify)]

    new_queued_tg: list[PacketQueued] = []
    new_queued_dc: list[PacketQueued] = []
    if args.notify_queued:
        for q in queued_tg:
            if not _state_has_seen(state, channel="telegram", kind="queued", digest=q.queued_hash):
                new_queued_tg.append(q)
        for q in queued_dc:
            if not _state_has_seen(state, channel="discord", kind="queued", digest=q.queued_hash):
                new_queued_dc.append(q)

    new_results_tg: list[PacketResult] = [r for r in results_tg if not _state_has_seen(state, channel="telegram", kind="result", digest=r.result_hash)]
    new_results_dc: list[PacketResult] = [r for r in results_dc if not _state_has_seen(state, channel="discord", kind="result", digest=r.result_hash)]

    new_alerts_tg = [item for item in workflow_alerts if not _state_has_seen(state, channel="telegram", kind="workflow", digest=item.alert_hash)]
    new_alerts_dc = [item for item in workflow_alerts if not _state_has_seen(state, channel="discord", kind="workflow", digest=item.alert_hash)]

    if not new_queued_tg and not new_results_tg and not new_queued_dc and not new_results_dc and not new_alerts_tg and not new_alerts_dc:
        print("NOTIFY_IDLE")
        return 0

    cap = max(1, int(args.max_per_run))

    def _cap_lists(
        qs: list[PacketQueued],
        rs: list[PacketResult],
        alerts: list[WorkflowAlert],
    ) -> tuple[list[PacketQueued], list[PacketResult], list[WorkflowAlert]]:
        if len(qs) + len(rs) + len(alerts) <= cap:
            return qs, rs, alerts
        rs2 = rs[:cap]
        remaining = max(0, cap - len(rs2))
        qs2 = qs[:remaining]
        remaining = max(0, remaining - len(qs2))
        alerts2 = alerts[:remaining]
        return qs2, rs2, alerts2

    new_queued_tg, new_results_tg, new_alerts_tg = _cap_lists(new_queued_tg, new_results_tg, new_alerts_tg)
    new_queued_dc, new_results_dc, new_alerts_dc = _cap_lists(new_queued_dc, new_results_dc, new_alerts_dc)

    dry_all = os.environ.get("NOTIFY_DRY_RUN", "").strip() == "1"
    suppress_tg = dry_all or _env_truthy("ORION_SUPPRESS_TELEGRAM") or _env_truthy("TELEGRAM_SUPPRESS")
    suppress_dc = dry_all or _env_truthy("ORION_SUPPRESS_DISCORD") or _env_truthy("DISCORD_SUPPRESS")

    policy_rules_path = _resolve_rules_path(repo_root, args.policy_rules)
    try:
        rule_set = load_rule_set(policy_rules_path)
    except Exception as e:
        print(f"ERROR: Could not load policy rules: {e}", file=sys.stderr)
        return 2

    tg_msg = ""
    dc_msg = ""
    if new_queued_tg or new_results_tg or new_alerts_tg:
        tg_msg = _sanitize_outbound(
            _format_message(queued=new_queued_tg, results=new_results_tg, workflow_alerts=new_alerts_tg, max_len=3800)
        )
    if new_queued_dc or new_results_dc or new_alerts_dc:
        dc_msg = _sanitize_outbound(
            _format_message(queued=new_queued_dc, results=new_results_dc, workflow_alerts=new_alerts_dc, max_len=1900)
        )

    def _item_record(kind: str, item: PacketQueued | PacketResult | WorkflowAlert, digest: str, channel: str) -> dict[str, object]:
        if kind == "workflow":
            return {
                "kind": kind,
                "channel": channel,
                "digest": digest,
                "workflow_id": item.workflow_id,
                "owners": list(item.owners),
                "state": item.state,
                "state_reasons": list(item.state_reasons),
                "job_count": item.job_count,
            }

        if isinstance(item, PacketQueued):
            return {
                "kind": kind,
                "channel": channel,
                "digest": digest,
                "owner": item.owner,
                "objective": item.objective,
                "path": item.display_path,
                "line_no": item.packet_start_line,
            }

        if isinstance(item, PacketResult):
            return {
                "kind": kind,
                "channel": channel,
                "digest": digest,
                "owner": item.owner,
                "objective": item.objective,
                "path": item.display_path,
                "line_no": item.packet_start_line,
            }

        # pragma: no cover
        raise RuntimeError("unsupported item")

    def _emit_channel_outcome(
        *,
        channel: str,
        items: list[tuple[str, str, PacketQueued | PacketResult | WorkflowAlert]],
        outcome: str,
        now_ts: float,
        reason_class: str | None = None,
        reason_detail: str | None = None,
    ) -> None:
        for kind, digest, item in items:
            _mark_delivery_outcome(
                state,
                channel=channel,
                kind=kind,
                digest=digest,
                outcome=outcome,
                now=now_ts,
            )
            if outcome != NOTIFY_OUTCOMES["failed"]:
                continue
            _append_dead_letter(
                dead_letter_path,
                reason_class=(reason_class or "unknown"),
                reason_detail=(reason_detail or ""),
                item_record=_item_record(kind, item, digest, channel),
            )

    def _events_from(
        queued: list[PacketQueued],
        results: list[PacketResult],
        alerts: list[WorkflowAlert],
    ) -> list[tuple[str, str, PacketQueued | PacketResult | WorkflowAlert]]:
        return [("queued", it.queued_hash, it) for it in queued] + [
            ("result", it.result_hash, it) for it in results
        ] + [("workflow", it.alert_hash, it) for it in alerts]

    tg_events = _events_from(new_queued_tg, new_results_tg, new_alerts_tg)
    dc_events = _events_from(new_queued_dc, new_results_dc, new_alerts_dc)

    fail_any = False
    now = time.time()

    def _gate(channel: str, message: str, queued_count: int, result_count: int) -> bool:
        blocked, _ = _gate_message(
            channel=channel,
            message=message,
            rule_set=rule_set,
            rule_path_output_dir=args.policy_output_dir,
            policy_mode=args.policy_mode,
            queued_count=queued_count,
            result_count=result_count,
            workflow_alert_count=len(new_alerts_tg if channel == "telegram" else new_alerts_dc),
            repo_root=repo_root,
        )
        if blocked:
            print(f"ERROR: {channel.upper()} outbound notification blocked by policy gate.", file=sys.stderr)
        return blocked

    tg_blocked = bool(tg_msg and _gate("telegram", tg_msg, len(new_queued_tg), len(new_results_tg)))
    dc_blocked = bool(dc_msg and _gate("discord", dc_msg, len(new_queued_dc), len(new_results_dc)))

    if tg_blocked:
        fail_any = True
        _emit_channel_outcome(
            channel="telegram",
            items=tg_events,
            outcome=NOTIFY_OUTCOMES["failed"],
            now_ts=now,
            reason_class="policy_block",
            reason_detail="policy_gate_blocked",
        )

    if dc_blocked:
        fail_any = True
        _emit_channel_outcome(
            channel="discord",
            items=dc_events,
            outcome=NOTIFY_OUTCOMES["failed"],
            now_ts=now,
            reason_class="policy_block",
            reason_detail="policy_gate_blocked",
        )

    if dry_all:
        if new_queued_tg or new_results_tg or new_alerts_tg:
            print("TELEGRAM:")
            print(tg_msg)
        if new_queued_dc or new_results_dc or new_alerts_dc:
            print("DISCORD:")
            print(dc_msg)

        if not tg_blocked:
            _emit_channel_outcome(
                channel="telegram",
                items=tg_events,
                outcome=NOTIFY_OUTCOMES["suppressed"],
                now_ts=now,
            )
        if not dc_blocked:
            _emit_channel_outcome(
                channel="discord",
                items=dc_events,
                outcome=NOTIFY_OUTCOMES["suppressed"],
                now_ts=now,
            )
    else:
        if (new_queued_tg or new_results_tg or new_alerts_tg) and not suppress_tg and not tg_blocked:
            try:
                chat_id = _get_telegram_chat_id()
                token = _get_telegram_bot_token()
                if not token:
                    raise RuntimeError("missing_telegram_bot_token")
                _telegram_send_message(chat_id=chat_id, token=token, text=tg_msg)
            except Exception as e:
                fail_any = True
                reason_class = _outcome_error_class(e)
                reason_detail = str(e)
                _emit_channel_outcome(
                    channel="telegram",
                    items=tg_events,
                    outcome=NOTIFY_OUTCOMES["failed"],
                    now_ts=now,
                    reason_class=reason_class,
                    reason_detail=reason_detail,
                )
            else:
                _emit_channel_outcome(
                    channel="telegram",
                    items=tg_events,
                    outcome=NOTIFY_OUTCOMES["delivered"],
                    now_ts=now,
                )
        elif not tg_blocked:
            _emit_channel_outcome(
                channel="telegram",
                items=tg_events,
                outcome=NOTIFY_OUTCOMES["suppressed"],
                now_ts=now,
            )

        if (new_queued_dc or new_results_dc or new_alerts_dc) and not suppress_dc and not dc_blocked:
            try:
                target = _get_discord_default_target(repo_root)
                _discord_send_message(repo_root=repo_root, target=target, text=dc_msg)
            except Exception as e:
                fail_any = True
                reason_class = _outcome_error_class(e)
                reason_detail = str(e)
                _emit_channel_outcome(
                    channel="discord",
                    items=dc_events,
                    outcome=NOTIFY_OUTCOMES["failed"],
                    now_ts=now,
                    reason_class=reason_class,
                    reason_detail=reason_detail,
                )
            else:
                _emit_channel_outcome(
                    channel="discord",
                    items=dc_events,
                    outcome=NOTIFY_OUTCOMES["delivered"],
                    now_ts=now,
                )
        elif not dc_blocked:
            _emit_channel_outcome(
                channel="discord",
                items=dc_events,
                outcome=NOTIFY_OUTCOMES["suppressed"],
                now_ts=now,
            )

    # Bound state size to avoid unbounded growth.
    if len(state) > 5000:
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:4000])

    _save_state(state_path, state)
    if fail_any:
        print("NOTIFY_FAILED")
        return 2

    print("NOTIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
