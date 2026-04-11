#!/usr/bin/env python3
"""
Conservative repair path for stale OpenClaw task-registry rows.

Why this exists:
- `openclaw tasks maintenance --apply` only prunes terminal tasks whose
  `cleanup_after` retention has already expired.
- Long-dead `lost` or `running` rows can therefore pollute the operator ledger
  for days after the underlying work is gone.

This tool does not invent new task state. It only:
- expedites pruning of old `lost` rows whose backing session is already gone
- force-reconciles very old `running` rows into terminal `lost` rows, then
  expedites their pruning through the normal OpenClaw maintenance path
- normalizes tiny terminal-task timestamp skew where `started_at` precedes
  `created_at` by a few milliseconds
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any


def repo_root(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def default_db_path() -> Path:
    return Path.home() / ".openclaw" / "tasks" / "runs.sqlite"


def db_path(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return default_db_path().resolve()


def backup_dir(root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (root / "tmp" / "task-registry-backups").resolve()


def report_dir(root: Path, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (root / "tasks" / "JOBS" / "runtime-repair").resolve()


def _query_rows(database: Path, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    con = sqlite3.connect(str(database))
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def _lost_candidates(database: Path, *, cutoff_ms: int) -> list[dict[str, Any]]:
    return _query_rows(
        database,
        """
        SELECT
          task_id,
          runtime,
          source_id,
          owner_key,
          scope_kind,
          child_session_key,
          agent_id,
          run_id,
          label,
          task,
          status,
          created_at,
          started_at,
          ended_at,
          last_event_at,
          cleanup_after,
          error
        FROM task_runs
        WHERE status = 'lost'
          AND lower(coalesce(error, '')) LIKE '%backing session missing%'
          AND coalesce(ended_at, last_event_at, created_at) <= ?
        ORDER BY created_at ASC
        """,
        (cutoff_ms,),
    )


def _stale_running_candidates(database: Path, *, cutoff_ms: int) -> list[dict[str, Any]]:
    return _query_rows(
        database,
        """
        SELECT
          task_id,
          runtime,
          source_id,
          owner_key,
          scope_kind,
          child_session_key,
          agent_id,
          run_id,
          label,
          task,
          status,
          created_at,
          started_at,
          ended_at,
          last_event_at,
          cleanup_after,
          error,
          progress_summary,
          terminal_summary
        FROM task_runs
        WHERE status = 'running'
          AND coalesce(last_event_at, started_at, created_at) <= ?
        ORDER BY created_at ASC
        """,
        (cutoff_ms,),
    )


def _timestamp_skew_candidates(database: Path, *, max_delta_ms: int) -> list[dict[str, Any]]:
    return _query_rows(
        database,
        """
        SELECT
          task_id,
          runtime,
          source_id,
          owner_key,
          scope_kind,
          child_session_key,
          agent_id,
          run_id,
          label,
          task,
          status,
          created_at,
          started_at,
          ended_at,
          last_event_at,
          cleanup_after,
          error,
          progress_summary,
          terminal_summary,
          terminal_outcome,
          (created_at - started_at) AS delta_ms
        FROM task_runs
        WHERE started_at IS NOT NULL
          AND created_at IS NOT NULL
          AND started_at < created_at
          AND (created_at - started_at) <= ?
          AND status NOT IN ('queued', 'running')
        ORDER BY (created_at - started_at) DESC, created_at ASC
        """,
        (max_delta_ms,),
    )


def _backup_database(database: Path, out_dir: Path, *, now_ts: int) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    backup = out_dir / f"runs-repair-{now_ts}.sqlite"
    src = sqlite3.connect(str(database))
    dst = sqlite3.connect(str(backup))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup


def _maintenance_apply(root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ["openclaw", "tasks", "maintenance", "--apply", "--json"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=120,
    )
    payload: Any | None = None
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        payload = None
    return {
        "cmd": ["openclaw", "tasks", "maintenance", "--apply", "--json"],
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "json": payload,
    }


def _apply_repairs(
    database: Path,
    *,
    now_ms: int,
    prune_before_ms: int,
    lost_ids: list[str],
    stale_ids: list[str],
    skew_ids: list[str],
) -> None:
    con = sqlite3.connect(str(database))
    try:
        con.execute("BEGIN IMMEDIATE")
        if lost_ids:
            placeholders = ",".join("?" for _ in lost_ids)
            con.execute(
                f"""
                UPDATE task_runs
                SET cleanup_after = CASE
                  WHEN cleanup_after IS NULL OR cleanup_after > ? THEN ?
                  ELSE cleanup_after
                END
                WHERE task_id IN ({placeholders})
                """,
                (prune_before_ms, prune_before_ms, *lost_ids),
            )
        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            con.execute(
                f"""
                UPDATE task_runs
                SET status = 'lost',
                    ended_at = COALESCE(ended_at, ?),
                    last_event_at = ?,
                    cleanup_after = ?,
                    error = COALESCE(NULLIF(error, ''), 'stale running task force-reconciled'),
                    terminal_summary = COALESCE(NULLIF(terminal_summary, ''), 'stale running task force-reconciled'),
                    terminal_outcome = 'lost'
                WHERE task_id IN ({placeholders})
                """,
                (now_ms, now_ms, prune_before_ms, *stale_ids),
            )
        if skew_ids:
            placeholders = ",".join("?" for _ in skew_ids)
            con.execute(
                f"""
                UPDATE task_runs
                SET created_at = started_at
                WHERE task_id IN ({placeholders})
                """,
                tuple(skew_ids),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _write_report(
    out_dir: Path,
    *,
    now_ts: int,
    payload: dict[str, Any],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"repair-{now_ts}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = out_dir / "latest.json"
    shutil.copyfile(path, latest)
    return path


def run(
    root: Path,
    *,
    database: Path,
    apply: bool,
    lost_hours: float,
    stale_running_hours: float,
    max_timestamp_skew_ms: int,
    backup_root: Path,
    report_root: Path,
) -> dict[str, Any]:
    now_ts = int(time.time())
    now_ms = now_ts * 1000
    lost_cutoff_ms = now_ms - int(lost_hours * 3600 * 1000)
    stale_cutoff_ms = now_ms - int(stale_running_hours * 3600 * 1000)
    prune_before_ms = now_ms - 1000

    lost_candidates = _lost_candidates(database, cutoff_ms=lost_cutoff_ms)
    stale_candidates = _stale_running_candidates(database, cutoff_ms=stale_cutoff_ms)
    skew_candidates = _timestamp_skew_candidates(database, max_delta_ms=max_timestamp_skew_ms)

    payload: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
        "apply_requested": apply,
        "db_path": str(database),
        "lost_hours": lost_hours,
        "stale_running_hours": stale_running_hours,
        "max_timestamp_skew_ms": max_timestamp_skew_ms,
        "candidates": {
            "lost": lost_candidates,
            "stale_running": stale_candidates,
            "timestamp_skew": skew_candidates,
        },
        "counts": {
            "lost": len(lost_candidates),
            "stale_running": len(stale_candidates),
            "timestamp_skew": len(skew_candidates),
        },
        "applied": False,
    }

    if apply and (lost_candidates or stale_candidates or skew_candidates):
        backup_path = _backup_database(database, backup_root, now_ts=now_ts)
        _apply_repairs(
            database,
            now_ms=now_ms,
            prune_before_ms=prune_before_ms,
            lost_ids=[row["task_id"] for row in lost_candidates],
            stale_ids=[row["task_id"] for row in stale_candidates],
            skew_ids=[row["task_id"] for row in skew_candidates],
        )
        maintenance = _maintenance_apply(root)
        payload["applied"] = True
        payload["backup_path"] = str(backup_path)
        payload["maintenance"] = maintenance

    report_path = _write_report(report_root, now_ts=now_ts, payload=payload)
    payload["report_path"] = str(report_path)
    payload["latest_report_path"] = str(report_root / "latest.json")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair stale OpenClaw task-registry rows conservatively.")
    ap.add_argument("--repo-root", help="Workspace root.")
    ap.add_argument("--db", help="Override task registry sqlite path.")
    ap.add_argument("--apply", action="store_true", help="Apply repairs and run task maintenance.")
    ap.add_argument("--lost-hours", type=float, default=12.0, help="Minimum age for orphaned lost rows.")
    ap.add_argument("--stale-running-hours", type=float, default=12.0, help="Minimum age for stale running rows.")
    ap.add_argument(
        "--max-timestamp-skew-ms",
        type=int,
        default=5000,
        help="Maximum terminal-task created/start skew to normalize.",
    )
    ap.add_argument("--backup-dir", help="Directory for sqlite backups.")
    ap.add_argument("--report-dir", help="Directory for JSON repair reports.")
    ap.add_argument("--json", action="store_true", help="Print machine-readable output.")
    args = ap.parse_args()

    root = repo_root(args.repo_root)
    payload = run(
        root,
        database=db_path(args.db),
        apply=args.apply,
        lost_hours=args.lost_hours,
        stale_running_hours=args.stale_running_hours,
        max_timestamp_skew_ms=args.max_timestamp_skew_ms,
        backup_root=backup_dir(root, args.backup_dir),
        report_root=report_dir(root, args.report_dir),
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("TASK_REGISTRY_REPAIR_OK")
        print(f"report: {payload['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
