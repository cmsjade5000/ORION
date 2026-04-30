from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "archive_completed_inbox_packets.py"
    spec = importlib.util.spec_from_file_location("archive_completed_inbox_packets", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestArchiveCompletedInboxPackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _write_fixture(self, root: Path, *, notified_at: float) -> str:
        inbox = root / "tasks" / "INBOX" / "ATLAS.md"
        jobs = root / "tasks" / "JOBS"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        jobs.mkdir(parents=True, exist_ok=True)
        complete_before_result = [
            "TASK_PACKET v1",
            "Owner: ATLAS",
            "Requester: ORION",
            "Notify: telegram",
            "Objective: Complete archival candidate.",
        ]
        queued_block = [
            "TASK_PACKET v1",
            "Owner: ATLAS",
            "Requester: ORION",
            "Notify: telegram",
            "Objective: Still active.",
        ]
        complete_block = complete_before_result + [
            "Result:",
            "Status: OK",
            "Summary: Done.",
        ]
        inbox.write_text("\n".join(complete_block + [""] + queued_block) + "\n", encoding="utf-8")
        digest = self.mod.sha256_lines(complete_before_result)
        summary = {
            "jobs": [
                {
                    "state": "complete",
                    "owner": "ATLAS",
                    "objective": "Complete archival candidate.",
                    "queued_digest": digest,
                    "inbox": {"path": "tasks/INBOX/ATLAS.md", "line": 1},
                    "result": {"status": "ok"},
                    "notification_delivery": {
                        "result": {
                            "status": "delivered",
                            "channels": {
                                "telegram": {
                                    "status": "delivered",
                                    "attempts": 1,
                                    "last_ts": notified_at,
                                    "last_error": "",
                                }
                            },
                        }
                    },
                }
            ]
        }
        (jobs / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return digest

    def test_dry_run_reports_archive_without_mutating_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_fixture(root, notified_at=1_000.0)
            before = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")

            report = self.mod.archive_completed_packets(
                repo_root=root,
                older_than_hours=48.0,
                apply=False,
                now_ts=1_000.0 + (49 * 3600.0),
            )

            self.assertEqual(report["mode"], "dry-run")
            self.assertEqual(report["archived_count"], 1)
            self.assertEqual((root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8"), before)
            self.assertFalse((root / "tasks" / "INBOX" / "archive").exists())

    def test_apply_archives_only_terminal_completed_packets_older_than_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_fixture(root, notified_at=1_000.0)

            report = self.mod.archive_completed_packets(
                repo_root=root,
                older_than_hours=48.0,
                apply=True,
                now_ts=1_000.0 + (49 * 3600.0),
            )

            self.assertEqual(report["archived_count"], 1)
            active = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertNotIn("Complete archival candidate.", active)
            self.assertIn("Still active.", active)
            archive_text = Path(str(report["archive_path"])).read_text(encoding="utf-8")
            self.assertIn("Complete archival candidate.", archive_text)

    def test_recent_completed_packet_stays_active(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_fixture(root, notified_at=10_000.0)

            report = self.mod.archive_completed_packets(
                repo_root=root,
                older_than_hours=48.0,
                apply=True,
                now_ts=10_000.0 + (47 * 3600.0),
            )

            self.assertEqual(report["archived_count"], 0)
            active = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertIn("Complete archival candidate.", active)


if __name__ == "__main__":
    unittest.main()
