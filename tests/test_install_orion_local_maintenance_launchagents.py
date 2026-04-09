import unittest
from pathlib import Path


class TestInstallOrionLocalMaintenanceLaunchAgents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.runner = (repo / "scripts" / "orion_local_maintenance_runner.sh").read_text(encoding="utf-8")
        cls.installer = (
            repo / "scripts" / "install_orion_local_maintenance_launchagents.sh"
        ).read_text(encoding="utf-8")

    def test_runner_covers_enabled_local_jobs(self):
        for needle in (
            "assistant-inbox-notify",
            "assistant-task-loop",
            "assistant-agenda-refresh",
            "kalshi-ref-arb-digest",
            "kalshi-digest-delivery-guard",
            "kalshi-digest-reliability-daily",
            "orion-reliability-daily",
            "orion-route-hygiene-daily",
            "orion-lane-hotspots-daily",
            "orion-stop-gate-daily",
            "orion-monthly-scorecard-daily",
            "orion-error-review",
            "orion-session-maintenance",
            "orion-ops-bundle",
            "orion-judgment-layer",
            "orion-skill-discovery-weekly",
        ):
            self.assertIn(needle, self.runner)

    def test_installer_disables_duplicate_crons(self):
        for needle in (
            'disable_cron_by_name "assistant-inbox-notify"',
            'disable_cron_by_name "assistant-task-loop"',
            'disable_cron_by_name "assistant-agenda-refresh"',
            'disable_cron_by_name "kalshi-ref-arb-digest"',
            'disable_cron_by_name "kalshi-digest-delivery-guard"',
            'disable_cron_by_name "kalshi-digest-reliability-daily"',
            'disable_cron_by_name "orion-reliability-daily"',
            'disable_cron_by_name "orion-route-hygiene-daily"',
            'disable_cron_by_name "orion-lane-hotspots-daily"',
            'disable_cron_by_name "orion-stop-gate-daily"',
            'disable_cron_by_name "orion-monthly-scorecard-daily"',
            'disable_cron_by_name "orion-error-review"',
            'disable_cron_by_name "orion-session-maintenance"',
            'disable_cron_by_name "orion-ops-bundle"',
            'disable_cron_by_name "orion-judgment-layer"',
            'disable_cron_by_name "orion-skill-discovery-weekly"',
        ):
            self.assertIn(needle, self.installer)


if __name__ == "__main__":
    unittest.main()
