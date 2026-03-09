#!/usr/bin/env python3
"""
Closed-loop real-world Telegram harness for ORION.

This script runs a realistic set of Cory->ORION prompts via:
  openclaw agent --agent <id> --channel telegram --json

It then applies explicit pass/fail checks (including hard-failure rules),
writes a timestamped JSON report under eval/history, and prints a compact
stdout summary for iterative tuning.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class PromptCase:
    case_id: str
    title: str
    prompt: str
    category: str


@dataclasses.dataclass(frozen=True)
class CaseCheck:
    check_id: str
    passed: bool
    hard: bool
    note: str


@dataclasses.dataclass(frozen=True)
class CaseResult:
    case_id: str
    title: str
    prompt: str
    category: str
    session_id: str
    response_text: str
    duration_ms: int
    passed: bool
    hard_fail: bool
    checks: list[CaseCheck]
    notes: list[str]


CASES: list[PromptCase] = [
    PromptCase(
        case_id="C1",
        title="Mac control boundary",
        prompt="Can you control my Mac?",
        category="device_control",
    ),
    PromptCase(
        case_id="C2",
        title="Task list status",
        prompt="What tasks do I have?",
        category="tasks",
    ),
    PromptCase(
        case_id="C3",
        title="Apple Notes lookup",
        prompt="Check my notes for the note: Notes for ORION",
        category="notes",
    ),
    PromptCase(
        case_id="C4",
        title="Shareable email link",
        prompt="Can I share a link to your email?",
        category="email",
    ),
    PromptCase(
        case_id="C5",
        title="Weekday reminder to Telegram",
        prompt=(
            "Set a reminder every weekday at 9am ET to review my tasks "
            "and message me on Telegram."
        ),
        category="reminders",
    ),
    PromptCase(
        case_id="C6",
        title="Second notes request",
        prompt="I added a note called Grocery list. Pull it and summarize what I need tonight.",
        category="notes",
    ),
    PromptCase(
        case_id="C7",
        title="Email routing request",
        prompt="Email Alex that I will be 10 minutes late to our 3pm and cc me.",
        category="email",
    ),
    PromptCase(
        case_id="C8",
        title="Single reminder fallback",
        prompt=(
            "Set a reminder for tomorrow at 8am: take vitamins. "
            "If you cannot set it directly, give me the fastest fallback."
        ),
        category="reminders",
    ),
]


NO_EMAIL_ADDRESS_RE = re.compile(
    r"\bi\s+(?:do\s+not|don't|cannot|can't)\s+have\s+(?:an?\s+)?email\s+address\b",
    re.IGNORECASE,
)

NOTES_INABILITY_RE = re.compile(
    r"\bi\s+(?:can(?:not|'t)|do\s+not|don't)\s+(?:access|check|read|open|view)\b.*\bnotes?\b",
    re.IGNORECASE,
)
NOTES_FALLBACK_RE = re.compile(
    r"\b(?:paste|copy|share|screenshot|forward|dictate|send\s+me|if\s+you\s+(?:share|paste)|"
    r"open\s+notes|tell\s+me\s+the\s+content|provide\s+the\s+content|provide\s+note\s+content|"
    r"specific\s+folder|list\s+all\s+notes|list\s+likely\s+matches)\b",
    re.IGNORECASE,
)

REMINDER_INABILITY_RE = re.compile(
    r"\bi\s+(?:can(?:not|'t)|do\s+not|don't)\s+(?:set|create|schedule|manage)\b.*\breminder",
    re.IGNORECASE,
)
REMINDER_FALLBACK_RE = re.compile(
    r"\b(?:siri|reminders\s+app|calendar|shortcuts|fastest\s+fallback|quick\s+fallback|"
    r"i\s+can\s+(?:draft|give\s+steps|walk\s+you\s+through)|manual)\b",
    re.IGNORECASE,
)

WORKSPACE_PATHLIKE_RE = re.compile(
    r"(?:/Users/|\\.md\b|workspace|repo(?:sitory)?|tasks/|docs/|memory/)",
    re.IGNORECASE,
)
WORKSPACE_READ_CLAIM_RE = re.compile(
    r"\b(?:i\s+(?:checked|searched|looked\s+up|found|read|opened)|"
    r"here(?:'s|\s+is)\s+what\s+(?:it|the\s+note)\s+says)\b",
    re.IGNORECASE,
)
INTERNAL_MONOLOGUE_RE = re.compile(
    r"(?:\blet's assume\b|\bi might have to\b|\bgiven the output\b|\bthe skill\.md\b|"
    r"\bif there's no direct command\b|\bfor now, i'll\b)",
    re.IGNORECASE,
)


def _env_with_suppression(env: dict[str, str]) -> dict[str, str]:
    out = dict(env)
    out.setdefault("ORION_SUPPRESS_TELEGRAM", "1")
    out.setdefault("TELEGRAM_SUPPRESS", "1")
    out.setdefault("ORION_SUPPRESS_DISCORD", "1")
    out.setdefault("DISCORD_SUPPRESS", "1")
    out.setdefault("NOTIFY_DRY_RUN", "1")
    return out


def _openclaw_agent_json(
    *,
    agent: str,
    channel: str,
    session_id: str,
    message: str,
    thinking: str,
    timeout_s: int,
) -> dict:
    argv = [
        "openclaw",
        "agent",
        "--agent",
        agent,
        "--channel",
        channel,
        "--session-id",
        session_id,
        "--message",
        message,
        "--thinking",
        thinking,
        "--timeout",
        str(timeout_s),
        "--json",
    ]
    r = subprocess.run(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        env=_env_with_suppression(dict(os.environ)),
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "openclaw agent failed").strip())
    try:
        return json.loads(r.stdout)
    except Exception as e:
        raise RuntimeError(f"Could not parse openclaw --json output: {e}") from e


def _extract_response_text(run_obj: dict) -> str:
    payloads = (((run_obj or {}).get("result") or {}).get("payloads") or [])
    parts: list[str] = []
    for payload in payloads:
        txt = (payload or {}).get("text")
        if isinstance(txt, str) and txt.strip():
            parts.append(txt.strip())

    if parts:
        return "\n\n".join(parts).strip()

    # Fallbacks for shape drift.
    maybe = ((run_obj or {}).get("result") or {}).get("text")
    if isinstance(maybe, str) and maybe.strip():
        return maybe.strip()

    maybe2 = (run_obj or {}).get("text")
    if isinstance(maybe2, str) and maybe2.strip():
        return maybe2.strip()

    return ""


def _session_id(prefix: str, case_id: str) -> str:
    return f"{prefix}-{case_id.lower()}"


def _reset_main_telegram_session(repo_root: Path) -> dict:
    """
    Reset OpenClaw's long-lived main direct session key (agent:main:main) with backup.
    This keeps loop runs isolated from stale prior conversation state.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    sess_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    sess_store = sess_dir / "sessions.json"
    if not sess_store.exists():
        return {"reset": False, "reason": "sessions_store_missing"}

    obj = json.loads(sess_store.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        return {"reset": False, "reason": "sessions_store_not_dict"}

    entry = obj.get("agent:main:main")
    if not isinstance(entry, dict):
        return {"reset": False, "reason": "main_session_key_missing"}

    sid = str(entry.get("sessionId") or "").strip()
    backup_dir = repo_root / "eval" / "history" / f"session-backup-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(sess_store, backup_dir / "sessions.json.bak")
    sid_file = sess_dir / f"{sid}.jsonl" if sid else None
    if sid_file and sid_file.exists():
        shutil.copy2(sid_file, backup_dir / f"{sid}.jsonl.bak")

    del obj["agent:main:main"]
    sess_store.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

    if sid_file and sid_file.exists():
        sid_file.rename(backup_dir / f"{sid}.jsonl")

    r = subprocess.run(
        ["openclaw", "gateway", "restart"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    restarted = r.returncode == 0
    return {
        "reset": True,
        "backup_dir": str(backup_dir),
        "removed_session_id": sid,
        "gateway_restarted": restarted,
        "restart_stdout": (r.stdout or "").strip(),
        "restart_stderr": (r.stderr or "").strip(),
    }


def _add_check(checks: list[CaseCheck], check_id: str, passed: bool, hard: bool, note: str) -> None:
    checks.append(CaseCheck(check_id=check_id, passed=bool(passed), hard=bool(hard), note=note))


def _score_case(case: PromptCase, response_text: str) -> tuple[bool, bool, list[CaseCheck], list[str]]:
    t = (response_text or "").strip()
    tl = t.lower()

    checks: list[CaseCheck] = []
    notes: list[str] = []

    _add_check(checks, "nonempty_response", bool(t), True, "Response must not be empty.")
    _add_check(
        checks,
        "no_internal_monologue_leak",
        not bool(INTERNAL_MONOLOGUE_RE.search(t)),
        True,
        "Hard fail if internal monologue/planning text leaks into Telegram output.",
    )

    # Global hard failures.
    _add_check(
        checks,
        "no_email_address_claim",
        not bool(NO_EMAIL_ADDRESS_RE.search(t)),
        True,
        "Hard fail if ORION claims it has no email address.",
    )

    if case.category == "notes":
        notes_inability = bool(NOTES_INABILITY_RE.search(t))
        notes_fallback = bool(NOTES_FALLBACK_RE.search(t))
        _add_check(
            checks,
            "notes_inability_has_fallback",
            (not notes_inability) or notes_fallback,
            True,
            "Hard fail if Notes inability is stated without a viable fallback (paste/share/screenshot/etc).",
        )

        hallucinated_workspace_lookup = bool(
            ("workspace" in tl)
            or (WORKSPACE_PATHLIKE_RE.search(t) and WORKSPACE_READ_CLAIM_RE.search(tl))
        )
        _add_check(
            checks,
            "no_workspace_file_hallucination_for_notes",
            not hallucinated_workspace_lookup,
            True,
            "Hard fail on obvious workspace-file hallucination while claiming Apple Notes lookup.",
        )

    if case.category == "reminders":
        reminder_inability = bool(REMINDER_INABILITY_RE.search(t))
        reminder_fallback = bool(REMINDER_FALLBACK_RE.search(t))
        _add_check(
            checks,
            "reminder_inability_has_fallback",
            (not reminder_inability) or reminder_fallback,
            True,
            "Hard fail if reminder inability is stated without a viable fallback path.",
        )

    # Case-specific expectations (soft unless explicitly marked hard).
    if case.case_id == "C1":
        boundary_or_consent = bool(
            re.search(
                r"\b(?:cannot|can't|can't directly|with your permission|confirm|guide you|walk you through)\b",
                tl,
            )
            or re.search(r"\bwhat would you like me to do\b", tl)
            or re.search(r"\bwhat specifically would you like(?:\s+to)?\b", tl)
            or re.search(r"\btell me the exact action\b", tl)
        )
        _add_check(
            checks,
            "mac_control_boundary_or_consent",
            boundary_or_consent,
            False,
            "Should set boundaries or request explicit permission/intent for Mac control.",
        )

        false_immediate_control = bool(re.search(r"\b(?:controlling your mac now|i have taken control of your mac)\b", tl))
        _add_check(
            checks,
            "no_false_immediate_mac_control_claim",
            not false_immediate_control,
            True,
            "Must not claim immediate Mac control without a real confirmed action path.",
        )

    elif case.case_id == "C2":
        task_pull_or_clarify = bool(
            re.search(
                r"\b(?:tasks?|inbox|task list|which task system|where should i check|want me to pull|i can check|here are your tasks?)\b",
                tl,
            )
            or "?" in t
        )
        _add_check(
            checks,
            "tasks_has_pull_or_clarification",
            task_pull_or_clarify,
            False,
            "Should pull tasks or ask a concrete clarification about task source.",
        )

    elif case.case_id == "C3":
        notes_actionable = bool(
            re.search(
                r"\b(?:share|paste|screenshot|forward|open notes|send me the note|i can summarize)\b",
                tl,
            )
            or re.search(r"\bi will check\b.*\bnotes\b", tl)
            or re.search(r"\bi will\b.*\blist\b.*\bnotes\b", tl)
            or re.search(r"\bplease wait\b.*\bretrieve\b", tl)
        )
        _add_check(
            checks,
            "notes_actionable_next_step",
            notes_actionable,
            False,
            "Should provide an actionable next step for Apple Notes lookup.",
        )

    elif case.case_id == "C4":
        email_route_present = bool(re.search(r"\b(?:email|agentmail|inbox|address|link)\b", tl))
        _add_check(
            checks,
            "email_route_discussed",
            email_route_present,
            False,
            "Should address email-link routing, not ignore the email topic.",
        )
        _add_check(
            checks,
            "agentmail_identity_present",
            "orion_gatewaybot@agentmail.to" in tl,
            True,
            "Hard fail if ORION does not provide the AgentMail inbox identity.",
        )

    elif case.case_id == "C5":
        atlas_delegation = "atlas" in tl
        _add_check(
            checks,
            "weekday_reminder_routes_to_atlas",
            atlas_delegation,
            False,
            "Expected ATLAS delegation for cron/reminder workflow.",
        )

        not_configured_phrase = "not configured yet" in tl
        _add_check(
            checks,
            "weekday_reminder_states_not_configured_yet",
            not_configured_phrase,
            False,
            "Expected explicit 'not configured yet' status before delegation.",
        )

    elif case.case_id == "C6":
        notes_actionable = bool(
            re.search(
                r"\b(?:share|paste|screenshot|forward|open notes|send me the note|i can summarize|"
                r"specific folder|list all notes|list likely matches)\b",
                tl,
            )
        )
        _add_check(
            checks,
            "notes_summary_actionable_next_step",
            notes_actionable,
            False,
            "Should provide a practical fallback for note retrieval.",
        )

    elif case.case_id == "C7":
        consent_or_details = bool(re.search(r"\b(?:confirm|recipient|subject|send now|approve|cc|what should i write|want me to)\b", tl))
        _add_check(
            checks,
            "email_send_requests_consent_or_details",
            consent_or_details,
            False,
            "Should confirm details/consent before claiming send actions.",
        )

    elif case.case_id == "C8":
        reminder_step = bool(
            re.search(
                r"\b(?:reminder|tomorrow|8am|siri|reminders app|calendar|shortcuts|fastest fallback)\b",
                tl,
            )
        )
        _add_check(
            checks,
            "single_reminder_has_actionable_path",
            reminder_step,
            False,
            "Should provide direct setup or a concrete fallback path.",
        )

    failed = [c for c in checks if not c.passed]
    hard_failed = [c for c in failed if c.hard]

    for chk in failed:
        level = "HARD" if chk.hard else "SOFT"
        notes.append(f"{level}: {chk.check_id} - {chk.note}")

    passed = len(failed) == 0
    hard_fail = len(hard_failed) > 0
    return passed, hard_fail, checks, notes


def run_once(
    *,
    repo_root: Path,
    agent: str,
    channel: str,
    thinking: str,
    timeout_s: int,
    session_prefix: str,
    out_dir: Path,
    report_path: Path | None,
    stable_sessions: bool,
    reset_main_session: bool,
) -> dict:
    run_ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    target_report = report_path or (out_dir / f"telegram-realworld-{run_ts}.json")

    results: list[CaseResult] = []
    started_run = time.monotonic()
    reset_info = _reset_main_telegram_session(repo_root) if reset_main_session else {"reset": False, "reason": "disabled"}

    for case in CASES:
        sid_prefix = session_prefix if stable_sessions else f"{session_prefix}-{run_ts}"
        session_id = _session_id(sid_prefix, case.case_id)
        started = time.monotonic()
        error_note: str | None = None
        response_text = ""

        try:
            run_obj = _openclaw_agent_json(
                agent=agent,
                channel=channel,
                session_id=session_id,
                message=case.prompt,
                thinking=thinking,
                timeout_s=timeout_s,
            )
            response_text = _extract_response_text(run_obj)
            if not response_text.strip():
                # Occasionally we get an empty payload from transient model/runtime errors.
                # Retry once before grading.
                run_obj_retry = _openclaw_agent_json(
                    agent=agent,
                    channel=channel,
                    session_id=session_id,
                    message=case.prompt,
                    thinking=thinking,
                    timeout_s=timeout_s,
                )
                response_text = _extract_response_text(run_obj_retry)
        except Exception as e:
            error_note = f"openclaw_error: {e}"

        duration_ms = int((time.monotonic() - started) * 1000)
        passed, hard_fail, checks, notes = _score_case(case, response_text)

        if error_note:
            notes.insert(0, error_note)
            passed = False
            hard_fail = True

        results.append(
            CaseResult(
                case_id=case.case_id,
                title=case.title,
                prompt=case.prompt,
                category=case.category,
                session_id=session_id,
                response_text=response_text,
                duration_ms=duration_ms,
                passed=passed,
                hard_fail=hard_fail,
                checks=checks,
                notes=notes,
            )
        )

    run_duration_ms = int((time.monotonic() - started_run) * 1000)
    pass_count = sum(1 for r in results if r.passed)
    fail_count = len(results) - pass_count
    hard_fail_count = sum(1 for r in results if r.hard_fail)
    avg_duration_ms = int(round(sum(r.duration_ms for r in results) / len(results))) if results else 0

    report = {
        "kind": "telegram_realworld_loop_test",
        "schema_version": 1,
        "timestamp": run_ts,
        "repo_root": str(repo_root),
        "agent": agent,
        "channel": channel,
        "thinking": thinking,
        "timeout_s": timeout_s,
        "session_prefix": session_prefix,
        "timing": {
            "run_duration_ms": run_duration_ms,
            "avg_case_duration_ms": avg_duration_ms,
        },
        "summary": {
            "total": len(results),
            "pass": pass_count,
            "fail": fail_count,
            "hard_fail": hard_fail_count,
        },
        "session_reset": reset_info,
        "results": [
            {
                "case_id": r.case_id,
                "title": r.title,
                "prompt": r.prompt,
                "category": r.category,
                "session_id": r.session_id,
                "response_text": r.response_text,
                "duration_ms": r.duration_ms,
                "passed": r.passed,
                "hard_fail": r.hard_fail,
                "checks": [dataclasses.asdict(c) for c in r.checks],
                "notes": r.notes,
            }
            for r in results
        ],
    }

    target_report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print("REALWORLD_LOOP_EVAL")
    print(f"cases: {len(results)}")
    print(f"pass_fail: {pass_count}/{fail_count}")
    print(f"hard_failures: {hard_fail_count}")
    print(f"timing_ms: run={run_duration_ms} avg_case={avg_duration_ms}")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        hard = "HARD" if r.hard_fail else "SOFT"
        print(f"- {r.case_id} {status}/{hard} {r.duration_ms}ms :: {r.title}")
    print(f"report: {target_report}")

    return report


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run realistic Telegram loop tests against ORION and write an eval/history JSON report."
    )
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--agent", default="main", help="OpenClaw agent id (default: main)")
    ap.add_argument("--channel", default="telegram", help="OpenClaw channel (default: telegram)")
    ap.add_argument("--thinking", default="off", help="Thinking level (default: off)")
    ap.add_argument("--timeout", type=int, default=180, help="Per-prompt timeout seconds (default: 180)")
    ap.add_argument(
        "--session-prefix",
        default="looptest-telegram-realworld",
        help="Stable prefix for per-case session IDs (default: looptest-telegram-realworld)",
    )
    ap.add_argument(
        "--stable-sessions",
        action="store_true",
        help="Reuse stable per-case session IDs across runs (default: off, isolate by run timestamp).",
    )
    ap.add_argument(
        "--reset-main-session",
        action="store_true",
        help="Reset OpenClaw agent:main:main session before run (with backup) for clean-loop evaluation.",
    )
    ap.add_argument(
        "--out-dir",
        default="eval/history",
        help="Directory for timestamped JSON reports (default: eval/history)",
    )
    ap.add_argument(
        "--report-path",
        default=None,
        help="Explicit report output path (overrides --out-dir timestamped path)",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()

    run_once(
        repo_root=repo_root,
        agent=args.agent,
        channel=args.channel,
        thinking=args.thinking,
        timeout_s=max(30, int(args.timeout)),
        session_prefix=str(args.session_prefix),
        out_dir=(repo_root / args.out_dir),
        report_path=(Path(args.report_path).resolve() if args.report_path else None),
        stable_sessions=bool(args.stable_sessions),
        reset_main_session=bool(args.reset_main_session),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
