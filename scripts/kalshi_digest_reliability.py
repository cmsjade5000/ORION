#!/usr/bin/env python3
"""
Kalshi digest delivery reliability monitor.

Capabilities:
- Guard: alert when the 07:00 ET digest cron run is marked ok but no email is
  observed within the configured grace window.
- Daily report: summarize expected digest slots vs observed runs/sends.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class CronRun:
    run_at: dt.datetime
    status: str
    summary: str
    error: str
    run_at_ms: int


@dataclass(frozen=True)
class SentEmail:
    ts: dt.datetime
    subject: str
    to: tuple[str, ...]
    message_id: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _openclaw_cmd(repo_root: Path) -> list[str]:
    wrapper = repo_root / "scripts" / "openclaww.sh"
    if wrapper.exists():
        return [str(wrapper)]
    return ["openclaw"]


def _run_json(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "unknown error"
        raise RuntimeError(f"command failed: {' '.join(cmd)} ({err})")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON from command: {' '.join(cmd)}") from exc


def _detect_kalshi_digest_job_id(repo_root: Path) -> str:
    cmd = _openclaw_cmd(repo_root) + ["cron", "list", "--json"]
    obj = _run_json(cmd, cwd=repo_root)
    jobs = obj.get("jobs") or []
    for job in jobs:
        if str(job.get("name") or "").strip() == "kalshi-ref-arb-digest":
            jid = str(job.get("id") or "").strip()
            if jid:
                return jid
    raise RuntimeError("could not auto-detect cron id for job name 'kalshi-ref-arb-digest'")


def load_cron_runs(repo_root: Path, *, job_id: str, tz: ZoneInfo, limit: int) -> list[CronRun]:
    cmd = _openclaw_cmd(repo_root) + ["cron", "runs", "--id", job_id, "--limit", str(int(limit))]
    obj = _run_json(cmd, cwd=repo_root)
    entries = obj.get("entries") or []
    out: list[CronRun] = []
    for e in entries:
        if e.get("action") != "finished":
            continue
        run_at_ms = int(e.get("runAtMs") or 0)
        if run_at_ms <= 0:
            continue
        out.append(
            CronRun(
                run_at=dt.datetime.fromtimestamp(run_at_ms / 1000.0, tz=tz),
                status=str(e.get("status") or ""),
                summary=str(e.get("summary") or ""),
                error=str(e.get("error") or ""),
                run_at_ms=run_at_ms,
            )
        )
    out.sort(key=lambda x: x.run_at)
    return out


def load_agentmail_sent(
    repo_root: Path,
    *,
    inbox_id: str,
    tz: ZoneInfo,
    limit: int,
    recipient: str,
    subject_token: str,
) -> list[SentEmail]:
    cmd = ["node", str(repo_root / "skills" / "agentmail" / "cli.js"), "list-messages", inbox_id, str(int(limit))]
    obj = _run_json(cmd, cwd=repo_root)
    msgs = obj.get("messages") or []
    rec_l = recipient.strip().lower()
    token_l = subject_token.strip().lower()
    out: list[SentEmail] = []
    for m in msgs:
        labels = [str(x).lower() for x in (m.get("labels") or [])]
        if "sent" not in labels:
            continue
        tos = tuple(str(x).strip() for x in (m.get("to") or []))
        tos_l = {x.lower() for x in tos}
        if rec_l and rec_l not in tos_l:
            continue
        subject = str(m.get("subject") or "")
        if token_l and token_l not in subject.lower():
            continue
        raw_ts = str(m.get("timestamp") or "")
        if not raw_ts:
            continue
        try:
            ts = dt.datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).astimezone(tz)
        except ValueError:
            continue
        out.append(
            SentEmail(
                ts=ts,
                subject=subject,
                to=tos,
                message_id=str(m.get("message_id") or ""),
            )
        )
    out.sort(key=lambda x: x.ts)
    return out


def _is_slot_run(run: CronRun, *, day: dt.date, hour: int) -> bool:
    # Cron jobs can start a few minutes late when the queue is busy.
    # Treat any run within the slot hour as the scheduled slot run.
    return run.run_at.date() == day and run.run_at.hour == hour


def _find_slot_run(runs: list[CronRun], *, day: dt.date, hour: int) -> CronRun | None:
    for r in runs:
        if _is_slot_run(r, day=day, hour=hour):
            return r
    return None


def _find_email_for_run(
    run: CronRun,
    emails: list[SentEmail],
    *,
    before_seconds: int,
    after_seconds: int,
) -> SentEmail | None:
    lo = run.run_at - dt.timedelta(seconds=max(0, before_seconds))
    hi = run.run_at + dt.timedelta(seconds=max(0, after_seconds))
    for e in emails:
        if lo <= e.ts <= hi:
            return e
    return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return {}
    return {}


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_openclaw_telegram_chat_id() -> str:
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    chan = ((cfg.get("channels") or {}).get("telegram") or {})
    allow = chan.get("allowFrom") or chan.get("dm", {}).get("allowFrom") or []
    if not isinstance(allow, list) or not allow:
        raise RuntimeError("missing channels.telegram.allowFrom in ~/.openclaw/openclaw.json")
    return str(allow[0]).strip()


def _send_telegram(repo_root: Path, *, chat_id: str, text: str) -> None:
    cmd = ["bash", str(repo_root / "scripts" / "telegram_send_message.sh"), str(chat_id), text]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip() or "unknown error"
        raise RuntimeError(f"telegram send failed ({err})")


def evaluate_morning_guard(
    runs: list[CronRun],
    emails: list[SentEmail],
    *,
    day: dt.date,
    morning_hour: int,
    grace_minutes: int,
) -> tuple[str, CronRun | None, SentEmail | None]:
    run = _find_slot_run(runs, day=day, hour=morning_hour)
    if run is None:
        return ("no_run", None, None)
    if run.status.lower() != "ok":
        return ("run_not_ok", run, None)
    email = _find_email_for_run(run, emails, before_seconds=120, after_seconds=grace_minutes * 60)
    if email is None:
        return ("missing_email", run, None)
    return ("ok", run, email)


def render_daily_report(
    *,
    day: dt.date,
    runs: list[CronRun],
    emails: list[SentEmail],
    slot_hours: list[int],
    match_minutes: int,
    tz_name: str,
) -> str:
    slot_hours = sorted(slot_hours)
    lines: list[str] = []
    lines.append(f"ORION Kalshi Digest Reliability — {day.isoformat()} ({tz_name})")
    delivered = 0
    missing = 0
    run_errors = 0
    for hour in slot_hours:
        run = _find_slot_run(runs, day=day, hour=hour)
        if run is None:
            missing += 1
            lines.append(f"{hour:02d}:00 run=missing email=missing")
            continue
        email = _find_email_for_run(run, emails, before_seconds=120, after_seconds=match_minutes * 60)
        status = run.status.lower()
        if status != "ok":
            run_errors += 1
        if email is None:
            missing += 1
            lines.append(f"{hour:02d}:00 run={status or 'unknown'} email=missing")
            if run.summary:
                lines.append(f"  note: {run.summary.strip()[:140]}")
            elif run.error:
                lines.append(f"  note: {run.error.strip()[:140]}")
            continue
        delivered += 1
        lines.append(f"{hour:02d}:00 run={status or 'unknown'} email={email.ts.strftime('%H:%M:%S')}")
    lines.insert(1, f"Slots expected: {len(slot_hours)} | delivered: {delivered} | missing: {missing} | run_errors: {run_errors}")
    return "\n".join(lines)


def _parse_slot_hours(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        v = int(p)
        if v < 0 or v > 23:
            raise ValueError(f"invalid hour in --slot-hours: {v}")
        out.append(v)
    if not out:
        raise ValueError("--slot-hours produced no values")
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser(description="Monitor Kalshi digest email delivery reliability.")
    ap.add_argument("--job-id", default="", help="Cron job id. Default: auto-detect by name kalshi-ref-arb-digest.")
    ap.add_argument("--inbox-id", default="orion_gatewaybot@agentmail.to", help="AgentMail inbox id/email.")
    ap.add_argument("--recipient", default=os.environ.get("KALSHI_ARB_DIGEST_EMAIL_TO", "cory.stoner@icloud.com"), help="Recipient email to audit.")
    ap.add_argument("--subject-token", default="kalshi", help="Case-insensitive subject filter.")
    ap.add_argument("--tz", default="America/New_York", help="IANA timezone.")
    ap.add_argument("--morning-hour", type=int, default=7, help="Morning slot hour (local tz).")
    ap.add_argument("--grace-minutes", type=int, default=10, help="Guard grace window after run in minutes.")
    ap.add_argument("--slot-hours", default="7,15,23", help="Comma-separated expected daily slot hours.")
    ap.add_argument("--report-date", default="", help="Report date YYYY-MM-DD. Default: yesterday in local tz.")
    ap.add_argument("--runs-limit", type=int, default=200, help="Cron run history limit (OpenClaw max: 200).")
    ap.add_argument("--messages-limit", type=int, default=500, help="AgentMail history limit.")
    ap.add_argument("--report-match-minutes", type=int, default=30, help="Run-to-email matching window for daily report.")
    ap.add_argument("--state-path", default="tmp/kalshi_ref_arb/digest_delivery_monitor_state.json", help="State file path (repo-relative unless absolute).")
    ap.add_argument("--guard", action="store_true", help="Run morning guard check.")
    ap.add_argument("--daily-report", action="store_true", help="Build/send daily reliability report.")
    ap.add_argument("--send-telegram", action="store_true", help="Send guard/report messages to Telegram.")
    ap.add_argument("--telegram-chat-id", default="", help="Override Telegram chat id.")
    ap.add_argument("--stdout-json", action="store_true", help="Print machine-readable summary JSON.")
    args = ap.parse_args()

    repo_root = _repo_root()
    tz = ZoneInfo(args.tz)
    slot_hours = _parse_slot_hours(args.slot_hours)
    today = dt.datetime.now(tz).date()

    if not args.guard and not args.daily_report:
        do_guard = True
        do_daily = True
    else:
        do_guard = bool(args.guard)
        do_daily = bool(args.daily_report)

    job_id = args.job_id.strip() or _detect_kalshi_digest_job_id(repo_root)
    runs_limit = max(1, min(int(args.runs_limit), 200))
    runs = load_cron_runs(repo_root, job_id=job_id, tz=tz, limit=runs_limit)
    emails = load_agentmail_sent(
        repo_root,
        inbox_id=args.inbox_id,
        tz=tz,
        limit=args.messages_limit,
        recipient=args.recipient,
        subject_token=args.subject_token,
    )

    state_path = Path(args.state_path)
    if not state_path.is_absolute():
        state_path = repo_root / state_path
    state = _read_json(state_path)
    alerts_state = state.get("alerts")
    if not isinstance(alerts_state, dict):
        alerts_state = {}
        state["alerts"] = alerts_state
    reports_state = state.get("daily_reports")
    if not isinstance(reports_state, dict):
        reports_state = {}
        state["daily_reports"] = reports_state

    out_obj: dict[str, Any] = {
        "job_id": job_id,
        "runs_count": len(runs),
        "emails_count": len(emails),
        "guard": {},
        "daily_report": {},
    }
    pending_msgs: list[str] = []

    if do_guard:
        guard_status, guard_run, guard_email = evaluate_morning_guard(
            runs,
            emails,
            day=today,
            morning_hour=args.morning_hour,
            grace_minutes=args.grace_minutes,
        )
        out_obj["guard"] = {"status": guard_status}
        if guard_run is not None:
            out_obj["guard"]["run_at"] = guard_run.run_at.isoformat()
            out_obj["guard"]["run_status"] = guard_run.status
            out_obj["guard"]["run_at_ms"] = guard_run.run_at_ms
        if guard_email is not None:
            out_obj["guard"]["email_at"] = guard_email.ts.isoformat()
            out_obj["guard"]["subject"] = guard_email.subject

        print(f"GUARD {guard_status}")
        if guard_status == "missing_email" and guard_run is not None:
            key = f"{guard_run.run_at_ms}"
            if key not in alerts_state:
                pending_msgs.append(
                    (
                        "ORION ALERT: Kalshi 07:00 digest run was ok but no email was detected "
                        f"within {args.grace_minutes} minutes.\n"
                        f"Run: {guard_run.run_at.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                        f"(job {job_id})\nRecipient: {args.recipient}"
                    )
                )
                alerts_state[key] = int(dt.datetime.now(tz=dt.timezone.utc).timestamp())
                print("GUARD_ALERT queued")
            else:
                print("GUARD_ALERT already_sent")

    if do_daily:
        if args.report_date.strip():
            report_day = dt.date.fromisoformat(args.report_date.strip())
        else:
            report_day = today - dt.timedelta(days=1)
        report_text = render_daily_report(
            day=report_day,
            runs=runs,
            emails=emails,
            slot_hours=slot_hours,
            match_minutes=args.report_match_minutes,
            tz_name=args.tz,
        )
        report_key = report_day.isoformat()
        out_obj["daily_report"] = {"date": report_key, "text": report_text}
        print(report_text)
        if report_key not in reports_state:
            pending_msgs.append(report_text)
            reports_state[report_key] = int(dt.datetime.now(tz=dt.timezone.utc).timestamp())
            print("DAILY_REPORT queued")
        else:
            print("DAILY_REPORT already_sent")

    if args.send_telegram and pending_msgs:
        chat_id = args.telegram_chat_id.strip() or _read_openclaw_telegram_chat_id()
        for msg in pending_msgs:
            _send_telegram(repo_root, chat_id=chat_id, text=msg)
        print(f"TELEGRAM_SENT {len(pending_msgs)}")
    elif pending_msgs:
        print(f"PENDING_MESSAGES {len(pending_msgs)}")

    _write_json(state_path, state)

    if args.stdout_json:
        print(json.dumps(out_obj, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
