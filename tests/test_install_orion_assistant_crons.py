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
        self.assertIn('--name "assistant-agenda-refresh"', self.script)
        self.assertIn('--name "assistant-inbox-notify"', self.script)
        self.assertIn('--name "assistant-task-loop"', self.script)
        self.assertGreaterEqual(self.script.count("--no-deliver"), 3)
        self.assertEqual(self.script.count("Then respond exactly NO_REPLY."), 3)
        self.assertEqual(self.script.count("Ignore stdout/stderr unless it fails."), 3)

    def test_follow_through_examples_use_no_deliver(self):
        self.assertIn('--name "inbox-result-notify"', self.follow_through)
        self.assertIn('--name "task-loop-heartbeat"', self.follow_through)
        self.assertIn('--name "task-loop-weekly-reconcile"', self.follow_through)
        self.assertIn('--name "inbox-result-notify-discord"', self.follow_through)
        self.assertGreaterEqual(self.follow_through.count("--no-deliver"), 4)


if __name__ == "__main__":
    unittest.main()
