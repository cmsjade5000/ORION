from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "orion_scheduler_overlap_guard.py"
    spec = importlib.util.spec_from_file_location("orion_scheduler_overlap_guard", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOrionSchedulerOverlapGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_detect_overlaps_when_launchagent_and_cron_share_job(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            launch_agents = root / "LaunchAgents"
            launch_agents.mkdir()
            (launch_agents / "com.openclaw.orion.assistant_email_triage.plist").write_text("", encoding="utf-8")
            cron_jobs = root / "jobs.json"
            cron_jobs.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {"name": "assistant-email-triage", "enabled": True},
                            {"name": "assistant-agenda-refresh", "enabled": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            overlaps = self.mod.detect_overlaps(
                launch_agents_dir=launch_agents,
                cron_jobs_path=cron_jobs,
            )

        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0]["job"], "assistant-email-triage")

    def test_ignores_disabled_or_missing_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            launch_agents = root / "LaunchAgents"
            launch_agents.mkdir()
            (launch_agents / "com.openclaw.orion.assistant_email_triage.plist").write_text("", encoding="utf-8")
            cron_jobs = root / "jobs.json"
            cron_jobs.write_text(
                json.dumps({"jobs": [{"name": "assistant-email-triage", "enabled": False}]}),
                encoding="utf-8",
            )

            overlaps = self.mod.detect_overlaps(
                launch_agents_dir=launch_agents,
                cron_jobs_path=cron_jobs,
            )

        self.assertEqual(overlaps, [])


if __name__ == "__main__":
    unittest.main()
