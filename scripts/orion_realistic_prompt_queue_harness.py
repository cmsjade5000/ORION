#!/usr/bin/env python3
"""Local realistic-prompt harness for the ORION packet queue.

This intentionally uses the repo's real packet runner and reconcile modules,
while isolating all state in a temp/staging root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_inbox_packets  # noqa: E402
import task_execution_loop  # noqa: E402
from inbox_file_ops import atomic_write_text, ensure_packets_header, locked_file  # noqa: E402


REQUIRED_SAFETY = {"local_staging_only", "read_only", "no_external_delivery", "no_credentials"}


def load_fixtures(path: Path) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{lineno}: fixture must be an object")
        fixtures.append(item)
    return fixtures


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "prompt"


def _init_staging_repo(root: Path) -> None:
    for lane in ("backlog", "in-progress", "testing", "done"):
        (root / "tasks" / "WORK" / lane).mkdir(parents=True, exist_ok=True)
    (root / "tasks" / "INBOX").mkdir(parents=True, exist_ok=True)
    (root / "tasks" / "JOBS").mkdir(parents=True, exist_ok=True)
    (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "diagnose_gateway.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "state_file=\"${ORION_REALISTIC_HARNESS_STATE:?missing state}\"\n"
        "behavior=\"${ORION_REALISTIC_HARNESS_BEHAVIOR:-success}\"\n"
        "attempt=1\n"
        "if [[ -f \"$state_file\" ]]; then attempt=$(( $(cat \"$state_file\") + 1 )); fi\n"
        "printf '%s' \"$attempt\" > \"$state_file\"\n"
        "if [[ \"$behavior\" == \"fail_once_then_succeed\" && \"$attempt\" -eq 1 ]]; then\n"
        "  echo 'Gateway target: local-staging'\n"
        "  echo 'worker failed during first claim' >&2\n"
        "  exit 2\n"
        "fi\n"
        "echo 'Gateway target: local-staging'\n"
        "echo 'Task ID: '${ORION_REALISTIC_HARNESS_TASK_ID:-unknown}\n"
        "echo 'Queue lifecycle: queued -> running -> completed'\n",
        encoding="utf-8",
    )
    (scripts_dir / "diagnose_gateway.sh").chmod(0o755)


def validate_fixture(item: dict[str, Any]) -> None:
    missing = [key for key in ("id", "prompt", "expected_behavior", "queue_behavior", "safety_constraints") if key not in item]
    if missing:
        raise ValueError(f"{item.get('id', '<unknown>')}: missing required fixture keys: {', '.join(missing)}")
    safety = set(item.get("safety_constraints") or [])
    missing_safety = REQUIRED_SAFETY - safety
    if missing_safety:
        raise ValueError(f"{item['id']}: missing safety constraints: {', '.join(sorted(missing_safety))}")


def packet_lines(item: dict[str, Any]) -> list[str]:
    q = item["queue_behavior"]
    owner = str(q.get("owner") or "ORION").upper()
    requester = str(q.get("requester") or "ORION").upper()
    fixture_id = str(item["id"])
    workflow_id = f"realistic-{_slug(fixture_id)}"
    expected = item.get("expected_behavior") or {}
    objective = f"Process realistic ORION prompt fixture {fixture_id}."
    retry_attempts = 2 if q.get("command_behavior") == "fail_once_then_succeed" else 1
    return [
        "TASK_PACKET v1",
        f"Owner: {owner}",
        f"Requester: {requester}",
        "Notify: telegram",
        "Execution Mode: direct",
        "Tool Scope: read-only",
        f"Idempotency Key: realistic-prompt:{fixture_id}",
        f"Packet ID: {workflow_id}",
        f"Root Packet ID: {workflow_id}",
        f"Workflow ID: {workflow_id}",
        f"Priority: {q.get('priority', 'normal')}",
        f"Objective: {objective}",
        "Context: Realistic ORION user prompt regression fixture.",
        "Success Criteria:",
        "- Original user wording is preserved in Inputs.",
        "- The packet receives a traceable task ID and durable job summary entry.",
        "- Local staging execution returns a useful result or failure artifact.",
        "Constraints:",
        "- Read-only.",
        "- Local staging only.",
        "- Do not contact external services or send user-facing messages.",
        "Inputs:",
        f"- Fixture ID: {fixture_id}",
        f"- Original Prompt: {item['prompt']}",
        f"- Expected Category: {expected.get('category', 'unspecified')}",
        "Risks:",
        "- Low; isolated temp repo and local command stub.",
        "Stop Gates:",
        "- Any production credential, external delivery, destructive command, or live provider call.",
        "Commands to run:",
        "- scripts/diagnose_gateway.sh",
        f"Retry Max Attempts: {retry_attempts}",
        "Retry Backoff Seconds: 0",
        "Retry Backoff Multiplier: 1",
        "Retry Max Backoff Seconds: 0",
        "Command Timeout Seconds: 5",
        "Output Format:",
        "- Short lifecycle summary with artifact path.",
    ]


def append_packet(repo_root: Path, item: dict[str, Any]) -> Path:
    owner = str(item["queue_behavior"].get("owner") or "ORION").upper()
    inbox = repo_root / "tasks" / "INBOX" / f"{owner}.md"
    lock_path = inbox.with_suffix(inbox.suffix + ".lock")
    with locked_file(lock_path):
        lines = ensure_packets_header(inbox.read_text(encoding="utf-8").splitlines() if inbox.exists() else [], owner=owner)
        text = "\n".join(lines).rstrip() + "\n\n" + "\n".join(packet_lines(item)).rstrip() + "\n"
        atomic_write_text(inbox, text)
    return inbox


def cancel_pending_packet(repo_root: Path, item: dict[str, Any]) -> None:
    owner = str(item["queue_behavior"].get("owner") or "ORION").upper()
    inbox = repo_root / "tasks" / "INBOX" / f"{owner}.md"
    text = inbox.read_text(encoding="utf-8")
    marker = f"Idempotency Key: realistic-prompt:{item['id']}"
    marker_idx = text.rfind(marker)
    if marker_idx < 0:
        raise AssertionError(f"{item['id']}: packet marker not found for cancellation")
    packet_tail = text[marker_idx:]
    if "\nTASK_PACKET v1" in packet_tail:
        packet_tail = packet_tail.split("\nTASK_PACKET v1", 1)[0]
    if "Result:" in packet_tail:
        raise AssertionError(f"{item['id']}: cannot cancel packet after it has a result")
    atomic_write_text(
        inbox,
        text.rstrip()
        + "\n\nResult:\nStatus: CANCELLED\nSummary: Cancelled while still queued in local staging.\n\n",
    )


def _run_fixture(repo_root: Path, item: dict[str, Any]) -> dict[str, Any]:
    validate_fixture(item)
    append_packet(repo_root, item)
    fixture_id = str(item["id"])
    behavior = str(item.get("queue_behavior", {}).get("command_behavior") or "success")
    cancel_before_run = bool(item.get("queue_behavior", {}).get("cancel_before_run"))
    if cancel_before_run:
        cancel_pending_packet(repo_root, item)
    state_path = repo_root / "tmp" / f"{_slug(fixture_id)}-attempts.txt"
    env_patch = {
        "ORION_REALISTIC_HARNESS_BEHAVIOR": behavior,
        "ORION_REALISTIC_HARNESS_STATE": str(state_path),
        "ORION_REALISTIC_HARNESS_TASK_ID": fixture_id,
        "ORION_TASK_LOOP_SKIP_OPENCLAW_SNAPSHOT": "1",
    }

    old_env = {key: os.environ.get(key) for key in env_patch}
    os.environ.update(env_patch)
    try:
        runner_rc_1 = 0
        retrying = False
        runner_rc_2 = None
        if not cancel_before_run:
            runner_rc_1 = run_inbox_packets.run(
                repo_root,
                max_packets=1,
                state_path=repo_root / "tmp" / "inbox_runner_state.json",
            )
            if behavior == "fail_once_then_succeed":
                retrying = True
                runner_rc_2 = run_inbox_packets.run(
                    repo_root,
                    max_packets=1,
                    state_path=repo_root / "tmp" / "inbox_runner_state.json",
                )
        loop_rc = task_execution_loop.run(
            repo_root,
            apply_changes=True,
            stale_hours=24.0,
            strict_stale=False,
            state_path=repo_root / "tmp" / "task_execution_loop_state.json",
        )
    finally:
        for key, old in old_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    summary = json.loads((repo_root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
    workflow_id = f"realistic-{_slug(fixture_id)}"
    jobs = [job for job in summary.get("jobs", []) if job.get("workflow_id") == workflow_id]
    if not jobs:
        raise AssertionError(f"{fixture_id}: no job summary entry for workflow {workflow_id}")
    job = jobs[0]
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    expected_terminal = "cancelled" if cancel_before_run else "ok"
    if result.get("status") != expected_terminal:
        raise AssertionError(f"{fixture_id}: expected {expected_terminal} result, got {result}")
    if not job.get("queued_digest") or not job.get("result_digest"):
        raise AssertionError(f"{fixture_id}: missing queued/result digest")
    expected_states = set(item.get("queue_behavior", {}).get("expected_states") or [])
    observed_states = {"queued", str(job.get("state") or "")}
    if retrying:
        observed_states.add("retrying")
    missing_states = expected_states - observed_states
    if missing_states:
        raise AssertionError(f"{fixture_id}: missing expected states {sorted(missing_states)} from {sorted(observed_states)}")
    return {
        "id": fixture_id,
        "runner_rc_1": runner_rc_1,
        "runner_rc_2": runner_rc_2,
        "loop_rc": loop_rc,
        "job_id": job.get("job_id"),
        "workflow_id": job.get("workflow_id"),
        "state": job.get("state"),
        "result_status": result.get("status"),
        "queued_digest": job.get("queued_digest"),
        "result_digest": job.get("result_digest"),
        "retrying_observed": retrying,
    }


def run_fixture_set(fixtures: list[dict[str, Any]], *, keep_root: Path | None = None) -> dict[str, Any]:
    if keep_root is not None:
        keep_root.mkdir(parents=True, exist_ok=True)
        _init_staging_repo(keep_root)
        results = [_run_fixture(keep_root, item) for item in fixtures]
        return {"ok": True, "repo_root": str(keep_root), "results": results}

    with tempfile.TemporaryDirectory(prefix="orion-realistic-queue-") as td:
        root = Path(td)
        _init_staging_repo(root)
        results = [_run_fixture(root, item) for item in fixtures]
        return {"ok": True, "repo_root": str(root), "results": results}


def main() -> int:
    default_fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "orion_realistic_user_prompts.jsonl"
    parser = argparse.ArgumentParser(description="Run realistic ORION prompt fixtures through the local packet queue.")
    parser.add_argument("--fixtures", default=str(default_fixture))
    parser.add_argument("--keep-root", default="", help="Optional staging repo root to keep after the run.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    fixtures = load_fixtures(Path(args.fixtures))
    report = run_fixture_set(fixtures, keep_root=Path(args.keep_root).resolve() if args.keep_root else None)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"REALISTIC_QUEUE_OK fixtures={len(report['results'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
