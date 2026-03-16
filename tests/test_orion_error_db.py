import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestOrionErrorDb(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "orion_error_db.py"

    def _init_repo(self, root: Path) -> None:
        (root / "tasks" / "INBOX").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
        (root / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "INCIDENTS.md").write_text(
            "\n".join(
                [
                    "# Incidents",
                    "",
                    "INCIDENT v1",
                    "Id: INC-20260316-0200-gateway",
                    "Opened: 2026-03-16T02:00:00Z",
                    "Opened By: ORION",
                    "Severity: P1",
                    "Trigger: ORION_GATEWAY_RESTART",
                    "Summary: Gateway restart loop detected.",
                    "Evidence:",
                    "- gateway.err.log showed repeated timeout errors",
                    "Actions:",
                    "- Restarted gateway once",
                    "Follow-up Owner: ATLAS",
                    "Follow-up Tasks:",
                    "- Review repeated restart cause",
                    "Closed: open",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (root / "tasks" / "INBOX" / "POLARIS.md").write_text(
            "\n".join(
                [
                    "# POLARIS Inbox",
                    "",
                    "## Packets",
                    "TASK_PACKET v1",
                    "Owner: POLARIS",
                    "Requester: ORION",
                    "Notify: telegram",
                    "Opened: 2026-03-16",
                    "Due: 2026-03-17",
                    "Execution Mode: direct",
                    "Tool Scope: read-only",
                    "Objective: Prepare today's agenda.",
                    "Success Criteria:",
                    "- done",
                    "Constraints:",
                    "- none",
                    "Inputs:",
                    "- (none)",
                    "Risks:",
                    "- low",
                    "Stop Gates:",
                    "- none",
                    "Output Format:",
                    "- short",
                    "Result:",
                    "- Status: FAILED",
                    "- What changed / what I found: reminder lookup failed",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_record_and_stats_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "db" / "orion-ops.sqlite"
            remember = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db),
                    "record",
                    "--direction",
                    "received",
                    "--source",
                    "gateway",
                    "--subsystem",
                    "gateway",
                    "--severity",
                    "error",
                    "--summary",
                    "Gateway timeout while probing",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(remember.returncode, 0, remember.stdout + remember.stderr)

            stats = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db),
                    "stats",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(stats.returncode, 0, stats.stdout + stats.stderr)
            payload = json.loads(stats.stdout)
            self.assertEqual(payload["events"], 1)
            self.assertTrue(payload["fingerprints"])

    def test_review_ingests_incidents_and_packets_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            db = root / "db" / "orion-ops.sqlite"
            review = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--db",
                    str(db),
                    "review",
                    "--window-hours",
                    "48",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(review.returncode, 0, review.stdout + review.stderr)
            payload = json.loads(review.stdout)
            self.assertGreaterEqual(payload["events_inserted"], 2)
            self.assertTrue((root / "tasks" / "NOTES" / "error-review.md").exists())

            conn = sqlite3.connect(db)
            try:
                events = conn.execute("SELECT COUNT(*) FROM error_events").fetchone()[0]
            finally:
                conn.close()
            self.assertGreaterEqual(events, 2)
