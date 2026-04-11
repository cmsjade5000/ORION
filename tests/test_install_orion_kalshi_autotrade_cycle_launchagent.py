import unittest
from pathlib import Path


class TestInstallOrionKalshiAutotradeCycleLaunchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.script = (
            repo / "scripts" / "install_orion_kalshi_autotrade_cycle_launchagent.sh"
        ).read_text(encoding="utf-8")
        cls.runner = (repo / "scripts" / "kalshi_autotrade_cycle_run.sh").read_text(encoding="utf-8")
        cls.readme = (repo / "scripts" / "README.md").read_text(encoding="utf-8")
        cls.doc = (
            repo / "apps" / "extensions" / "kalshi" / "docs" / "KALSHI_REF_ARB.md"
        ).read_text(encoding="utf-8")

    def test_installer_prefers_current_repo_and_disables_duplicate_cron(self):
        git_idx = self.script.index('repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"')
        fallback_idx = self.script.index('repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"')
        self.assertLess(git_idx, fallback_idx)
        self.assertIn('select(.name == "kalshi-ref-arb-5m")', self.script)
        self.assertIn('openclaw cron disable "${job_id}"', self.script)
        self.assertIn("Disabled duplicate OpenClaw cron job", self.script)

    def test_runner_executes_cycle_and_freshness_check(self):
        self.assertIn("/usr/bin/python3 scripts/kalshi_autotrade_cycle.py", self.runner)
        self.assertIn("scripts/kalshi_cycle_freshness_check.py", self.runner)
        self.assertIn('--max-age-sec 600', self.runner)

    def test_docs_prefer_launchagent_over_approval_gated_cron(self):
        self.assertIn("install_orion_kalshi_autotrade_cycle_launchagent.sh", self.readme)
        self.assertIn("system.run", self.readme)
        self.assertIn("Preferred unattended runner", self.doc)
        self.assertIn("approval prompts", self.doc)


if __name__ == "__main__":
    unittest.main()
