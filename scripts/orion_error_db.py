#!/usr/bin/env python3
"""
Repo-local ORION operational error tracker.

This keeps a machine-oriented record of recurring failures while leaving
tasks/INCIDENTS.md as the human/audit layer.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any


ISO_UTC = "%Y-%m-%dT%H:%M:%SZ"
SEVERITY_ORDER = {"info": 0, "warn": 1, "error": 2}
INCIDENT_RE = re.compile(r"^INCIDENT v1\s*$", re.MULTILINE)
KV_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z _-]*):\s*(?P<value>.*)\s*$")
ERROR_LINE_RE = re.compile(r"(error|failed|failure|timeout|exception|abort)", re.IGNORECASE)
INCIDENT_APPEND_SUMMARY_MAX_BYTES = 1024
INCIDENT_APPEND_SUMMARY_FALLBACK = "no summary provided"


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def db_path(path: str | None, root: Path) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return (root / "db" / "orion-ops.sqlite").resolve()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime(ISO_UTC)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def stable_fingerprint(parts: list[str]) -> str:
    norm = " | ".join(normalize_text(p).lower() for p in parts if normalize_text(p))
    digest = hashlib.sha1(norm.encode("utf-8", errors="replace")).hexdigest()
    return digest[:16]


def sanitize_incident_summary(raw_summary: str, max_bytes: int = INCIDENT_APPEND_SUMMARY_MAX_BYTES) -> str:
    normalized = normalize_text(raw_summary or "")
    if not normalized:
        return INCIDENT_APPEND_SUMMARY_FALLBACK

    safe = normalized.replace("\x00", "")
    safe = safe.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    safe = re.sub(r"\s+", " ", safe).strip()
    encoded = safe.encode("utf-8", errors="replace")
    if len(encoded) > max_bytes:
        safe = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or INCIDENT_APPEND_SUMMARY_FALLBACK


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS error_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          direction TEXT NOT NULL,
          source TEXT NOT NULL,
          subsystem TEXT NOT NULL,
          severity TEXT NOT NULL,
          fingerprint TEXT NOT NULL,
          summary TEXT NOT NULL,
          raw_excerpt TEXT,
          session_id TEXT,
          run_id TEXT,
          ticket_ref TEXT,
          incident_id TEXT,
          status TEXT NOT NULL DEFAULT 'open',
          artifact_path TEXT
        );
        CREATE TABLE IF NOT EXISTS error_fingerprints (
          fingerprint TEXT PRIMARY KEY,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          occurrences INTEGER NOT NULL DEFAULT 1,
          last_summary TEXT NOT NULL,
          last_source TEXT NOT NULL,
          last_status TEXT NOT NULL DEFAULT 'open',
          auto_fixable INTEGER NOT NULL DEFAULT 0,
          last_fix_at TEXT
        );
        CREATE TABLE IF NOT EXISTS review_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          window_hours INTEGER NOT NULL,
          events_scanned INTEGER NOT NULL DEFAULT 0,
          recurring_groups INTEGER NOT NULL DEFAULT 0,
          fixes_attempted INTEGER NOT NULL DEFAULT 0,
          fixes_applied INTEGER NOT NULL DEFAULT 0,
          report_path TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_error_event_dedupe
          ON error_events (created_at, fingerprint, source, summary);
        CREATE INDEX IF NOT EXISTS idx_error_events_created_at
          ON error_events (created_at);
        CREATE INDEX IF NOT EXISTS idx_error_events_fingerprint
          ON error_events (fingerprint);
        """
    )
    return conn


