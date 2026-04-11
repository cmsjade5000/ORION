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

try:
    from inbox_state import sha256_lines
    from inbox_file_ops import atomic_write_text
except Exception:  # pragma: no cover
    from scripts.inbox_state import sha256_lines  # type: ignore
    from scripts.inbox_file_ops import atomic_write_text  # type: ignore


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
    if normalized in {"FAILED", "BLOCKED"}:
        return "blocked"
    if normalized == "OK":
        if "done" in ticket_lanes:
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


def build_job_record(
    *,
    repo_root: Path,
    packet,
    ticket_map: dict[str, object],
    pending_since_ts: float | None,
    stale_threshold_hours: float,
    now_ts: float,
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
        "owner": packet.fields.get("Owner", packet.inbox_path.stem.upper()),
        "requester": packet.fields.get("Requester", ""),
        "objective": packet.fields.get("Objective", ""),
        "notify": packet.fields.get("Notify", ""),
        "result_status": packet.result_status,
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

    for packet in packets:
        pending_since_ts = pending_since_by_key.get(packet.pending_key)
        record = build_job_record(
            repo_root=repo_root,
            packet=packet,
            ticket_map=ticket_map,
            pending_since_ts=pending_since_ts,
            stale_threshold_hours=stale_threshold_hours,
            now_ts=now_ts,
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
                "owner": record["owner"],
                "objective": record["objective"],
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
                "state": rec["state"],
                "owner": rec["owner"],
                "objective": rec["objective"],
                "inbox": rec["inbox"],
            }
            for rec in sorted(records, key=lambda item: (str(item["state"]), str(item["owner"]), str(item["objective"])))
        ],
        "workflows": [
            {
                "workflow_id": rec["workflow_id"],
                "state": rec["state"],
                "owners": rec["owners"],
                "job_count": rec["job_count"],
            }
            for rec in workflow_records
        ],
    }
    atomic_write_text(out_dir / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return records
