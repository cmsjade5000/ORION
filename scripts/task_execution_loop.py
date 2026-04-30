#!/usr/bin/env python3
"""
Closed-loop execution guard for Task Packets + ticket lanes.

Why this exists:
- Keep tasks/NOTES/{status,plan}.md continuously updated from actual repo state.
- Reconcile safe drift between ticket lane and Status field.
- Reconcile packet lifecycle with ticket lanes:
  - pending packet with ticket reference -> ticket should be in-progress
  - terminal packet result with ticket reference -> ticket should be testing
- Fail loudly for stale pending packets when strict mode is enabled.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Ensure the script's directory is on the Python path for local imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inbox_state import load_kv_state, save_kv_state, sha256_lines
from delegated_job_state import write_job_artifacts
from delegated_job_state import packet_content_id
from inbox_file_ops import append_packet_if_absent, atomic_write_text, ensure_packets_header, locked_file, strong_packet_identity


LANES = ("backlog", "in-progress", "testing", "done")
LANE_TO_STATUS = {
    "backlog": "queued",
    "in-progress": "in-progress",
    "testing": "testing",
    "done": "done",
}
CANONICAL_CRON_LABELS = {
    "assistant-agenda-refresh",
    "assistant-inbox-notify",
    "assistant-task-loop",
    "orion-error-review",
    "orion-ops-bundle",
    "orion-session-maintenance",
}

RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")
RE_RESULT_STATUS = re.compile(r"^\s*-?\s*Status:\s*(OK|FAILED|BLOCKED|CANCELLED)\b", re.IGNORECASE)
RE_TICKET_PATH = re.compile(r"(tasks/WORK/(?:backlog|in-progress|testing|done)/\d{4}-[a-z0-9][a-z0-9-]*\.md)")
NEXT_PACKET_PREFIX = "Next Packet "


@dataclasses.dataclass
class Ticket:
    path: Path
    relpath: str
    lane: str
    filename: str
    status: str
    title: str


@dataclasses.dataclass
class Packet:
    inbox_path: Path
    display_path: str
    start_line: int
    fields: dict[str, str]
    lines: list[str]
    pending_key: str
    result_status: str | None
    ticket_refs: list[str]
    next_packet_fields: dict[str, str]
    next_packet_sections: dict[str, list[str]]
    packet_id: str
    parent_packet_id: str
    root_packet_id: str
    workflow_id: str


@dataclasses.dataclass
class Action:
    kind: str
    ticket: str
    detail: str


@dataclasses.dataclass
class CommandSnapshot:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    data: dict | list | None


@dataclasses.dataclass
class OpenClawSnapshot:
    gateway_health: CommandSnapshot
    gateway_status: CommandSnapshot
    channels_status: CommandSnapshot
    tasks_list: CommandSnapshot
    tasks_audit: CommandSnapshot


def _safe_json(text: str) -> dict | list | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        stripped = text.strip()
        if not stripped:
            return None
        lines = stripped.splitlines()
        for idx, line in enumerate(lines):
            trimmed = line.lstrip()
            if not trimmed.startswith(("{", "[")):
                continue
            try:
                return json.loads("\n".join(lines[idx:]))
            except json.JSONDecodeError:
                pass
        for opener, closer in (("{", "}"), ("[", "]")):
            start = stripped.find(opener)
            end = stripped.rfind(closer)
            if start >= 0 and end > start:
                try:
                    return json.loads(stripped[start : end + 1])
                except json.JSONDecodeError:
                    continue
        return None


def _json_payload(stdout: str, stderr: str) -> dict | list | None:
    return _safe_json(stdout) or _safe_json(stderr)


def _split_packets(lines: list[str], *, start_line_offset: int = 0) -> list[tuple[int, list[str]]]:
    """Return (start_line_number, packet_lines) list for TASK_PACKET v1 blocks."""
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


def _packet_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in packet_lines[1:]:
        m = RE_KV.match(line)
        if not m:
            continue
        fields[m.group("key").strip()] = m.group("value").strip()
    return fields


def _packet_next_spec(packet_lines: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {
        "Success Criteria": [],
        "Constraints": [],
        "Inputs": [],
        "Risks": [],
        "Stop Gates": [],
        "Output Format": [],
    }
    current_section: str | None = None

    for line in packet_lines[1:]:
        m = RE_KV.match(line)
        if m:
            key = m.group("key").strip()
            value = m.group("value").strip()
            if not key.startswith(NEXT_PACKET_PREFIX):
                current_section = None
                continue
            next_key = key[len(NEXT_PACKET_PREFIX) :].strip()
            if next_key in sections:
                current_section = next_key
                if value:
                    sections[next_key].append(value)
            else:
                current_section = None
                fields[next_key] = value
            continue

        if not current_section:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            sections[current_section].append(stripped[2:].strip())
        else:
            sections[current_section].append(stripped)

    return fields, sections


def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in packet_lines:
        if ln.strip() == "Result:":
            break
        out.append(ln)
    return out


def _packet_result_status(packet_lines: list[str]) -> str | None:
    in_result = False
    for ln in packet_lines:
        s = ln.rstrip("\n")
        if s.strip() == "Result:":
            in_result = True
            continue
        if not in_result:
            continue
        m = RE_RESULT_STATUS.match(s.strip())
        if m:
            return m.group(1).upper()
    return None


def _extract_ticket_refs(packet_lines: list[str]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for ln in packet_lines:
        for m in RE_TICKET_PATH.finditer(ln):
            ref = m.group(1)
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _parse_ticket(path: Path, repo_root: Path, lane: str) -> Ticket:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = path.stem
    status = ""

    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip() or title
            break

    for ln in lines:
        if ln.startswith("Status:"):
            status = ln.split(":", 1)[1].strip()
            break

    return Ticket(
        path=path,
        relpath=str(path.relative_to(repo_root)),
        lane=lane,
        filename=path.name,
        status=status,
        title=title,
    )


def _load_tickets(repo_root: Path) -> dict[str, Ticket]:
    by_name: dict[str, Ticket] = {}
    for lane in LANES:
        lane_dir = repo_root / "tasks" / "WORK" / lane
        if not lane_dir.exists():
            continue
        for p in sorted(lane_dir.glob("*.md")):
            m = re.match(r"^\d{4}-[a-z0-9][a-z0-9-]*\.md$", p.name)
            if not m:
                continue
            t = _parse_ticket(p, repo_root, lane)
            by_name[t.filename] = t
    return by_name


def _packet_identity(packet_fields: dict[str, str], packet_id: str, pending_key: str) -> tuple[str, str]:
    idem_key = (packet_fields.get("Idempotency Key", "") or "").strip()
    if idem_key:
        return ("idempotency-key", idem_key)
    if packet_id:
        return ("packet-id", packet_id)
    return ("content-hash", pending_key)


def _packet_lookup_identity(packet: Packet) -> tuple[str, str]:
    return strong_packet_identity(fields=packet.fields, packet_before_result=_packet_before_result(packet.lines))


def _prefer_packet(candidate: Packet, current: Packet) -> bool:
    if len(candidate.lines) != len(current.lines):
        return len(candidate.lines) > len(current.lines)
    if candidate.inbox_path != current.inbox_path:
        return str(candidate.inbox_path) > str(current.inbox_path)
    return candidate.start_line > current.start_line


def _load_packets(repo_root: Path) -> list[Packet]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    out: list[Packet] = []
    seen: dict[tuple[str, str], tuple[int, Packet]] = {}
    if not inbox_dir.exists():
        return out

    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue

        text = inbox.read_text(encoding="utf-8")
        all_lines = text.splitlines()

        packets_header_idx = None
        for i, line in enumerate(all_lines):
            if line.strip() == "## Packets":
                packets_header_idx = i
                break

        start_idx = packets_header_idx + 1 if packets_header_idx is not None else 0
        packet_blocks = _split_packets(all_lines[start_idx:], start_line_offset=start_idx)

        try:
            display = str(inbox.relative_to(repo_root))
        except Exception:
            display = inbox.resolve().as_posix()

        for start_line, pkt_lines in packet_blocks:
            before = _packet_before_result(pkt_lines)
            fp = sha256_lines(before)
            result_status = _packet_result_status(pkt_lines)
            next_fields, next_sections = _packet_next_spec(pkt_lines)
            fields = _packet_fields(pkt_lines)
            packet_id = _packet_id(fields, before)
            packet = Packet(
                inbox_path=inbox,
                display_path=display,
                start_line=start_line,
                fields=fields,
                lines=pkt_lines,
                pending_key=f"pending:{fp}",
                result_status=result_status,
                ticket_refs=_extract_ticket_refs(pkt_lines),
                next_packet_fields=next_fields,
                next_packet_sections=next_sections,
                packet_id=packet_id,
                parent_packet_id=fields.get("Parent Packet ID", "").strip(),
                root_packet_id=fields.get("Root Packet ID", "").strip() or packet_id,
                workflow_id=fields.get("Workflow ID", "").strip() or fields.get("Root Packet ID", "").strip() or packet_id,
            )
            key = _packet_identity(fields, packet.packet_id, packet.pending_key)
            if key not in seen:
                seen[key] = (len(out), packet)
                out.append(packet)
                continue
            existing_idx, existing = seen[key]
            if _prefer_packet(packet, existing):
                out[existing_idx] = packet
                seen[key] = (existing_idx, packet)

    return out


def _rewrite_status(md: str, new_status: str) -> str:
    lines = md.splitlines()
    kept = [ln for ln in lines if not ln.startswith("Status:")]
    insert = f"Status: {new_status}"

    for i, ln in enumerate(kept):
        if ln.startswith("Owner:"):
            kept.insert(i + 1, insert)
            return "\n".join(kept).rstrip() + "\n"

    for i, ln in enumerate(kept):
        if ln.startswith("# "):
            kept.insert(i + 1, "")
            kept.insert(i + 2, insert)
            return "\n".join(kept).rstrip() + "\n"

    return (insert + "\n\n" + "\n".join(kept)).rstrip() + "\n"


def _append_note(md: str, note: str) -> str:
    if "## Notes" in md:
        head, tail = md.split("## Notes", 1)
        tail = tail.lstrip("\n")
        return f"{head}## Notes\n- {note}\n{tail}"
    return md.rstrip() + f"\n\n## Notes\n- {note}\n"


def _sanitize_status_fragment(value: str) -> str:
    return " ".join((value or "").split())


def _packet_id(fields: dict[str, str], packet_before_result: list[str]) -> str:
    raw = (fields.get("Packet ID", "") or "").strip()
    if raw:
        return raw
    return packet_content_id(fields, packet_before_result)


def _openclaw_capture_timeout_seconds() -> float:
    raw = (os.environ.get("TASK_EXECUTION_OPENCLAW_TIMEOUT_S") or "").strip()
    if not raw:
        return 8.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 8.0


def _run_capture(argv: list[str]) -> CommandSnapshot:
    try:
        cp = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=_openclaw_capture_timeout_seconds(),
        )
    except FileNotFoundError as exc:
        return CommandSnapshot(argv=argv, returncode=127, stdout="", stderr=str(exc), data=None)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timeout_note = (
            f"command timed out after {_openclaw_capture_timeout_seconds():.1f}s: {' '.join(argv)}"
        )
        stderr = ((stderr + "\n") if stderr else "") + timeout_note
        return CommandSnapshot(argv=argv, returncode=124, stdout=stdout, stderr=stderr, data=None)

    stdout = cp.stdout or ""
    stderr = cp.stderr or ""
    data: dict | list | None = None
    if stdout.strip() or stderr.strip():
        data = _json_payload(stdout, stderr)
    return CommandSnapshot(argv=argv, returncode=cp.returncode, stdout=stdout, stderr=stderr, data=data)


def _collect_openclaw_snapshot() -> OpenClawSnapshot:
    if os.environ.get("ORION_TASK_LOOP_SKIP_OPENCLAW_SNAPSHOT") == "1":
        skipped = CommandSnapshot(argv=[], returncode=0, stdout="", stderr="", data={})
        return OpenClawSnapshot(
            gateway_health=skipped,
            gateway_status=skipped,
            channels_status=skipped,
            tasks_list=skipped,
            tasks_audit=skipped,
        )

    commands = {
        "gateway_health": ["openclaw", "gateway", "health"],
        "gateway_status": ["openclaw", "gateway", "status", "--json"],
        "channels_status": ["openclaw", "channels", "status", "--probe", "--json"],
        "tasks_list": ["openclaw", "tasks", "list", "--json"],
        "tasks_audit": ["openclaw", "tasks", "audit", "--json"],
    }
    results: dict[str, CommandSnapshot] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
        future_map = {
            executor.submit(_run_capture, argv): name
            for name, argv in commands.items()
        }
        for future in concurrent.futures.as_completed(future_map):
            results[future_map[future]] = future.result()

    return OpenClawSnapshot(
        gateway_health=results["gateway_health"],
        gateway_status=results["gateway_status"],
        channels_status=results["channels_status"],
        tasks_list=results["tasks_list"],
        tasks_audit=results["tasks_audit"],
    )


def _task_summary(snapshot: OpenClawSnapshot) -> dict[str, object]:
    tasks_payload = snapshot.tasks_list.data if isinstance(snapshot.tasks_list.data, dict) else {}
    audit_payload = snapshot.tasks_audit.data if isinstance(snapshot.tasks_audit.data, dict) else {}
    if isinstance(snapshot.tasks_list.data, list):
        tasks = snapshot.tasks_list.data
    else:
        tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
    findings = audit_payload.get("findings", []) if isinstance(audit_payload, dict) else []
    summary = audit_payload.get("summary", {}) if isinstance(audit_payload, dict) else {}

    counts = {
        "total": len(tasks),
        "running": 0,
        "queued": 0,
        "succeeded": 0,
        "failed": 0,
        "timed_out": 0,
        "cancelled": 0,
        "lost": 0,
        "canonical_issues": 0,
        "approval_followups": 0,
    }
    recent_failures: list[str] = []
    stale_running: list[str] = []
    latest_canonical: dict[str, tuple[int, dict[str, object], str]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "")
        if status in counts:
            counts[status] += 1
        label = _sanitize_status_fragment(str(task.get("label") or task.get("task") or ""))
        error = _sanitize_status_fragment(str(task.get("error") or ""))
        terminal_summary = _sanitize_status_fragment(str(task.get("terminalSummary") or ""))
        task_text = "\n".join(part for part in (error, terminal_summary) if part)
        event_at = max(
            int(task.get("lastEventAt") or 0),
            int(task.get("endedAt") or 0),
            int(task.get("startedAt") or 0),
            int(task.get("createdAt") or 0),
        )
        if "approval-timeout" in task_text or "approval" in task_text.lower():
            counts["approval_followups"] += 1
        if label in CANONICAL_CRON_LABELS:
            current = latest_canonical.get(label)
            if current is None or event_at >= current[0]:
                latest_canonical[label] = (event_at, task, task_text)
        if label in CANONICAL_CRON_LABELS and status in {"failed", "timed_out", "lost"}:
            recent_failures.append(f"{label}: {status or 'unknown'}")
        elif status in {"failed", "timed_out", "lost"} and label:
            recent_failures.append(f"{label}: {status}")

    for label, (_event_at, task, task_text) in latest_canonical.items():
        status = str(task.get("status") or "")
        if status in {"failed", "timed_out", "lost"} or "no approval client" in task_text.lower():
            counts["canonical_issues"] += 1

    warnings = int(summary.get("warnings") or 0) if isinstance(summary, dict) else 0
    errors = int(summary.get("errors") or 0) if isinstance(summary, dict) else 0
    for finding in findings:
        if not isinstance(finding, dict) or str(finding.get("code") or "") != "stale_running":
            continue
        task = finding.get("task") if isinstance(finding.get("task"), dict) else {}
        label = str(task.get("label") or task.get("task") or task.get("taskId") or "unknown")
        detail = str(finding.get("detail") or "").strip()
        stale_running.append(f"{label}: {detail or 'stuck'}")
    return {
        "counts": counts,
        "audit_warnings": warnings,
        "audit_errors": errors,
        "audit_codes": summary.get("byCode", {}) if isinstance(summary, dict) else {},
        "recent_failures": recent_failures[:8],
        "findings_count": len(findings),
        "stale_running": stale_running[:6],
    }


def _channel_summary(snapshot: OpenClawSnapshot) -> dict[str, object]:
    payload = snapshot.channels_status.data if isinstance(snapshot.channels_status.data, dict) else {}
    channels = payload.get("channels", {}) if isinstance(payload, dict) else {}
    states: list[str] = []
    alerts: list[str] = []
    for channel_id in ("telegram", "discord", "slack", "mochat"):
        channel = channels.get(channel_id, {}) if isinstance(channels, dict) else {}
        if not isinstance(channel, dict):
            continue
        configured = bool(channel.get("configured"))
        running = bool(channel.get("running"))
        probe = channel.get("probe") if isinstance(channel.get("probe"), dict) else {}
        probe_ok = probe.get("ok") if isinstance(probe, dict) else None
        last_error = str(channel.get("lastError") or "").strip()
        if not configured:
            states.append(f"{channel_id}=off")
            continue
        if running and (probe_ok is True or probe_ok is None):
            states.append(f"{channel_id}=ok")
        elif last_error == "disabled":
            states.append(f"{channel_id}=disabled")
        else:
            states.append(f"{channel_id}=degraded")
            detail = last_error or str(probe.get("error") or "probe failed")
            alerts.append(f"{channel_id}: {detail}")
    return {"states": states, "alerts": alerts[:6]}


def _gateway_summary(snapshot: OpenClawSnapshot) -> dict[str, object]:
    payload = snapshot.gateway_status.data if isinstance(snapshot.gateway_status.data, dict) else {}
    rpc = payload.get("rpc", {}) if isinstance(payload, dict) else {}
    health = payload.get("health", {}) if isinstance(payload, dict) else {}
    service = payload.get("service", {}) if isinstance(payload, dict) else {}
    runtime = service.get("runtime", {}) if isinstance(service, dict) else {}
    config_audit = service.get("configAudit", {}) if isinstance(service, dict) else {}
    health_line = next((line.strip() for line in snapshot.gateway_health.stdout.splitlines() if line.strip()), "")
    return {
        "health_line": health_line,
        "rpc_ok": bool(rpc.get("ok")),
        "healthy": bool(health.get("healthy")),
        "runtime_status": str(runtime.get("status") or "unknown"),
        "config_audit_ok": config_audit.get("ok") if isinstance(config_audit.get("ok"), bool) else None,
    }


def _update_ticket_status(ticket: Ticket, new_status: str) -> None:
    raw = ticket.path.read_text(encoding="utf-8")
    out = _rewrite_status(raw, new_status)
    if out != raw:
        ticket.path.write_text(out, encoding="utf-8")
    ticket.status = new_status


def _move_ticket_lane(
    *, repo_root: Path, ticket: Ticket, to_lane: str, reason: str
) -> Ticket:
    if ticket.lane == to_lane:
        expected = LANE_TO_STATUS[to_lane]
        if ticket.status != expected:
            _update_ticket_status(ticket, expected)
        return ticket

    dest_dir = repo_root / "tasks" / "WORK" / to_lane
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / ticket.filename

    raw = ticket.path.read_text(encoding="utf-8")
    out = _rewrite_status(raw, LANE_TO_STATUS[to_lane])
    today = dt.datetime.now().strftime("%Y-%m-%d")
    out = _append_note(out, f"{today}: moved to {to_lane} ({reason})")
    ticket.path.write_text(out, encoding="utf-8")
    ticket.path.rename(dest)

    new_ticket = _parse_ticket(dest, repo_root, to_lane)
    return new_ticket


def _next_packet_lines(packet: Packet) -> list[str] | None:
    fields = packet.next_packet_fields
    if not fields:
        return None
    owner = fields.get("Owner", "").strip()
    requester = fields.get("Requester", "").strip()
    objective = fields.get("Objective", "").strip()
    if not owner or not requester or not objective:
        return None

    required_section_order = [
        "Success Criteria",
        "Constraints",
        "Inputs",
        "Risks",
        "Stop Gates",
        "Output Format",
    ]
    for section in required_section_order:
        items = [item for item in packet.next_packet_sections.get(section, []) if item.strip()]
        if not items:
            return None

    normalized_fields = dict(fields)
    if not normalized_fields.get("Idempotency Key", "").strip():
        normalized_fields["Idempotency Key"] = _generated_next_packet_idempotency_key(packet)
    normalized_fields.setdefault("Parent Packet ID", packet.packet_id)
    normalized_fields.setdefault("Root Packet ID", packet.root_packet_id or packet.packet_id)
    normalized_fields.setdefault("Workflow ID", packet.workflow_id or packet.root_packet_id or packet.packet_id)
    normalized_fields.setdefault(
        "Packet ID",
        packet_content_id({"Idempotency Key": normalized_fields["Idempotency Key"]}, []),
    )

    lines = ["TASK_PACKET v1"]
    base_field_order = ["Owner", "Requester", "Objective"]
    optional_fields = [key for key in normalized_fields.keys() if key not in base_field_order]
    for key in base_field_order + sorted(optional_fields):
        value = normalized_fields.get(key, "").strip()
        if value:
            lines.append(f"{key}: {value}")
    lines.append(f"Handoff Source: {packet.display_path}:{packet.start_line}")
    for section in required_section_order:
        lines.append(f"{section}:")
        for item in packet.next_packet_sections.get(section, []):
            if item.strip():
                lines.append(f"- {item.strip()}")
    return lines


def _next_packet_should_fire(packet: Packet) -> bool:
    if not packet.next_packet_fields:
        return False
    result_status = (packet.result_status or "").strip().upper()
    if not result_status:
        return False
    trigger = (packet.next_packet_fields.get("On Result", "OK") or "OK").strip().upper()
    if trigger == "ANY":
        return True
    return result_status == trigger


def _generated_next_packet_idempotency_key(packet: Packet) -> str:
    lines = _packet_before_result(packet.lines)
    next_lines: list[str] = []
    for key in sorted(packet.next_packet_fields.keys()):
        next_lines.append(f"{key}: {packet.next_packet_fields[key]}")
    for key in sorted(packet.next_packet_sections.keys()):
        next_lines.append(f"{key}:")
        next_lines.extend(packet.next_packet_sections[key])
    return "handoff:" + packet_content_id({}, lines + next_lines)


def _append_next_packet_if_needed(repo_root: Path, packet: Packet) -> Action | None:
    if not _next_packet_should_fire(packet):
        return None
    lines = _next_packet_lines(packet)
    if not lines:
        return None

    owner = packet.next_packet_fields.get("Owner", "").strip().upper()
    if not owner:
        return None
    target = repo_root / "tasks" / "INBOX" / f"{owner}.md"
    handoff_source = f"Handoff Source: {packet.display_path}:{packet.start_line}"
    if not append_packet_if_absent(target, owner=owner, packet_lines=lines, source_markers=[handoff_source]):
        return None
    return Action(
        kind="next-packet",
        ticket=owner,
        detail=f"appended handoff from {packet.display_path}:{packet.start_line} to tasks/INBOX/{owner}.md",
    )


def _stale_recovery_target(packet: Packet) -> tuple[str, str]:
    owner = (packet.fields.get("Owner", "") or packet.inbox_path.stem).strip().upper()
    if owner in {"ATLAS", "ORION"}:
        return "ORION", "ORION"
    return "ATLAS", "ORION"


def _stale_recovery_packet_lines(packet: Packet, *, age_h: float) -> list[str]:
    target_owner, requester = _stale_recovery_target(packet)
    recovery_key = f"recovery:stale:{packet.packet_id}"
    objective = (
        f"Recover stale delegated workflow for [{packet.fields.get('Owner', packet.inbox_path.stem.upper())}] "
        f"{packet.fields.get('Objective', '(no objective)')}"
    )
    return [
        "TASK_PACKET v1",
        f"Owner: {target_owner}",
        f"Requester: {requester}",
        "Notify: telegram",
        f"Idempotency Key: {recovery_key}",
        f"Packet ID: {packet_content_id({'Idempotency Key': recovery_key}, [])}",
        f"Parent Packet ID: {packet.packet_id}",
        f"Root Packet ID: {packet.root_packet_id or packet.packet_id}",
        f"Workflow ID: {packet.workflow_id or packet.root_packet_id or packet.packet_id}",
        f"Objective: {objective}",
        "Success Criteria:",
        "- Determine why the delegated workflow stalled.",
        "- Either resume the workflow or leave a terminal recovery result with a concrete blocker.",
        "Constraints:",
        "- Prefer reversible recovery steps first.",
        "- Preserve packet and ticket history.",
        "Inputs:",
        f"- Source packet: {packet.display_path}:{packet.start_line}",
        f"- Current age: {age_h:.1f}h stale",
        "Risks:",
        "- Duplicate recovery work if this packet is appended more than once.",
        "Stop Gates:",
        "- Any destructive or irreversible change without fresh evidence.",
        "Output Format:",
        "- Short checklist with resume path or blocker.",
    ]


def _append_stale_recovery_packet_if_needed(repo_root: Path, packet: Packet, *, age_h: float) -> Action | None:
    owner, _requester = _stale_recovery_target(packet)
    target = repo_root / "tasks" / "INBOX" / f"{owner}.md"
    lines = _stale_recovery_packet_lines(packet, age_h=age_h)
    source_marker = f"Recovery Source: {packet.display_path}:{packet.start_line}"
    if not append_packet_if_absent(target, owner=owner, packet_lines=lines + [source_marker], source_markers=[source_marker]):
        return None
    return Action(
        kind="stale-escalation",
        ticket=owner,
        detail=f"appended recovery packet for {packet.display_path}:{packet.start_line}",
    )


def _packet_has_non_empty_result(packet_lines: list[str]) -> bool:
    start = None
    for idx, line in enumerate(packet_lines):
        if line.strip() == "Result:":
            start = idx
            break
    return start is not None and any(line.strip() for line in packet_lines[start + 1 :])


def _should_cancel_superseded_packet(packet: Packet, terminal_by_id: dict[str, Packet], terminal_roots: set[str]) -> Packet | None:
    if packet.result_status is not None:
        return None
    parent = packet.parent_packet_id.strip()
    root = packet.root_packet_id.strip()
    source = terminal_by_id.get(parent)
    if source is None and root and root in terminal_roots:
        source = terminal_by_id.get(root)
    if source is None:
        return None
    idem = (packet.fields.get("Idempotency Key", "") or "").strip().lower()
    objective = (packet.fields.get("Objective", "") or "").strip().lower()
    if idem.startswith("recovery:") or "recover stale" in objective or "triage" in objective:
        return source
    return None


def _append_superseded_result(repo_root: Path, packet: Packet, source: Packet) -> bool:
    identity = _packet_lookup_identity(packet)
    lock_path = packet.inbox_path.with_suffix(packet.inbox_path.suffix + ".lock")
    result_lines = [
        "",
        "Result:",
        "Status: CANCELLED",
        "Reason: superseded_by_terminal_source",
        f"Source Packet: {source.display_path}:{source.start_line}",
        f"Source Status: {source.result_status}",
        "Next step (if any):",
        "  - None.",
        "",
    ]
    with locked_file(lock_path):
        file_lines = ensure_packets_header(
            packet.inbox_path.read_text(encoding="utf-8").splitlines()
            if packet.inbox_path.exists()
            else [],
            owner=packet.inbox_path.stem.upper(),
        )
        packets_header_idx = next((idx for idx, line in enumerate(file_lines) if line.strip() == "## Packets"), None)
        if packets_header_idx is None:
            return False
        packet_blocks = _split_packets(file_lines[packets_header_idx + 1 :], start_line_offset=packets_header_idx + 1)
        for start_line, pkt_lines in packet_blocks:
            fields = _packet_fields(pkt_lines)
            candidate_identity = strong_packet_identity(fields=fields, packet_before_result=_packet_before_result(pkt_lines))
            if candidate_identity != identity:
                continue
            if _packet_has_non_empty_result(pkt_lines):
                return False
            packet_start_idx = start_line - 1
            packet_end_idx = packet_start_idx + len(pkt_lines)
            atomic_write_text(packet.inbox_path, "\n".join(file_lines[:packet_end_idx] + result_lines + file_lines[packet_end_idx:]).rstrip() + "\n")
            return True
    return False


def _write_status_md(
    *,
    repo_root: Path,
    now_local: dt.datetime,
    lane_counts: dict[str, int],
    pending_packets: list[Packet],
    terminal_packets: list[Packet],
    stale_pending: list[tuple[Packet, float]],
    actions: list[Action],
    stale_hours: float,
    openclaw_snapshot: OpenClawSnapshot,
) -> None:
    p = repo_root / "tasks" / "NOTES" / "status.md"
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Status")
    lines.append("")
    lines.append(f"- Updated: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(
        "- Ticket lanes: "
        + " | ".join(f"{lane}={lane_counts.get(lane, 0)}" for lane in LANES)
    )
    lines.append(
        f"- Inbox packets: pending={len(pending_packets)} terminal={len(terminal_packets)}"
    )
    lines.append(
        f"- Stale pending (>{stale_hours:.1f}h): {len(stale_pending)}"
    )
    lines.append("")

    gateway_summary = _gateway_summary(openclaw_snapshot)
    channel_summary = _channel_summary(openclaw_snapshot)
    task_summary = _task_summary(openclaw_snapshot)

    lines.append("## OpenClaw Runtime")
    lines.append(
        f"- Gateway: {gateway_summary['health_line'] or 'unavailable'} | rpc_ok={gateway_summary['rpc_ok']} | healthy={gateway_summary['healthy']} | runtime={gateway_summary['runtime_status']} | config_audit_ok={gateway_summary['config_audit_ok']}"
    )
    if channel_summary["states"]:
        lines.append("- Channels: " + " | ".join(channel_summary["states"]))
    else:
        lines.append("- Channels: unavailable")
    if channel_summary["alerts"]:
        for alert in channel_summary["alerts"]:
            lines.append(f"- Alert: {alert}")
    else:
        lines.append("- Alert: none")
    lines.append("")

    counts = task_summary["counts"]
    lines.append("## OpenClaw Tasks")
    lines.append(
        "- Ledger: "
        f"total={counts['total']} running={counts['running']} queued={counts['queued']} "
        f"succeeded={counts['succeeded']} failed={counts['failed']} timed_out={counts['timed_out']} lost={counts['lost']}"
    )
    lines.append(
        "- Audit: "
        f"warnings={task_summary['audit_warnings']} errors={task_summary['audit_errors']} findings={task_summary['findings_count']}"
    )
    lines.append(
        "- Canonical cron issues: "
        f"{counts['canonical_issues']} | stale_running={len(task_summary['stale_running'])} | approval_followups={counts['approval_followups']}"
    )
    if task_summary["recent_failures"]:
        for failure in task_summary["recent_failures"]:
            lines.append(f"- Recent failure: {failure}")
    else:
        lines.append("- Recent failure: none")
    if task_summary["stale_running"]:
        for entry in task_summary["stale_running"]:
            lines.append(f"- Stale running: {entry}")
    else:
        lines.append("- Stale running: none")
    lines.append("")

    lines.append("## Stale Pending Packets")
    if stale_pending:
        for pkt, age_h in stale_pending[:20]:
            owner = pkt.fields.get("Owner", pkt.inbox_path.stem.upper())
            objective = pkt.fields.get("Objective", "(no objective)")
            lines.append(
                f"- [{owner}] {objective} ({pkt.display_path}:{pkt.start_line}, age={age_h:.1f}h)"
            )
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Reconcile Actions")
    if actions:
        for a in actions[:50]:
            lines.append(f"- {a.kind}: {a.ticket} ({a.detail})")
    else:
        lines.append("- none")
    lines.append("")

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_plan_md(
    *,
    repo_root: Path,
    now_local: dt.datetime,
    tickets: dict[str, Ticket],
    stale_pending: list[tuple[Packet, float]],
) -> None:
    p = repo_root / "tasks" / "NOTES" / "plan.md"
    p.parent.mkdir(parents=True, exist_ok=True)

    in_progress = sorted([t for t in tickets.values() if t.lane == "in-progress"], key=lambda x: x.filename)
    backlog = sorted([t for t in tickets.values() if t.lane == "backlog"], key=lambda x: x.filename)

    lines: list[str] = []
    lines.append("# Plan")
    lines.append("")
    lines.append(f"- Refreshed: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append("")

    lines.append("## Active")
    if in_progress:
        for t in in_progress[:10]:
            lines.append(f"- Continue {t.filename} ({t.title})")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Queue")
    if backlog:
        for t in backlog[:10]:
            lines.append(f"- Next {t.filename} ({t.title})")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Attention")
    if stale_pending:
        for pkt, age_h in stale_pending[:10]:
            owner = pkt.fields.get("Owner", pkt.inbox_path.stem.upper())
            objective = pkt.fields.get("Objective", "(no objective)")
            lines.append(
                f"- Resolve stale packet [{owner}] {objective} ({pkt.display_path}:{pkt.start_line}, age={age_h:.1f}h)"
            )
    else:
        lines.append("- none")
    lines.append("")

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run(
    repo_root: Path,
    *,
    apply_changes: bool,
    stale_hours: float,
    strict_stale: bool,
    state_path: Path,
) -> int:
    now_ts = time.time()
    now_local = dt.datetime.now().astimezone()

    tickets = _load_tickets(repo_root)
    packets = _load_packets(repo_root)
    openclaw_snapshot = _collect_openclaw_snapshot()

    pending_packets = [p for p in packets if p.result_status is None]
    terminal_packets = [p for p in packets if p.result_status is not None]

    state = load_kv_state(state_path)

    # Track first-seen timestamps for pending packets.
    pending_keys = {p.pending_key for p in pending_packets}
    for pkt in pending_packets:
        if pkt.pending_key not in state:
            state[pkt.pending_key] = now_ts

    # Clean up resolved pending keys.
    for key in list(state.keys()):
        if not key.startswith("pending:"):
            continue
        if key not in pending_keys:
            del state[key]

    stale_pending: list[tuple[Packet, float]] = []
    for pkt in pending_packets:
        started = state.get(pkt.pending_key, now_ts)
        age_h = max(0.0, (now_ts - started) / 3600.0)
        if age_h > stale_hours:
            stale_pending.append((pkt, age_h))

    actions: list[Action] = []

    # Status reconciliation from lane -> Status field.
    for t in sorted(tickets.values(), key=lambda x: x.filename):
        expected = LANE_TO_STATUS[t.lane]
        if t.status != expected:
            actions.append(Action(kind="status-sync", ticket=t.filename, detail=f"{t.status or '(missing)'} -> {expected}"))
            if apply_changes:
                _update_ticket_status(t, expected)

    # Build desired lane state from packet lifecycle.
    desired_lanes: dict[str, tuple[str, str]] = {}

    for pkt in terminal_packets:
        for ref in pkt.ticket_refs:
            base = os.path.basename(ref)
            if base in tickets:
                desired_lanes.setdefault(base, ("testing", f"terminal result in {pkt.display_path}:{pkt.start_line}"))

    for pkt in pending_packets:
        for ref in pkt.ticket_refs:
            base = os.path.basename(ref)
            if base in tickets:
                desired_lanes[base] = ("in-progress", f"pending packet in {pkt.display_path}:{pkt.start_line}")

    for filename, (target_lane, reason) in sorted(desired_lanes.items()):
        t = tickets.get(filename)
        if not t:
            continue
        if t.lane == target_lane:
            continue
        # Safe reconcile policy: only move backlog/in-progress/testing between active lanes.
        # Do not auto-reopen done tickets.
        if t.lane == "done":
            continue

        actions.append(Action(kind="lane-move", ticket=t.filename, detail=f"{t.lane} -> {target_lane}; {reason}"))
        if apply_changes:
            moved = _move_ticket_lane(repo_root=repo_root, ticket=t, to_lane=target_lane, reason=reason)
            tickets[filename] = moved

    for pkt in terminal_packets:
        if not pkt.next_packet_fields:
            continue
        if not _next_packet_should_fire(pkt):
            continue
        next_owner = pkt.next_packet_fields.get("Owner", "").strip().upper() or "(unknown)"
        action = Action(
            kind="next-packet",
            ticket=next_owner,
            detail=f"handoff from {pkt.display_path}:{pkt.start_line}",
        )
        if apply_changes:
            appended = _append_next_packet_if_needed(repo_root, pkt)
            if appended is not None:
                action = appended
            else:
                action = Action(
                    kind="next-packet-skip",
                    ticket=next_owner,
                    detail=f"existing handoff or invalid spec from {pkt.display_path}:{pkt.start_line}",
                )
        actions.append(action)

    terminal_by_id: dict[str, Packet] = {}
    terminal_roots: set[str] = set()
    for pkt in terminal_packets:
        if pkt.packet_id:
            terminal_by_id[pkt.packet_id] = pkt
        if pkt.root_packet_id:
            terminal_roots.add(pkt.root_packet_id)

    for pkt in list(pending_packets):
        source = _should_cancel_superseded_packet(pkt, terminal_by_id, terminal_roots)
        if source is None:
            continue
        actions.append(
            Action(
                kind="terminal-propagation",
                ticket=pkt.fields.get("Owner", pkt.inbox_path.stem.upper()),
                detail=f"{pkt.display_path}:{pkt.start_line} superseded by {source.display_path}:{source.start_line}",
            )
        )
        if apply_changes:
            _append_superseded_result(repo_root, pkt, source)

    for pkt, age_h in sorted(stale_pending, key=lambda item: item[1], reverse=True):
        if _should_cancel_superseded_packet(pkt, terminal_by_id, terminal_roots) is not None:
            continue
        if (pkt.fields.get("Idempotency Key", "") or "").strip().startswith("recovery:"):
            continue
        target_owner, _ = _stale_recovery_target(pkt)
        action = Action(
            kind="stale-escalation",
            ticket=target_owner,
            detail=f"recovery packet for {pkt.display_path}:{pkt.start_line} age={age_h:.1f}h",
        )
        if apply_changes:
            appended = _append_stale_recovery_packet_if_needed(repo_root, pkt, age_h=age_h)
            if appended is not None:
                action = appended
            else:
                action = Action(
                    kind="stale-escalation-skip",
                    ticket=target_owner,
                    detail=f"existing recovery packet for {pkt.display_path}:{pkt.start_line}",
                )
        actions.append(action)

    if apply_changes:
        packets = _load_packets(repo_root)
        pending_packets = [p for p in packets if p.result_status is None]
        terminal_packets = [p for p in packets if p.result_status is not None]
        pending_keys = {p.pending_key for p in pending_packets}
        for pkt in pending_packets:
            if pkt.pending_key not in state:
                state[pkt.pending_key] = now_ts
        for key in list(state.keys()):
            if key.startswith("pending:") and key not in pending_keys:
                del state[key]
        stale_pending = []
        for pkt in pending_packets:
            started = state.get(pkt.pending_key, now_ts)
            age_h = max(0.0, (now_ts - started) / 3600.0)
            if age_h > stale_hours:
                stale_pending.append((pkt, age_h))

    # Write notes after reconcile pass.
    lane_counts = {lane: 0 for lane in LANES}
    for t in tickets.values():
        lane_counts[t.lane] += 1

    _write_status_md(
        repo_root=repo_root,
        now_local=now_local,
        lane_counts=lane_counts,
        pending_packets=pending_packets,
        terminal_packets=terminal_packets,
        stale_pending=sorted(stale_pending, key=lambda x: x[1], reverse=True),
        actions=actions,
        stale_hours=stale_hours,
        openclaw_snapshot=openclaw_snapshot,
    )
    _write_plan_md(
        repo_root=repo_root,
        now_local=now_local,
        tickets=tickets,
        stale_pending=sorted(stale_pending, key=lambda x: x[1], reverse=True),
    )
    write_job_artifacts(
        repo_root=repo_root,
        packets=packets,
        ticket_map=tickets,
        pending_since_by_key={key: value for key, value in state.items() if key.startswith("pending:")},
        stale_threshold_hours=stale_hours,
        now_ts=now_ts,
    )

    # Bound state size.
    if len(state) > 5000:
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:4000])
    save_kv_state(state_path, state)

    stale_count = len(stale_pending)
    action_count = len(actions)
    if strict_stale and stale_count > 0:
        print(f"TASK_LOOP_STALE stale={stale_count} actions={action_count} apply={int(apply_changes)}")
        return 2

    print(f"TASK_LOOP_OK stale={stale_count} actions={action_count} apply={int(apply_changes)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Closed-loop reconcile for inbox packets, ticket lanes, and notes.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--state-path",
        default="tmp/task_execution_loop_state.json",
        help="State file path (default: tmp/task_execution_loop_state.json)",
    )
    ap.add_argument("--stale-hours", type=float, default=24.0, help="Pending-packet stale threshold in hours.")
    ap.add_argument("--strict-stale", action="store_true", help="Exit non-zero when stale pending packets exist.")
    ap.add_argument("--apply", action="store_true", help="Apply status/lane reconciliation changes.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    return run(
        repo_root,
        apply_changes=bool(args.apply),
        stale_hours=max(0.1, float(args.stale_hours)),
        strict_stale=bool(args.strict_stale),
        state_path=state_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