def upsert_event(
    conn: sqlite3.Connection,
    *,
    created_at: str,
    direction: str,
    source: str,
    subsystem: str,
    severity: str,
    fingerprint: str,
    summary: str,
    raw_excerpt: str = "",
    session_id: str = "",
    run_id: str = "",
    ticket_ref: str = "",
    incident_id: str = "",
    status: str = "open",
    artifact_path: str = "",
) -> bool:
    payload = (
        created_at,
        direction,
        source,
        subsystem,
        severity,
        fingerprint,
        normalize_text(summary),
        normalize_text(raw_excerpt),
        session_id or None,
        run_id or None,
        ticket_ref or None,
        incident_id or None,
        status,
        artifact_path or None,
    )
    before = conn.total_changes
    conn.execute(
        """
        INSERT OR IGNORE INTO error_events (
          created_at, direction, source, subsystem, severity, fingerprint, summary,
          raw_excerpt, session_id, run_id, ticket_ref, incident_id, status, artifact_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    inserted = conn.total_changes > before
    if inserted:
        row = conn.execute(
            "SELECT fingerprint, first_seen_at, occurrences, auto_fixable FROM error_fingerprints WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO error_fingerprints (
                  fingerprint, first_seen_at, last_seen_at, occurrences, last_summary, last_source, last_status, auto_fixable
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    fingerprint,
                    created_at,
                    created_at,
                    normalize_text(summary),
                    source,
                    status,
                    1 if is_auto_fixable(summary, subsystem) else 0,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE error_fingerprints
                SET last_seen_at = ?,
                    occurrences = occurrences + 1,
                    last_summary = ?,
                    last_source = ?,
                    last_status = ?,
                    auto_fixable = CASE WHEN auto_fixable = 1 OR ? = 1 THEN 1 ELSE 0 END
                WHERE fingerprint = ?
                """,
                (
                    created_at,
                    normalize_text(summary),
                    source,
                    status,
                    1 if is_auto_fixable(summary, subsystem) else 0,
                    fingerprint,
                ),
            )
    return inserted


def is_auto_fixable(summary: str, subsystem: str) -> bool:
    text = f"{subsystem} {summary}".lower()
    needles = ("config", "binding", "plugin", "hook", "session", "stale", "queue")
    return any(n in text for n in needles)


