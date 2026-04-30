#!/usr/bin/env python3
"""
Durable delegated-job artifacts derived from inbox Task Packets.

Why this exists:
- Packet state currently lives across inbox markdown, task-loop state, and ticket lanes.
- ORION needs one durable per-job artifact to understand whether delegated work is
  queued, moving, blocked, or waiting on verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from inbox_state import parse_notify_channels, sha256_lines
    from inbox_file_ops import atomic_write_text
    from outbound_text_guard import sanitize_outbound_text
except Exception:  # pragma: no cover
    from scripts.inbox_state import parse_notify_channels, sha256_lines  # type: ignore
    from scripts.inbox_file_ops import atomic_write_text  # type: ignore
    from scripts.outbound_text_guard import sanitize_outbound_text  # type: ignore


def packet_content_id(fields: dict[str, str], packet_before_result: list[str]) -> str:
    raw = (fields.get("Idempotency Key", "") or "").strip()
    if raw:
        return "ik-" + sha256_lines([raw])[:16]
    return "pkt-" + sha256_lines(packet_before_result)[:16]


def infer_job_state(
    *,
    result_status: str | None,
    ticket_lanes: list[str],
    pending_since_ts: float | None,
    stale_threshold_hours: float,
    now_ts: float,
) -> str:
    normalized = (result_status or "").strip().upper()
    if normalized == "CANCELLED":
        return "cancelled"
    if normalized in {"FAILED", "BLOCKED"}:
        return "blocked"
    if normalized == "OK":
        if "done" in ticket_lanes:
            return "complete"
        if not ticket_lanes:
            return "complete"
        return "pending_verification"

    if ticket_lanes:
        if "testing" in ticket_lanes:
            return "pending_verification"
        if "done" in ticket_lanes:
            return "complete"
        if "in-progress" in ticket_lanes:
            return "in_progress"

    if pending_since_ts is not None:
        age_h = max(0.0, (now_ts - pending_since_ts) / 3600.0)
        if age_h > stale_threshold_hours:
            return "blocked"
        return "queued"

    return "queued"


def infer_job_state_reason(
    *,
    result_status: str | None,
    ticket_lanes: list[str],
    pending_since_ts: float | None,
    stale_threshold_hours: float,
    now_ts: float,
) -> str:
    normalized = (result_status or "").strip().upper()
    if normalized == "CANCELLED":
        return "result_cancelled"
    if normalized == "FAILED":
        return "result_failed"
    if normalized == "BLOCKED":
        return "result_blocked"
    if normalized == "OK":
        if "done" in ticket_lanes:
            return "result_ok_ticket_done"
        if not ticket_lanes:
            return "result_ok_no_ticket_refs"
        return "result_ok_waiting_done"

    if ticket_lanes:
        if "testing" in ticket_lanes:
            return "ticket_testing"
        if "done" in ticket_lanes:
            return "ticket_done"
        if "in-progress" in ticket_lanes:
            return "ticket_in_progress"

    if pending_since_ts is not None:
        age_h = max(0.0, (now_ts - pending_since_ts) / 3600.0)
        if age_h > stale_threshold_hours:
            return "stale_pending"
        return "pending_packet"

    return "packet_present"


def infer_workflow_state(states: list[str]) -> str:
    normalized = [str(state or "").strip() for state in states if str(state or "").strip()]
    if not normalized:
        return "queued"
    if any(state in {"blocked", "manual_required", "unsupported"} for state in normalized):
        return "blocked"
    if all(state == "complete" for state in normalized):
        return "complete"
    if any(state in {"in_progress", "pending_verification"} for state in normalized):
        return "in_progress"
    return "queued"


def normalize_result_status(result_status: str | None) -> str:
    normalized = (result_status or "").strip().upper()
    if normalized in {"OK", "FAILED", "BLOCKED", "CANCELLED"}:
        return normalized.lower()
    return "pending"


def normalize_notify(raw_notify: str) -> tuple[str, list[str]]:
    channels = sorted(parse_notify_channels(raw_notify))
    return raw_notify.strip(), channels


def extract_result_block(packet_lines: list[str]) -> list[str] | None:
    start = None
    for idx, line in enumerate(packet_lines):
        if line.strip() == "Result:":
            start = idx
            break
    if start is None:
        return None
    block = packet_lines[start:]
    if not any(line.strip() for line in block[1:]):
        return None
    return block


def preview_result_lines(result_block: list[str], *, max_lines: int = 12, max_chars: int = 900) -> list[str]:
    non_empty: list[tuple[int, str]] = []
    for idx, raw in enumerate(result_block[1:], start=1):
        line = sanitize_outbound_text(raw.rstrip())
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

    if out:
        last = out[-1].strip().lower()
        if last in {"next step:", "next step (if any):"} and cut < len(non_empty):
            nxt = non_empty[cut][1]
            if chars + len(nxt) + 1 <= max_chars:
                out.append(nxt)

    return out


def build_result_record(*, result_status: str | None, state: str) -> dict[str, object]:
    raw_status = (result_status or "").strip().upper()
    return {
        "present": bool(raw_status),
        "status": normalize_result_status(result_status),
        "raw_status": raw_status or None,
        "job_state": state,
    }


def _load_notify_state(repo_root: Path) -> dict[str, float]:
    path = repo_root / "tmp" / "inbox_notify_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, (int, float)):
            out[key] = float(value)
    return out


def _load_notify_dead_letters(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "tmp" / "inbox_notify_dead_letters.jsonl"
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for line in lines:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _delivery_error_for(
    dead_letters: list[dict[str, Any]],
    *,
    channel: str,
    kind: str,
    digest: str,
) -> str:
    for entry in reversed(dead_letters):
        item = entry.get("item")
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("channel") or "") == channel
            and str(item.get("kind") or "") == kind
            and str(item.get("digest") or "") == digest
        ):
            detail = str(entry.get("reason_detail") or "").strip()
            reason = str(entry.get("reason_class") or "").strip()
            return detail or reason
    return ""


def _delivery_channel_record(
    notify_state: dict[str, float],
    dead_letters: list[dict[str, Any]],
    *,
    channel: str,
    kind: str,
    digest: str | None,
) -> dict[str, object]:
    if not digest:
        return {"status": "not-requested", "attempts": 0, "last_ts": None, "last_error": ""}

    outcomes = ("delivered", "suppressed", "failed-to-deliver")
    candidates: list[tuple[float, str]] = []
    attempts_key = f"{channel}:{kind}:attempts:{digest}"
    raw_attempts = notify_state.get(attempts_key)
    attempts = int(raw_attempts) if isinstance(raw_attempts, (int, float)) and raw_attempts >= 0 else 0
    for outcome in outcomes:
        key = f"{channel}:{kind}:{outcome}:{digest}"
        if key in notify_state:
            attempts = max(attempts, 1)
            candidates.append((notify_state[key], outcome))

    if not candidates:
        return {"status": "pending", "attempts": 0, "last_ts": None, "last_error": ""}

    last_ts, status = max(candidates, key=lambda item: item[0])
    return {
        "status": status,
        "attempts": attempts,
        "last_ts": last_ts,
        "last_error": _delivery_error_for(dead_letters, channel=channel, kind=kind, digest=digest)
        if status == "failed-to-deliver"
        else "",
    }


def build_notification_delivery(
    *,
    notify_channels: list[str],
    queued_digest: str,
    result_digest: str | None,
    notify_state: dict[str, float],
    dead_letters: list[dict[str, Any]],
) -> dict[str, object]:
    if not notify_channels:
        return {
            "queued": {"status": "not-requested", "channels": {}},
            "result": {"status": "not-requested", "channels": {}},
        }

    def _kind(kind: str, digest: str | None) -> dict[str, object]:
        channels = {
            channel: _delivery_channel_record(
                notify_state,
                dead_letters,
                channel=channel,
                kind=kind,
                digest=digest,
            )
            for channel in notify_channels
        }
        statuses = {str(payload.get("status") or "") for payload in channels.values()}
        if "failed-to-deliver" in statuses:
            status = "failed-to-deliver"
        elif "pending" in statuses:
            status = "pending"
        elif "delivered" in statuses:
            status = "delivered"
        elif "suppressed" in statuses:
            status = "suppressed"
        else:
            status = "not-requested"
        return {"status": status, "channels": channels}

    return {
        "queued": _kind("queued", queued_digest),
        "result": _kind("result", result_digest),
    }


def build_job_record(
    *,
    repo_root: Path,
    packet,
    ticket_map: dict[str, object],
    pending_since_ts: float | None,
    stale_threshold_hours: float,
    now_ts: float,
    notify_state: dict[str, float] | None = None,
    dead_letters: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    before_result = []
    for line in packet.lines:
        if line.strip() == "Result:":
            break
        before_result.append(line)
    job_id = packet_content_id(packet.fields, before_result)

    ticket_refs: list[dict[str, object]] = []
    ticket_lanes: list[str] = []
    for ref in packet.ticket_refs:
        base = Path(ref).name
        ticket = ticket_map.get(base)
        if ticket is None:
            ticket_refs.append({"path": ref, "present": False})
            continue
        lane = getattr(ticket, "lane", "")
        ticket_lanes.append(lane)
        ticket_refs.append(
            {
                "path": getattr(ticket, "relpath", ref),
                "present": True,
                "lane": lane,
                "status": getattr(ticket, "status", ""),
                "title": getattr(ticket, "title", base),
            }
        )

    state = infer_job_state(
        result_status=packet.result_status,
        ticket_lanes=ticket_lanes,
        pending_since_ts=pending_since_ts,
        stale_threshold_hours=stale_threshold_hours,
        now_ts=now_ts,
    )
    state_reason = infer_job_state_reason(
        result_status=packet.result_status,
        ticket_lanes=ticket_lanes,
        pending_since_ts=pending_since_ts,
        stale_threshold_hours=stale_threshold_hours,
        now_ts=now_ts,
    )
    notify_raw, notify_channels = normalize_notify(packet.fields.get("Notify", ""))
    result_block = extract_result_block(packet.lines)
    queued_digest = sha256_lines(before_result)
    result_digest = sha256_lines(result_block or []) if result_block else None
    result = build_result_record(result_status=packet.result_status, state=state)
    if result_block:
        result["preview_lines"] = preview_result_lines(result_block)

    age_hours = None
    if pending_since_ts is not None:
        age_hours = round(max(0.0, (now_ts - pending_since_ts) / 3600.0), 2)

    return {
        "version": 1,
        "job_id": job_id,
        "packet_id": getattr(packet, "packet_id", job_id),
        "parent_packet_id": getattr(packet, "parent_packet_id", ""),
        "root_packet_id": getattr(packet, "root_packet_id", job_id),
        "workflow_id": getattr(packet, "workflow_id", job_id),
        "state": state,
        "state_reason": state_reason,
        "owner": packet.fields.get("Owner", packet.inbox_path.stem.upper()),
        "requester": packet.fields.get("Requester", ""),
        "objective": packet.fields.get("Objective", ""),
        "notify": notify_raw,
        "notify_channels": notify_channels,
        "notification_delivery": build_notification_delivery(
            notify_channels=notify_channels,
            queued_digest=queued_digest,
            result_digest=result_digest,
            notify_state=notify_state or {},
            dead_letters=dead_letters or [],
        ),
        "queued_digest": queued_digest,
        "result_digest": result_digest,
        "result_status": packet.result_status,
        "result": result,
        "inbox": {
            "path": packet.display_path,
            "line": packet.start_line,
        },
        "ticket_refs": ticket_refs,
        "pending_since_ts": pending_since_ts,
        "age_hours": age_hours,
        "stale_threshold_hours": stale_threshold_hours,
        "updated_ts": now_ts,
    }


def write_job_artifacts(
    *,
    repo_root: Path,
    packets: list[object],
    ticket_map: dict[str, object],
    pending_since_by_key: dict[str, float],
    stale_threshold_hours: float,
    now_ts: float,
) -> list[dict[str, object]]:
    out_dir = repo_root / "tasks" / "JOBS"
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    active_paths: set[Path] = set()
    counts: dict[str, int] = {}
    workflows: dict[str, dict[str, object]] = {}
    notify_state = _load_notify_state(repo_root)
    dead_letters = _load_notify_dead_letters(repo_root)

    for packet in packets:
        pending_since_ts = pending_since_by_key.get(packet.pending_key)
        record = build_job_record(
            repo_root=repo_root,
            packet=packet,
            ticket_map=ticket_map,
            pending_since_ts=pending_since_ts,
            stale_threshold_hours=stale_threshold_hours,
            now_ts=now_ts,
            notify_state=notify_state,
            dead_letters=dead_letters,
        )
        records.append(record)
        counts[record["state"]] = counts.get(record["state"], 0) + 1
        path = out_dir / f"{record['job_id']}.json"
        active_paths.add(path)
        atomic_write_text(path, json.dumps(record, indent=2, sort_keys=True) + "\n")
        workflow_id = str(record["workflow_id"])
        workflow = workflows.setdefault(
            workflow_id,
            {
                "workflow_id": workflow_id,
                "root_packet_id": record["root_packet_id"],
                "owners": set(),
                "states": [],
                "jobs": [],
            },
        )
        workflow["owners"].add(record["owner"])
        workflow["states"].append(record["state"])
        workflow["jobs"].append(
            {
                "job_id": record["job_id"],
                "packet_id": record["packet_id"],
                "parent_packet_id": record["parent_packet_id"],
                "state": record["state"],
                "state_reason": record["state_reason"],
                "owner": record["owner"],
                "objective": record["objective"],
                "notify": record["notify"],
                "notify_channels": record["notify_channels"],
                "notification_delivery": record["notification_delivery"],
                "queued_digest": record["queued_digest"],
                "result_digest": record["result_digest"],
                "result": record["result"],
                "inbox": record["inbox"],
            }
        )

    for existing in out_dir.glob("pkt-*.json"):
        if existing not in active_paths:
            try:
                existing.unlink()
            except FileNotFoundError:
                pass
    for existing in out_dir.glob("ik-*.json"):
        if existing not in active_paths:
            try:
                existing.unlink()
            except FileNotFoundError:
                pass
    for existing in out_dir.glob("wf-*.json"):
        if existing not in active_paths:
            try:
                existing.unlink()
            except FileNotFoundError:
                pass

    workflow_records: list[dict[str, object]] = []
    workflow_counts: dict[str, int] = {}
    for workflow_id, workflow in sorted(workflows.items()):
        workflow_state = infer_workflow_state(list(workflow["states"]))
        workflow_counts[workflow_state] = workflow_counts.get(workflow_state, 0) + 1
        workflow_record = {
            "version": 1,
            "workflow_id": workflow_id,
            "root_packet_id": workflow["root_packet_id"],
            "state": workflow_state,
            "state_reasons": sorted(
                {
                    str(job.get("state_reason") or "").strip()
                    for job in workflow["jobs"]
                    if str(job.get("state_reason") or "").strip()
                }
            ),
            "owners": sorted(str(owner) for owner in workflow["owners"]),
            "job_count": len(workflow["jobs"]),
            "jobs": workflow["jobs"],
            "updated_ts": now_ts,
        }
        workflow_records.append(workflow_record)
        workflow_path = out_dir / f"wf-{packet_content_id({'Idempotency Key': workflow_id}, [])}.json"
        active_paths.add(workflow_path)
        atomic_write_text(workflow_path, json.dumps(workflow_record, indent=2, sort_keys=True) + "\n")

    summary = {
        "version": 1,
        "updated_ts": now_ts,
        "job_count": len(records),
        "counts": counts,
        "workflow_count": len(workflow_records),
        "workflow_counts": workflow_counts,
        "jobs": [
            {
                "job_id": rec["job_id"],
                "workflow_id": rec["workflow_id"],
                "state": rec["state"],
                "state_reason": rec["state_reason"],
                "owner": rec["owner"],
                "objective": rec["objective"],
                "notify": rec["notify"],
                "notify_channels": rec["notify_channels"],
                "notification_delivery": rec["notification_delivery"],
                "queued_digest": rec["queued_digest"],
                "result_digest": rec["result_digest"],
                "result": rec["result"],
                "inbox": rec["inbox"],
            }
            for rec in sorted(records, key=lambda item: (str(item["state"]), str(item["owner"]), str(item["objective"])))
        ],
        "result_counts": {
            key: sum(1 for rec in records if str(rec["result"]["status"]) == key)
            for key in sorted({str(rec["result"]["status"]) for rec in records})
        },
        "workflows": [
            {
                "workflow_id": rec["workflow_id"],
                "state": rec["state"],
                "state_reasons": rec["state_reasons"],
                "owners": rec["owners"],
                "job_count": rec["job_count"],
            }
            for rec in workflow_records
        ],
    }
    atomic_write_text(out_dir / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return records
