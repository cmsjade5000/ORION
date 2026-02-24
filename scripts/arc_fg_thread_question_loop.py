#!/usr/bin/env python3
"""Post targeted Arc FG questions per thread and create missing subject threads."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

OPENCLAW_BIN = (
    os.environ.get("OPENCLAW_BIN")
    or shutil.which("openclaw")
    or "/Users/corystoner/.npm-global/bin/openclaw"
)

DOC_PATHS = {
    "FG-Chapters-Layout": "docs/arc-raiders-field-guide/chapters-layout-draft.md",
    "FG-Cost-Breakdown": "docs/arc-raiders-field-guide/cost-breakdown-draft.md",
    "FG-Project-Management": "docs/arc-raiders-field-guide/project-management-draft.md",
}

DEFAULT_QUESTION_SETS = {
    "FG-Chapters-Layout": [
        ("SCRIBE", "Which 2 chapters should be prioritized for first polished release?"),
        ("SCRIBE", "Do you want each chapter to end with a one-page checklist?"),
        ("SCRIBE", "Should we split tactics explicitly into solo vs squad callouts in every chapter?"),
    ],
    "FG-Project-Management": [
        ("POLARIS", "What is your target publish date for the first public draft?"),
        ("POLARIS", "Who should be owner-of-record for final QA sign-off?"),
        ("POLARIS", "Which risk is highest right now: scope creep, sourcing quality, or schedule drift?"),
    ],
}

REQUIRED_SUBJECT_THREADS = [
    {
        "name": "FG-Research-Sources",
        "purpose": "Source quality control, citation policy, and evidence confidence.",
        "depends_on_hq": True,
        "initial_prompt": (
            "ORION created this thread to stabilize research quality and citation policy for the Field Guide.\n"
            "Please reply in-thread with your preferences so research can continue without blocking."
        ),
    },
    {
        "name": "FG-Audience-Scope",
        "purpose": "Audience personas, scope boundaries, and publishing intent.",
        "depends_on_hq": True,
        "initial_prompt": (
            "ORION created this thread to lock audience and scope decisions for the Field Guide.\n"
            "Please reply in-thread so drafting can stay aligned."
        ),
    },
]


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def minutes_since(ts: str | None, now_dt: datetime) -> float | None:
    dt = parse_iso(ts)
    if dt is None:
        return None
    return (now_dt - dt).total_seconds() / 60.0


def run_cmd(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text())


def save_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)


def channel_info(channel_id: str, dry_run: bool) -> dict[str, Any]:
    cmd = [
        OPENCLAW_BIN,
        "message",
        "channel",
        "info",
        "--channel",
        "discord",
        "--target",
        channel_id,
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    data = json.loads(raw)
    payload = data.get("payload") or {}
    channel = payload.get("channel")
    return channel if isinstance(channel, dict) else {}


def list_threads(guild_id: str, parent_channel_id: str, dry_run: bool) -> list[dict[str, Any]]:
    if dry_run:
        return []
    cmd = [
        OPENCLAW_BIN,
        "message",
        "thread",
        "list",
        "--channel",
        "discord",
        "--guild-id",
        guild_id,
        "--channel-id",
        parent_channel_id,
        "--limit",
        "100",
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    data = json.loads(raw)
    payload = data.get("payload") or {}
    threads_root = payload.get("threads") or {}
    return threads_root.get("threads") or []


def create_thread(parent_channel_id: str, name: str, message: str, dry_run: bool) -> dict[str, Any]:
    cmd = [
        OPENCLAW_BIN,
        "message",
        "thread",
        "create",
        "--channel",
        "discord",
        "--target",
        parent_channel_id,
        "--thread-name",
        name,
        "--message",
        message,
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    return json.loads(raw)


def send_message(target: str, message: str, dry_run: bool) -> dict[str, Any]:
    cmd = [
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
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    return json.loads(raw)


def read_messages(target: str, limit: int, dry_run: bool) -> list[dict[str, Any]]:
    if dry_run:
        return []
    cmd = [
        OPENCLAW_BIN,
        "message",
        "read",
        "--channel",
        "discord",
        "--target",
        target,
        "--limit",
        str(limit),
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    data = json.loads(raw)
    payload = data.get("payload") or {}
    return payload.get("messages") or []


def message_id_from_send_result(result: dict[str, Any]) -> str | None:
    payload = result.get("payload") or {}
    nested = payload.get("result") or {}
    mid = nested.get("messageId")
    return str(mid) if mid else None


def extract_open_questions(md_text: str) -> list[str]:
    lines = md_text.splitlines()
    questions: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## open questions"):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped.startswith("- "):
            val = stripped[2:].strip()
            if val:
                questions.append(val)
    return questions


def build_question_sets(cwd: Path) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {k: list(v) for k, v in DEFAULT_QUESTION_SETS.items()}
    cost_doc = cwd / DOC_PATHS["FG-Cost-Breakdown"]
    if cost_doc.exists():
        open_q = extract_open_questions(cost_doc.read_text())
        if open_q:
            out["FG-Cost-Breakdown"] = [("LEDGER", q.rstrip("?") + "?") for q in open_q[:6]]
    if "FG-Research-Sources" not in out:
        out["FG-Research-Sources"] = [
            ("SCRIBE", "Which 3 sources should be treated as primary references for factual claims?"),
            ("SCRIBE", "Do you want unofficial wikis included, or only official/dev-backed sources?"),
            ("SCRIBE", "What citation style should we use in the field guide: inline links or endnotes?"),
        ]
    if "FG-Audience-Scope" not in out:
        out["FG-Audience-Scope"] = [
            ("POLARIS", "Who is the primary audience for v1: brand-new players, returners, or mixed?"),
            ("POLARIS", "Should v1 scope include only gameplay systems, or also lore and monetization context?"),
            ("POLARIS", "Which outcome matters most for v1: speed to publish, depth, or visual polish?"),
        ]
    return out


def ensure_required_threads(
    *,
    registry: dict[str, Any],
    state: dict[str, Any],
    parent_channel_id: str,
    guild_id: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    now = now_iso()
    known = {str(t.get("name", "")).strip(): str(t.get("id", "")).strip() for t in (registry.get("threads") or [])}
    threads_live = list_threads(guild_id, parent_channel_id, dry_run=dry_run)
    for t in threads_live:
        name = str(t.get("name", "")).strip()
        tid = str(t.get("id", "")).strip()
        if name and tid:
            known[name] = tid

    hq_id = str(registry.get("hq_thread_id") or "")
    for spec in REQUIRED_SUBJECT_THREADS:
        name = spec["name"]
        if known.get(name):
            continue
        create_thread(parent_channel_id, name, spec["initial_prompt"], dry_run=dry_run)
        refreshed = list_threads(guild_id, parent_channel_id, dry_run=dry_run)
        created_id = ""
        for t in refreshed:
            if str(t.get("name", "")).strip() == name:
                created_id = str(t.get("id", "")).strip()
                break
        if not created_id and dry_run:
            created_id = f"dryrun:{name}"
        if not created_id:
            continue
        known[name] = created_id
        if not dry_run:
            registry.setdefault("threads", []).append(
                {
                    "id": created_id,
                    "name": name,
                    "status": "active",
                    "purpose": spec["purpose"],
                    "depends_on": [hq_id] if spec.get("depends_on_hq") and hq_id else [],
                }
            )
        created.append({"id": created_id, "name": name, "purpose": spec["purpose"], "created_at": now})
    loop = state.setdefault("question_loop", {})
    created_log = loop.setdefault("created_threads", [])
    created_log.extend(created)
    return created


def has_user_reply_since_question(messages: list[dict[str, Any]], asked_at_iso: str, asked_id: str | None) -> bool:
    asked_dt = parse_iso(asked_at_iso)
    for msg in messages:
        author = msg.get("author") or {}
        if bool(author.get("bot")):
            continue
        if asked_id and str(msg.get("id")) == str(asked_id):
            continue
        ts = parse_iso(msg.get("timestamp"))
        if asked_dt and ts and ts > asked_dt:
            return True
        if not asked_dt:
            return True
    return False


def post_questions(
    *,
    registry: dict[str, Any],
    state: dict[str, Any],
    questions_by_thread: dict[str, list[tuple[str, str]]],
    dry_run: bool,
    min_minutes_between_questions: int,
) -> dict[str, Any]:
    now_dt = datetime.now().astimezone()
    now = now_dt.replace(microsecond=0).isoformat()
    qstate = state.setdefault("question_loop", {})
    tstate = qstate.setdefault("threads", {})

    asked: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for t in registry.get("threads") or []:
        tname = str(t.get("name") or "")
        tid = str(t.get("id") or "")
        if not tname or not tid:
            continue
        qset = questions_by_thread.get(tname) or []
        if not qset:
            continue
        ts = tstate.setdefault(tid, {"cursor": 0, "awaiting_reply": False})
        msgs = read_messages(tid, limit=50, dry_run=dry_run)

        if ts.get("awaiting_reply"):
            if has_user_reply_since_question(msgs, str(ts.get("last_question_at") or ""), ts.get("last_question_id")):
                ts["awaiting_reply"] = False
                ts["last_user_reply_at"] = now
            else:
                waiting.append({"thread": tname, "thread_id": tid, "reason": "awaiting_user_reply"})
                continue

        mins = minutes_since(ts.get("last_question_at"), now_dt)
        if mins is not None and mins < float(min_minutes_between_questions):
            skipped.append({"thread": tname, "thread_id": tid, "reason": "cooldown"})
            continue

        cursor = int(ts.get("cursor", 0))
        agent, question = qset[cursor % len(qset)]
        text = (
            f"Question ({agent})\n"
            f"{question}\n\n"
            "Please reply in this thread so ORION can continue the next pass."
        )
        res = send_message(tid, text, dry_run=dry_run)
        msg_id = message_id_from_send_result(res)
        ts["cursor"] = cursor + 1
        ts["awaiting_reply"] = True
        ts["last_question_at"] = now
        ts["last_question_id"] = msg_id
        ts["last_question_agent"] = agent
        ts["last_question_text"] = question
        asked.append({"thread": tname, "thread_id": tid, "agent": agent, "question": question, "message_id": msg_id})

    qstate["last_run_at"] = now
    qstate["status"] = "ok"
    qstate["last_asked_count"] = len(asked)
    qstate["last_waiting_count"] = len(waiting)
    qstate["last_skipped_count"] = len(skipped)
    return {"asked": asked, "waiting": waiting, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="Arc FG thread question loop with auto-thread creation.")
    parser.add_argument("--registry", default="tmp/arc_fg_thread_registry.json")
    parser.add_argument("--state", default="tmp/arc_fg_loop_state.json")
    parser.add_argument("--min-minutes-between-questions", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cwd = Path.cwd()
    registry_path = (cwd / args.registry).resolve()
    state_path = (cwd / args.state).resolve()

    registry = load_json(registry_path, {"version": 1, "threads": []})
    state = load_json(state_path, {"version": 1, "updated_at": now_iso(), "active_run": None})
    if args.dry_run:
        registry = json.loads(json.dumps(registry))
        state = json.loads(json.dumps(state))

    if state.get("active_run"):
        state.setdefault("question_loop", {})["status"] = "skip_active_run"
        state["updated_at"] = now_iso()
        if not args.dry_run:
            save_json(state_path, state)
        print(json.dumps({"status": "ok", "action": "skip_active_run"}))
        return 0

    parent_channel_id = str(registry.get("parent_channel_id") or "")
    if not parent_channel_id:
        raise RuntimeError("missing parent_channel_id in registry")

    chan = channel_info(parent_channel_id, dry_run=args.dry_run)
    guild_id = str(chan.get("guild_id") or "")
    if not guild_id and args.dry_run:
        guild_id = "dryrun"
    if not guild_id and not args.dry_run:
        raise RuntimeError("missing guild_id for parent channel")

    created = ensure_required_threads(
        registry=registry,
        state=state,
        parent_channel_id=parent_channel_id,
        guild_id=guild_id,
        dry_run=args.dry_run,
    )
    question_sets = build_question_sets(cwd)
    post_res = post_questions(
        registry=registry,
        state=state,
        questions_by_thread=question_sets,
        dry_run=args.dry_run,
        min_minutes_between_questions=args.min_minutes_between_questions,
    )

    state["updated_at"] = now_iso()
    if not args.dry_run:
        save_json(registry_path, registry)
        save_json(state_path, state)

    print(
        json.dumps(
            {
                "status": "ok",
                "created_threads": created,
                "asked_count": len(post_res["asked"]),
                "waiting_count": len(post_res["waiting"]),
                "skipped_count": len(post_res["skipped"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