def parse_incidents(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    blocks: list[dict[str, Any]] = []
    current: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if INCIDENT_RE.match(raw):
            if current:
                blocks.append(_parse_incident_block(current))
            current = [raw]
        elif current:
            current.append(raw)
    if current:
        blocks.append(_parse_incident_block(current))
    return [b for b in blocks if b]


def _parse_incident_block(lines: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    current_section: str | None = None
    for line in lines[1:]:
        m = KV_RE.match(line)
        if m:
            key = m.group("key").strip()
            value = m.group("value").strip()
            if key in {"Evidence", "Actions", "Follow-up Tasks"}:
                fields[key] = [value] if value else []
                current_section = key
            else:
                fields[key] = value
                current_section = None
            continue
        if current_section and line.strip().startswith("- "):
            fields.setdefault(current_section, []).append(line.strip()[2:].strip())
    return fields


def ingest_incidents(conn: sqlite3.Connection, root: Path) -> int:
    path = root / "tasks" / "INCIDENTS.md"
    count = 0
    for item in parse_incidents(path):
        summary = str(item.get("Summary", "")).strip()
        if not summary:
            continue
        trigger = str(item.get("Trigger", "")).strip()
        incident_id = str(item.get("Id", "")).strip()
        opened = str(item.get("Opened", "")).strip() or now_utc()
        severity = _severity_from_incident(str(item.get("Severity", "P2")))
        evidence = "; ".join(item.get("Evidence") or [])
        fingerprint = stable_fingerprint(["incident", trigger, summary])
        inserted = upsert_event(
            conn,
            created_at=opened,
            direction="received",
            source="incident",
            subsystem="orion-ops",
            severity=severity,
            fingerprint=fingerprint,
            summary=summary,
            raw_excerpt=evidence,
            incident_id=incident_id,
            status="escalated" if str(item.get("Closed", "open")).strip().lower() == "open" else "fixed",
            artifact_path=str(path.relative_to(root)),
        )
        count += 1 if inserted else 0
    conn.commit()
    return count


def _severity_from_incident(severity: str) -> str:
    sev = severity.strip().upper()
    return {"P0": "error", "P1": "error", "P2": "warn"}.get(sev, "warn")


def ingest_packets(conn: sqlite3.Connection, root: Path) -> int:
    try:
        from assistant_common import load_packets  # type: ignore
    except Exception:
        return 0
    count = 0
    for packet in load_packets(root):
        result = (packet.result_status or "").upper()
        if result not in {"FAILED", "BLOCKED"}:
            continue
        owner = packet.fields.get("Owner", "UNKNOWN").strip()
        objective = packet.fields.get("Objective", "(no objective)").strip()
        fingerprint = stable_fingerprint(["packet", owner, result, objective])
        inserted = upsert_event(
            conn,
            created_at=now_utc(),
            direction="initiated",
            source="task-packet",
            subsystem=owner.lower(),
            severity="error" if result == "FAILED" else "warn",
            fingerprint=fingerprint,
            summary=f"{owner} packet {result.lower()}: {objective}",
            raw_excerpt=f"{packet.inbox_path}:{packet.start_line}",
            status="open",
            artifact_path=str(packet.inbox_path.relative_to(root)),
        )
        count += 1 if inserted else 0
    conn.commit()
    return count


def _default_gateway_log_paths() -> list[Path]:
    paths = [
        Path.home() / ".openclaw" / "logs" / "gateway.err.log",
        Path("/tmp/openclaw") / f"openclaw-{dt.date.today().isoformat()}.log",
    ]
    return [p for p in paths if p.exists()]


def ingest_gateway_logs(conn: sqlite3.Connection, root: Path, path: Path | None = None, *, limit_lines: int = 400) -> int:
    targets = [path.resolve()] if path else _default_gateway_log_paths()
    count = 0
    for target in targets:
        if not target.exists():
            continue
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit_lines:]
        for line in lines:
            if not ERROR_LINE_RE.search(line):
                continue
            summary = normalize_text(line)
            fingerprint = stable_fingerprint(["gateway-log", _coarse_log_bucket(summary)])
            inserted = upsert_event(
                conn,
                created_at=now_utc(),
                direction="received",
                source="gateway-log",
                subsystem="gateway",
                severity="error" if "error" in summary.lower() or "exception" in summary.lower() else "warn",
                fingerprint=fingerprint,
                summary=_coarse_log_bucket(summary),
                raw_excerpt=summary[:400],
                artifact_path=str(target),
            )
            count += 1 if inserted else 0
    conn.commit()
    return count


def _coarse_log_bucket(line: str) -> str:
    text = line.lower()
    for token in (
        "lane wait exceeded",
        "timeout",
        "aborterror",
        "config",
        "plugin",
        "binding collision",
        "gateway",
        "session",
        "telegram",
        "discord",
    ):
        if token in text:
            return token
    return text[:120]


def _run_command(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
            env=merged_env,
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {"cmd": cmd, "exit_code": 99, "stdout": "", "stderr": str(exc)}


def _safe_fix_commands(root: Path, recurring: list[dict[str, Any]]) -> list[tuple[list[str], dict[str, str] | None]]:
    commands: list[tuple[list[str], dict[str, str] | None]] = [
        (["openclaw", "config", "validate", "--json"], None),
        (["openclaw", "agents", "bindings", "--json"], None),
        (["openclaw", "plugins", "list", "--json"], None),
        (["openclaw", "hooks", "list"], None),
        (["openclaw", "gateway", "status", "--json"], None),
        (["python3", "scripts/task_execution_loop.py", "--repo-root", str(root), "--apply", "--stale-hours", "24"], None),
    ]
    text = " ".join(str(item.get("summary") or "").lower() for item in recurring)
    if any(token in text for token in ("session", "listener invoked outside active run", "backing session missing", "stale", "lost")):
        commands.append((["python3", "scripts/runtime_reconcile.py", "--repo-root", str(root), "--apply", "--json"], None))
        commands.append((["python3", "scripts/task_registry_repair.py", "--repo-root", str(root), "--apply", "--json"], None))
        commands.append(
            (
                [
                    "python3",
                    "scripts/session_maintenance.py",
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--apply",
                    "--doctor",
                    "--min-missing",
                    "1",
                    "--min-reclaim",
                    "1",
                    "--json",
                ],
                {"AUTO_OK": "1"},
            )
        )
    else:
        commands.append((["openclaw", "sessions", "cleanup", "--agent", "main", "--dry-run", "--fix-missing", "--json"], None))
    if "discord" in text:
        commands.append((["openclaw", "channels", "status", "--probe", "--json"], None))
        commands.append((["openclaw", "channels", "logs", "--channel", "discord", "--json", "--lines", "200"], None))
    return commands


def _events_since(conn: sqlite3.Connection, hours: int) -> list[sqlite3.Row]:
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime(ISO_UTC)
    return conn.execute(
        """
        SELECT *
        FROM error_events
        WHERE created_at >= ?
        ORDER BY created_at DESC
        """,
        (cutoff,),
    ).fetchall()


def _write_review_report(root: Path, payload: dict[str, Any]) -> Path:
    path = root / "tasks" / "NOTES" / "error-review.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ORION Error Review",
        "",
        f"Generated: {payload['generated_at']}",
        f"Window: last {payload['window_hours']}h",
        "",
        "## Summary",
        f"- Events scanned: {payload['events_scanned']}",
        f"- Recurring groups: {payload['recurring_groups']}",
        f"- Fixes attempted: {payload['fixes_attempted']}",
        f"- Fixes applied: {payload['fixes_applied']}",
        "",
        "## Recurring Errors",
    ]
    if payload["recurring"]:
        for item in payload["recurring"]:
            lines.append(
                f"- `{item['fingerprint']}` [{item['severity']}] x{item['occurrences']} :: {item['summary']}"
            )
    else:
        lines.append("- No recurring errors in the review window.")
    lines.append("")
    lines.append("## Safe Fix Attempts")
    if payload["fix_results"]:
        for item in payload["fix_results"]:
            cmd = " ".join(item["cmd"])
            lines.append(f"- `{cmd}` -> exit {item['exit_code']}")
    else:
        lines.append("- No safe fixes attempted.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _maybe_append_incident(root: Path, item: dict[str, Any]) -> str | None:
    if item["severity"] != "error" or item["occurrences"] < 3:
        return None
    summary = sanitize_incident_summary(item["summary"])
    cmd = [
        "bash",
        "scripts/incident_append.sh",
        "--opened-by",
        "ORION",
        "--severity",
        "P1",
        "--trigger",
        "ORION_RECURRING_ERROR",
        "--summary",
        summary,
        "--evidence",
        f"fingerprint={item['fingerprint']} occurrences={item['occurrences']}",
        "--action",
        "Nightly ORION error review escalated the recurring error.",
        "--follow-up-owner",
        "ATLAS",
        "--follow-up",
        "Review recurring runtime error and harden the prevention path.",
        "--closed",
        "open",
    ]
    proc = _run_command(cmd, cwd=root)
    if proc["exit_code"] == 0:
        out = proc["stdout"]
        m = re.search(r"id=([A-Z0-9\-]+)", out)
        return m.group(1) if m else "INC-UNKNOWN"
    return None


def cmd_record(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    conn = open_db(db_path(args.db, root))
    fingerprint = args.fingerprint or stable_fingerprint([args.source, args.subsystem, args.summary])
    inserted = upsert_event(
        conn,
        created_at=args.created_at or now_utc(),
        direction=args.direction,
        source=args.source,
        subsystem=args.subsystem,
        severity=args.severity,
        fingerprint=fingerprint,
        summary=args.summary,
        raw_excerpt=args.raw_excerpt,
        session_id=args.session_id,
        run_id=args.run_id,
        ticket_ref=args.ticket_ref,
        incident_id=args.incident_id,
        status=args.status,
        artifact_path=args.artifact_path,
    )
    conn.commit()
    payload = {"ok": True, "inserted": inserted, "fingerprint": fingerprint}
    print(json.dumps(payload, indent=2) if args.json else payload)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    conn = open_db(db_path(args.db, root))
    rows = conn.execute(
        """
        SELECT fingerprint, occurrences, last_summary, last_source, last_status
        FROM error_fingerprints
        ORDER BY occurrences DESC, last_seen_at DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    payload = {
        "fingerprints": [dict(r) for r in rows],
        "events": conn.execute("SELECT COUNT(*) FROM error_events").fetchone()[0],
    }
    print(json.dumps(payload, indent=2) if args.json else payload)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    conn = open_db(db_path(args.db, root))
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).strftime(ISO_UTC)
    before = conn.execute("SELECT COUNT(*) FROM error_events").fetchone()[0]
    conn.execute("DELETE FROM error_events WHERE created_at < ?", (cutoff,))
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM error_events").fetchone()[0]
    payload = {"ok": True, "deleted": before - after, "remaining": after}
    print(json.dumps(payload, indent=2) if args.json else payload)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    root = repo_root(args.repo_root)
    conn = open_db(db_path(args.db, root))
    started_at = now_utc()
    inserted = 0
    inserted += ingest_incidents(conn, root)
    inserted += ingest_packets(conn, root)
    if args.ingest_gateway_logs:
        inserted += ingest_gateway_logs(conn, root, limit_lines=args.gateway_log_lines)

    rows = _events_since(conn, args.window_hours)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row["fingerprint"],
            {
                "fingerprint": row["fingerprint"],
                "summary": row["summary"],
                "severity": row["severity"],
                "occurrences": 0,
                "sources": set(),
                "latest_status": row["status"],
            },
        )
        bucket["occurrences"] += 1
        bucket["sources"].add(row["source"])
        if SEVERITY_ORDER.get(row["severity"], 0) > SEVERITY_ORDER.get(bucket["severity"], 0):
            bucket["severity"] = row["severity"]
    recurring = sorted(
        [
            {
                **item,
                "sources": sorted(item["sources"]),
            }
            for item in grouped.values()
            if item["occurrences"] >= args.recurring_threshold
        ],
        key=lambda x: (-x["occurrences"], -SEVERITY_ORDER.get(x["severity"], 0), x["summary"]),
    )

    fix_results: list[dict[str, Any]] = []
    fixes_attempted = 0
    fixes_applied = 0
    if args.apply_safe_fixes and recurring:
        for cmd, env in _safe_fix_commands(root, recurring):
            result = _run_command(cmd, cwd=root, env=env)
            fix_results.append(result)
            fixes_attempted += 1
            if result["exit_code"] == 0:
                fixes_applied += 1

    escalations: list[str] = []
    if args.escalate_incidents:
        for item in recurring:
            incident_id = _maybe_append_incident(root, item)
            if incident_id:
                escalations.append(incident_id)
                conn.execute(
                    "UPDATE error_fingerprints SET last_status = 'escalated' WHERE fingerprint = ?",
                    (item["fingerprint"],),
                )
    generated_at = now_utc()
    payload = {
        "generated_at": generated_at,
        "window_hours": args.window_hours,
        "events_scanned": len(rows),
        "events_inserted": inserted,
        "recurring_groups": len(recurring),
        "recurring": recurring[: args.limit],
        "fixes_attempted": fixes_attempted,
        "fixes_applied": fixes_applied,
        "fix_results": fix_results,
        "escalations": escalations,
    }
    report_path = _write_review_report(root, payload)
    conn.execute(
        """
        INSERT INTO review_runs (
          started_at, completed_at, window_hours, events_scanned, recurring_groups,
          fixes_attempted, fixes_applied, report_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started_at,
            now_utc(),
            args.window_hours,
            len(rows),
            len(recurring),
            fixes_attempted,
            fixes_applied,
            str(report_path.relative_to(root)),
        ),
    )
    conn.commit()
    payload["report_path"] = str(report_path.relative_to(root))
    print(json.dumps(payload, indent=2) if args.json else payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track and review ORION operational errors.")
    parser.add_argument("--repo-root", help="Override repo root.")
    parser.add_argument("--db", help="Override sqlite DB path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    record = sub.add_parser("record", help="Record one error event.")
    record.add_argument("--created-at")
    record.add_argument("--direction", required=True, choices=["created", "initiated", "received"])
    record.add_argument("--source", required=True)
    record.add_argument("--subsystem", required=True)
    record.add_argument("--severity", required=True, choices=["info", "warn", "error"])
    record.add_argument("--summary", required=True)
    record.add_argument("--raw-excerpt", default="")
    record.add_argument("--fingerprint", default="")
    record.add_argument("--session-id", default="")
    record.add_argument("--run-id", default="")
    record.add_argument("--ticket-ref", default="")
    record.add_argument("--incident-id", default="")
    record.add_argument("--status", default="open")
    record.add_argument("--artifact-path", default="")
    record.add_argument("--json", action="store_true")
    record.set_defaults(func=cmd_record)

    stats = sub.add_parser("stats", help="Show DB summary.")
    stats.add_argument("--limit", type=int, default=10)
    stats.add_argument("--json", action="store_true")
    stats.set_defaults(func=cmd_stats)

    prune = sub.add_parser("prune", help="Delete old events.")
    prune.add_argument("--days", type=int, default=30)
    prune.add_argument("--json", action="store_true")
    prune.set_defaults(func=cmd_prune)

    review = sub.add_parser("review", help="Ingest and review recent errors.")
    review.add_argument("--window-hours", type=int, default=24)
    review.add_argument("--gateway-log-lines", type=int, default=400)
    review.add_argument("--limit", type=int, default=10)
    review.add_argument("--recurring-threshold", type=int, default=2)
    review.add_argument("--apply-safe-fixes", action="store_true")
    review.add_argument("--escalate-incidents", action="store_true")
    review.add_argument("--ingest-gateway-logs", action="store_true", default=True)
    review.add_argument("--json", action="store_true")
    review.set_defaults(func=cmd_review)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
