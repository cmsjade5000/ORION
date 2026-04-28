from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "inbox_doctor.py"
    spec = importlib.util.spec_from_file_location("inbox_doctor", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestInboxDoctor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_doctor_healthy_when_core_checks_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with (
                mock.patch.object(self.mod, "_validate_packets", return_value={"ok": True}),
                mock.patch.object(self.mod, "_summary_health", return_value={"ok": True, "counts": {"queued": 0}}),
                mock.patch.object(self.mod, "_dead_letters", return_value={"ok": True, "count": 0}),
                mock.patch.object(self.mod, "_notify_state", return_value={"ok": True, "outcomes": {}}),
                mock.patch.object(self.mod, "_email_reply_queue", return_value={"ok": True, "queued_count": 0, "stuck_count": 0}),
                mock.patch.object(self.mod, "_runtime", return_value={"ok": True, "skipped": True}),
                mock.patch.object(self.mod, "_cron_overlap", return_value={"ok": True, "enabled_legacy": []}),
            ):
                report = self.mod.run_doctor(root, skip_runtime=True)

            self.assertTrue(report["ok"])
            self.assertEqual(report["issues"], [])

    def test_doctor_reports_dead_letters_as_actionable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with (
                mock.patch.object(self.mod, "_validate_packets", return_value={"ok": True}),
                mock.patch.object(self.mod, "_summary_health", return_value={"ok": True, "counts": {"queued": 0}}),
                mock.patch.object(self.mod, "_dead_letters", return_value={"ok": False, "count": 1}),
                mock.patch.object(self.mod, "_notify_state", return_value={"ok": True, "outcomes": {}}),
                mock.patch.object(self.mod, "_email_reply_queue", return_value={"ok": True, "queued_count": 0, "stuck_count": 0}),
                mock.patch.object(self.mod, "_runtime", return_value={"ok": True, "skipped": True}),
                mock.patch.object(self.mod, "_cron_overlap", return_value={"ok": True, "enabled_legacy": []}),
            ):
                report = self.mod.run_doctor(root, skip_runtime=True)

            self.assertFalse(report["ok"])
            self.assertIn("dead_letters", report["issues"])

    def test_doctor_warns_on_stuck_email_reply_queue(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jobs = root / "tasks" / "JOBS"
            jobs.mkdir(parents=True)
            (jobs / "summary.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "ik-email",
                                "state": "queued",
                                "owner": "SCRIBE",
                                "objective": "Create a send-ready draft response from the inbound request context.",
                                "pending_since_ts": 1000.0,
                                "inbox": {"path": "tasks/INBOX/SCRIBE.md", "line": 9},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.mod.time, "time", return_value=1000.0 + (16 * 60)):
                report = self.mod._email_reply_queue(root, threshold_minutes=15)

            self.assertFalse(report["ok"])
            self.assertEqual(report["queued_count"], 1)
            self.assertEqual(report["stuck_count"], 1)


if __name__ == "__main__":
    unittest.main()
