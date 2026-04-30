#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from inbox_file_ops import append_packet_if_absent
except Exception:  # pragma: no cover
    from scripts.inbox_file_ops import append_packet_if_absent  # type: ignore


APPROVALS_REL_PATH = Path("tasks") / "APPROVALS" / "task-packet-approvals.jsonl"
SUPPORTED_DECISIONS = {"approve_once", "deny"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _summary_jobs(repo_root: Path) -> list[dict[str, Any]]:
    payload = _read_json(repo_root / "tasks" / "JOBS" / "summary.json", {"jobs": []})
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [job for job in jobs if isinstance(job, dict)]


def _find_job(repo_root: Path, job_id: str) -> dict[str, Any] | None:
    target = str(job_id or "").strip()
    if not target:
        return None
    for job in _summary_jobs(repo_root):
        if str(job.get("job_id") or "") == target:
            return job
    return None


def _approval_log_path(repo_root: Path) -> Path:
    return repo_root / APPROVALS_REL_PATH


def _read_records(repo_root: Path) -> list[dict[str, Any]]:
    path = _approval_log_path(repo_root)
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []


def _record_id(*, job_id: str, decision: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{job_id}\0{decision}\0{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"tpa-{digest}"


def _actor_label(actor: str) -> str:
    clean = " ".join(str(actor or "").split()).strip()
    return clean[:160] or "telegram:unknown"


def _job_owner(job: dict[str, Any]) -> str:
    owner = str(job.get("owner") or "").strip().upper()
    return owner or "ATLAS"


def _inbox_pointer(job: dict[str, Any]) -> str:
    inbox = job.get("inbox") if isinstance(job.get("inbox"), dict) else {}
    path = str(inbox.get("path") or "").strip()
    line = str(inbox.get("line") or "").strip()
    if path and line:
        return f"{path}:{line}"
    return path or "tasks/JOBS/summary.json"


def _append_record(repo_root: Path, record: dict[str, Any]) -> None:
    path = _approval_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _existing_record(repo_root: Path, *, job_id: str, decision: str) -> dict[str, Any] | None:
    for record in reversed(_read_records(repo_root)):
        if record.get("job_id") == job_id and record.get("decision") == decision:
            return record
    return None


def _approval_packet(record: dict[str, Any], job: dict[str, Any]) -> list[str]:
    owner = _job_owner(job)
    job_id = str(record["job_id"])
    workflow_id = str(job.get("workflow_id") or job_id)
    objective = str(job.get("objective") or "Continue approved Task Packet.").strip()
    inbox_pointer = _inbox_pointer(job)
    return [
        "TASK_PACKET v1",
        f"Owner: {owner}",
        "Requester: ORION",
        "Notify: telegram",
        f"Idempotency Key: task-approval-{record['id']}",
        f"Workflow ID: {workflow_id}",
        "Approval Gate: CORY_MINIAPP_APPROVED",
        f"Gate Evidence: {APPROVALS_REL_PATH.as_posix()} id={record['id']}",
        "Execution Mode: direct",
        "Tool Scope: write",
        f"Objective: Continue the approved Task Packet exactly once: {objective}",
        "Success Criteria:",
        "- Re-check the original packet, stop gates, and current state before any action.",
        "- Execute only the work covered by Cory's Mini App approval record.",
        "- Report command/path proof and verification in the Result block.",
        "Constraints:",
        "- Approval scope is this exact packet only; do not generalize it to future packets.",
        "- Preserve every stop gate from the original packet unless the approval record explicitly covers it.",
        "- Do not perform credential, payment, destructive, or broad external-delivery work unless the original packet and approval both authorize it.",
        "Inputs:",
        f"- Approval record: {APPROVALS_REL_PATH.as_posix()} id={record['id']}",
        f"- Original job id: {job_id}",
        f"- Original inbox: {inbox_pointer}",
        f"- Actor: {record['actor']}",
        "Risks:",
        "- Approval could be misapplied to adjacent work; mitigate by matching the original job id and inbox pointer.",
        "Stop Gates:",
        "- If the original packet is missing, changed materially, or no longer blocked on Cory approval, stop and return BLOCKED.",
        "- If execution would exceed the original packet scope, stop and ask ORION for a new approval packet.",
        "Output Format:",
        "- Result:",
        "- Status: OK | FAILED | BLOCKED",
        "- What changed / what I found:",
        "- Verification:",
        "- Next step (if any):",
    ]


def decide(repo_root: Path, *, job_id: str, decision: str, actor: str) -> dict[str, Any]:
    decision = decision.strip().lower().replace("-", "_")
    if decision not in SUPPORTED_DECISIONS:
        raise ValueError(f"unsupported decision: {decision}")
    job = _find_job(repo_root, job_id)
    if not job:
        raise ValueError("job not found")
    state = str(job.get("state") or "").strip().lower()
    if state != "blocked":
        raise ValueError(f"job is not blocked: {state or 'unknown'}")

    existing = _existing_record(repo_root, job_id=str(job.get("job_id")), decision=decision)
    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "message": _message_for(existing, queued=bool(existing.get("queued_packet"))),
            "record": existing,
        }

    created_at = _utc_now()
    record = {
        "id": _record_id(job_id=str(job.get("job_id")), decision=decision, created_at=created_at),
        "created_at": created_at,
        "source": "orion-miniapp",
        "actor": _actor_label(actor),
        "decision": decision,
        "scope": "exact_packet_only",
        "job_id": str(job.get("job_id")),
        "workflow_id": str(job.get("workflow_id") or job.get("job_id")),
        "owner": _job_owner(job),
        "objective": str(job.get("objective") or "").strip(),
        "inbox": _inbox_pointer(job),
    }

    queued_packet = ""
    appended = False
    if decision == "approve_once":
        owner = _job_owner(job)
        inbox_path = repo_root / "tasks" / "INBOX" / f"{owner}.md"
        packet_lines = _approval_packet(record, job)
        appended = append_packet_if_absent(inbox_path, owner=owner, packet_lines=packet_lines)
        queued_packet = str(inbox_path.relative_to(repo_root))
        record["queued_packet"] = queued_packet
        record["queued"] = appended

    _append_record(repo_root, record)
    return {
        "ok": True,
        "duplicate": False,
        "message": _message_for(record, queued=appended),
        "record": record,
    }


def _message_for(record: dict[str, Any], *, queued: bool) -> str:
    if record.get("decision") == "deny":
        return "Task Packet denied; no follow-up packet was created."
    if queued:
        return f"Task Packet approved once; follow-up queued for {record.get('owner', 'the owner')}."
    return "Task Packet approval was already recorded."


def seed_tests(repo_root: Path) -> dict[str, Any]:
    inbox_path = repo_root / "tasks" / "INBOX" / "ATLAS.md"
    seeded: list[dict[str, Any]] = []
    specs = [
        (
            "miniapp-approval-test-dry-run-20260430",
            "TEST APPROVAL: confirm Mini App approval flow for a dry-run ATLAS packet.",
            "This is a safe approval-flow smoke test. Approving it should only queue the approved follow-up packet; no external side effects are required.",
        ),
        (
            "miniapp-approval-test-deny-path-20260430",
            "TEST APPROVAL: confirm Mini App deny path for a Task Packet.",
            "This is a safe deny-flow smoke test. Denying it should write the approval decision log and queue no follow-up packet.",
        ),
        (
            "miniapp-approval-test-visible-approve-20260430b",
            "TEST APPROVAL: verify visible approved-state feedback in the Mini App.",
            "This is a safe approval-feedback smoke test. Approving it should show an approved decision and a queued owner follow-up in the detail panel.",
        ),
        (
            "miniapp-approval-test-visible-deny-20260430b",
            "TEST APPROVAL: verify visible denied-state feedback in the Mini App.",
            "This is a safe denial-feedback smoke test. Denying it should show a denied decision in the detail panel and queue no owner follow-up.",
        ),
    ]
    for key, objective, note in specs:
        packet_lines = [
            "TASK_PACKET v1",
            "Owner: ATLAS",
            "Requester: ORION",
            "Notify: telegram",
            f"Idempotency Key: {key}",
            f"Objective: {objective}",
            "Success Criteria:",
            "- The Mini App shows this blocked packet as eligible for Cory approval.",
            "- Cory can tap Approve Once or Deny without any external side effects.",
            "Constraints:",
            "- Test packet only.",
            "- Do not run external commands, send messages, edit credentials, or change live services from this packet.",
            "Inputs:",
            f"- {note}",
            "Risks:",
            "- Low; this packet exists only to exercise the approval UI.",
            "Stop Gates:",
            "- Any non-test side effect.",
            "Output Format:",
            "- Result:",
            "- Status: OK | FAILED | BLOCKED",
            "- What changed / what I found:",
            "- Next step (if any):",
            "",
            "Result:",
            "Status: BLOCKED",
            "What changed / what I found:",
            f"- {note}",
            "Next step (if any):",
            "- Await Cory's Mini App approval decision.",
        ]
        appended = append_packet_if_absent(inbox_path, owner="ATLAS", packet_lines=packet_lines)
        seeded.append({"idempotency_key": key, "objective": objective, "appended": appended})
    return {"ok": True, "seeded": seeded}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record Cory Mini App approvals for blocked Task Packets.")
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    decide_parser = sub.add_parser("decide")
    decide_parser.add_argument("--job-id", required=True)
    decide_parser.add_argument("--decision", required=True, choices=sorted(SUPPORTED_DECISIONS))
    decide_parser.add_argument("--actor", default="telegram:unknown")

    sub.add_parser("seed-tests")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    try:
        if args.cmd == "decide":
            payload = decide(repo_root, job_id=args.job_id, decision=args.decision, actor=args.actor)
        elif args.cmd == "seed-tests":
            payload = seed_tests(repo_root)
        else:  # pragma: no cover
            raise ValueError(f"unknown command: {args.cmd}")
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(payload["error"], file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload.get("message") or json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
