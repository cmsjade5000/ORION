import unittest
from pathlib import Path


class TestInstallOrionLocalJobBundleLaunchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.script = (
            repo / "scripts" / "install_orion_local_job_bundle_launchagent.sh"
        ).read_text(encoding="utf-8")
        cls.readme = (repo / "scripts" / "README.md").read_text(encoding="utf-8")

    def test_installer_prefers_current_repo_and_disables_duplicate_crons(self):
        git_idx = self.script.index('repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"')
        fallback_idx = self.script.index('repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"')
        self.assertLess(git_idx, fallback_idx)
        for needle in (
            "assistant-inbox-notify",
            "assistant-task-loop",
            "kalshi-digest-reliability-daily",
            "orion-skill-discovery-weekly",
        ):
            self.assertIn(needle, self.script)
        self.assertIn('openclaw cron disable "${job_id}"', self.script)
        self.assertIn("Disabled duplicate OpenClaw cron job", self.script)

    def test_readme_documents_bundle_preference(self):
        self.assertIn("install_orion_local_job_bundle_launchagent.sh", self.readme)
        self.assertIn("local job bundle", self.readme.lower())
        self.assertIn("system.run approval prompts", self.readme)


if __name__ == "__main__":
    unittest.main()
