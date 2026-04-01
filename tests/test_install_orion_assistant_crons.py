import unittest
from pathlib import Path


class TestInstallOrionAssistantCrons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.script = (repo / "scripts" / "install_orion_assistant_crons.sh").read_text(
            encoding="utf-8"
        )
        cls.follow_through = (repo / "docs" / "FOLLOW_THROUGH.md").read_text(encoding="utf-8")

    def test_installer_uses_no_deliver_for_no_reply_jobs(self):
        self.assertIn('--name "$job_name"', self.script)
        self.assertIn('"orion-ops-bundle"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-agenda-refresh"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-inbox-notify"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-task-loop"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-error-review"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-session-maintenance"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-ops-bundle"', self.script)
        self.assertIn("prune_jobs", self.script)
        self.assertIn("openclaw cron list --all --json", self.script)
        self.assertIn('"inbox-result-notify"', self.script)
        self.assertIn('"inbox-result-notify-discord"', self.script)
        self.assertIn('"task-loop-heartbeat"', self.script)
        self.assertIn('"task-loop-weekly-reconcile"', self.script)
        self.assertIn('"orion-session-maintenance"', self.script)
        self.assertIn("scripts/orion_incident_bundle.py", self.script)
        self.assertIn("openclaw cron edit", self.script)
        self.assertIn("openclaw cron rm --json", self.script)
        self.assertGreaterEqual(self.script.count("--no-deliver"), 2)
        self.assertGreaterEqual(self.script.count("--wake next-heartbeat"), 2)
        self.assertEqual(self.script.count("Then respond exactly NO_REPLY."), 6)
        self.assertEqual(self.script.count("Ignore stdout/stderr unless it fails."), 6)
        self.assertIn("scripts/orion_error_db.py", self.script)
        self.assertIn("scripts/session_maintenance.py", self.script)

    def test_follow_through_examples_use_no_deliver(self):
        self.assertIn('bash scripts/install_orion_assistant_crons.sh', self.follow_through)
        self.assertIn('--name "assistant-inbox-notify"', self.follow_through)
        self.assertIn('--name "task-loop-heartbeat"', self.follow_through)
        self.assertIn('--name "task-loop-weekly-reconcile"', self.follow_through)
        self.assertIn('--name "orion-session-maintenance"', self.follow_through)
        self.assertIn('--name "orion-ops-bundle"', self.follow_through)
        self.assertIn('--name "inbox-result-notify-discord"', self.follow_through)
        self.assertGreaterEqual(self.follow_through.count("--no-deliver"), 6)
        self.assertGreaterEqual(self.follow_through.count("--wake next-heartbeat"), 6)


if __name__ == "__main__":
    unittest.main()
