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

    def test_installer_requires_explicit_opt_in_and_overlap_guard(self):
        self.assertIn('ALLOW_LLM_CRON_WRAPPERS="${ALLOW_LLM_CRON_WRAPPERS:-0}"', self.script)
        self.assertIn('ALLOW_SCHEDULER_OVERLAP="${ALLOW_SCHEDULER_OVERLAP:-0}"', self.script)
        self.assertIn("Refusing to install LLM-backed cron wrappers", self.script)
        self.assertIn("launchagent_overlap_guard", self.script)
        self.assertIn("scripts/orion_scheduler_overlap_guard.py", self.script)
        self.assertIn('--name "$job_name"', self.script)
        self.assertIn('"orion-ops-bundle"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-agenda-refresh"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-email-triage"', self.script)
        self.assertIn('upsert_job "$jobs_json" "assistant-inbox-notify"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-error-review"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-session-maintenance"', self.script)
        self.assertIn('upsert_job "$jobs_json" "orion-ops-bundle"', self.script)
        self.assertIn("openclaw cron edit", self.script)
        self.assertIn("openclaw cron rm --json", self.script)
        self.assertEqual(self.script.count("Then respond exactly NO_REPLY."), 6)
        self.assertEqual(self.script.count("Ignore stdout/stderr unless it fails."), 6)

    def test_follow_through_marks_agentturn_crons_as_compatibility_only(self):
        self.assertIn("Cron (Compatibility Only)", self.follow_through)
        self.assertIn("ALLOW_LLM_CRON_WRAPPERS=1 bash scripts/install_orion_assistant_crons.sh --apply", self.follow_through)
        self.assertIn("prefer:", self.follow_through)
        self.assertIn("bash scripts/install_orion_local_maintenance_launchagents.sh", self.follow_through)
        self.assertIn('--name "assistant-email-triage"', self.follow_through)
        self.assertIn("scripts/email_triage_router.py", self.follow_through)


if __name__ == "__main__":
    unittest.main()
