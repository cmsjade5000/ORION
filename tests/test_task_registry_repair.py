import json
import os
import sqlite3
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SCHEMA = """
CREATE TABLE task_runs (
  task_id TEXT PRIMARY KEY,
  runtime TEXT NOT NULL,
  source_id TEXT,
  owner_key TEXT NOT NULL,
  scope_kind TEXT NOT NULL,
  child_session_key TEXT,
  parent_task_id TEXT,
  agent_id TEXT,
  run_id TEXT,
  label TEXT,
  task TEXT NOT NULL,
  status TEXT NOT NULL,
  delivery_status TEXT NOT NULL,
  notify_policy TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  ended_at INTEGER,
  last_event_at INTEGER,
  cleanup_after INTEGER,
  error TEXT,
  progress_summary TEXT,
  terminal_summary TEXT,
  terminal_outcome TEXT,
  parent_flow_id TEXT
);
CREATE TABLE task_delivery_state (
  task_id TEXT PRIMARY KEY,
  requester_origin_json TEXT,
  last_notified_event_at INTEGER
);
"""


class TestTaskRegistryRepair(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "task_registry_repair.py"

    def _init_db(self, root: Path) -> Path:
        db = root / "openclaw-home" / "tasks" / "runs.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db)
        try:
            con.executescript(SCHEMA)
            con.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, source_id, owner_key, scope_kind, child_session_key,
                  parent_task_id, agent_id, run_id, label, task, status, delivery_status,
                  notify_policy, created_at, started_at, ended_at, last_event_at,
                  cleanup_after, error, progress_summary, terminal_summary, terminal_outcome, parent_flow_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "lost-1",
                    "cron",
                    "job-1",
                    "system:cron:job-1",
                    "system",
                    None,
                    None,
                    "main",
                    "cron:job-1:1",
                    "assistant-task-loop",
                    "assistant-task-loop",
                    "lost",
                    "not_applicable",
                    "silent",
                    1_700_000_000_000,
                    1_700_000_000_000,
                    1_700_000_600_000,
                    1_700_000_600_000,
                    1_999_999_999_000,
                    "backing session missing",
                    None,
                    None,
                    None,
                    None,
                ),
            )
            con.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, source_id, owner_key, scope_kind, child_session_key,
                  parent_task_id, agent_id, run_id, label, task, status, delivery_status,
                  notify_policy, created_at, started_at, ended_at, last_event_at,
                  cleanup_after, error, progress_summary, terminal_summary, terminal_outcome, parent_flow_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "run-1",
                    "cli",
                    "run-1",
                    "agent:main:main",
                    "session",
                    "agent:main:main",
                    None,
                    "main",
                    "run-1",
                    None,
                    "Reply with exactly: operator-health-bundle-ok",
                    "running",
                    "not_applicable",
                    "silent",
                    1_700_000_000_000,
                    1_700_000_000_000,
                    None,
                    1_700_000_000_000,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            con.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, source_id, owner_key, scope_kind, child_session_key,
                  parent_task_id, agent_id, run_id, label, task, status, delivery_status,
                  notify_policy, created_at, started_at, ended_at, last_event_at,
                  cleanup_after, error, progress_summary, terminal_summary, terminal_outcome, parent_flow_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "skew-1",
                    "cron",
                    "job-2",
                    "system:cron:job-2",
                    "system",
                    None,
                    None,
                    "main",
                    "cron:job-2:1",
                    "assistant-inbox-notify",
                    "assistant-inbox-notify",
                    "succeeded",
                    "not_applicable",
                    "silent",
                    1_700_000_000_003,
                    1_700_000_000_000,
                    1_700_000_010_000,
                    1_700_000_010_000,
                    1_999_999_999_000,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            con.commit()
        finally:
            con.close()
        return db

    def _write_fake_openclaw(self, root: Path) -> None:
        fake = root / "openclaw"
        log = root / "command-log.txt"
        fake.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{log}"
if [[ "$1 $2 $3" == "tasks maintenance --apply" ]]; then
  cat <<'JSON'
{{"ok":true,"applied":true}}
JSON
  exit 0
fi
echo "unexpected command: $*" >&2
exit 2
""",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def test_preview_reports_old_lost_and_stale_running_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = self._init_db(root)
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db),
                    "--lost-hours",
                    "1",
                    "--stale-running-hours",
                    "1",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["counts"]["lost"], 1)
            self.assertEqual(payload["counts"]["stale_running"], 1)
            self.assertEqual(payload["counts"]["timestamp_skew"], 1)
            self.assertFalse(payload["applied"])

    def test_apply_updates_rows_and_runs_tasks_maintenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = self._init_db(root)
            self._write_fake_openclaw(root)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db),
                    "--lost-hours",
                    "1",
                    "--stale-running-hours",
                    "1",
                    "--apply",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            self.assertTrue((root / "tmp" / "task-registry-backups").exists())
            self.assertTrue((root / "tasks" / "JOBS" / "runtime-repair" / "latest.json").exists())
            self.assertEqual(payload["maintenance"]["exit_code"], 0)
            con = sqlite3.connect(db)
            try:
                lost_cleanup_after = con.execute("SELECT cleanup_after FROM task_runs WHERE task_id = 'lost-1'").fetchone()[0]
                stale_row = con.execute(
                    "SELECT status, ended_at, cleanup_after, error, terminal_outcome FROM task_runs WHERE task_id = 'run-1'"
                ).fetchone()
                skew_row = con.execute(
                    "SELECT created_at, started_at FROM task_runs WHERE task_id = 'skew-1'"
                ).fetchone()
            finally:
                con.close()
            self.assertIsNotNone(lost_cleanup_after)
            self.assertEqual(stale_row[0], "lost")
            self.assertIsNotNone(stale_row[1])
            self.assertIsNotNone(stale_row[2])
            self.assertIn("force-reconciled", stale_row[3])
            self.assertEqual(stale_row[4], "lost")
            self.assertEqual(skew_row[0], skew_row[1])
            command_log = (root / "command-log.txt").read_text(encoding="utf-8")
            self.assertIn("tasks maintenance --apply --json", command_log)


if __name__ == "__main__":
    unittest.main()
