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

    def test_dry_run_finds_complete_but_does_not_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "tasks" / "INBOX" / "ATLAS.md"
            jobs = root / "tasks" / "JOBS"
            inbox.parent.mkdir(parents=True)
            jobs.mkdir(parents=True)
            inbox.write_text(
                "\n".join(
                    [
                        "# ATLAS Inbox",
                        "",
                        "## Packets",
                        "",
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Done work.",
                        "Result:",
                        "Status: OK",
                        "",
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Still active.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (jobs / "summary.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "done",
                                "state": "complete",
                                "result": {"status": "ok"},
                                "result_digest": "digest-done",
                                "notify_channels": [],
                                "inbox": {"path": "tasks/INBOX/ATLAS.md", "line": 5},
                            },
                            {
                                "job_id": "queued",
                                "state": "queued",
                                "result": {"status": "pending"},
                                "inbox": {"path": "tasks/INBOX/ATLAS.md", "line": 12},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            candidates = self.mod.find_candidates(
                root,
                state_path=root / "tmp" / "missing.json",
                min_age_hours=0,
                include_result_ok=False,
                now_ts=9999999999,
            )
            result = self.mod.archive_candidates(root, candidates, apply=False)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(result["archived"], [{"path": "tasks/INBOX/ATLAS.md", "line": 5, "reason": "state_complete"}])
            self.assertIn("Done work.", inbox.read_text(encoding="utf-8"))
            self.assertFalse((root / "tasks" / "INBOX" / "archive").exists())

    def test_apply_archives_result_ok_when_explicitly_included(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "tasks" / "INBOX" / "SCRIBE.md"
            jobs = root / "tasks" / "JOBS"
            state_path = root / "tmp" / "inbox_notify_state.json"
            inbox.parent.mkdir(parents=True)
            jobs.mkdir(parents=True)
            state_path.parent.mkdir(parents=True)
            inbox.write_text(
                "\n".join(
                    [
                        "# SCRIBE Inbox",
                        "",
                        "## Packets",
                        "",
                        "TASK_PACKET v1",
                        "Owner: SCRIBE",
                        "Requester: ORION",
                        "Objective: Completed looking work.",
                        "Result:",
                        "Status: OK",
                        "",
                        "TASK_PACKET v1",
                        "Owner: SCRIBE",
                        "Requester: ORION",
                        "Objective: Keep this one.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            state_path.write_text(json.dumps({"telegram:result:delivered:digest-ok": 100.0}), encoding="utf-8")
            (jobs / "summary.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "ok",
                                "state": "pending_verification",
                                "result": {"status": "ok"},
                                "result_digest": "digest-ok",
                                "notify_channels": ["telegram"],
                                "inbox": {"path": "tasks/INBOX/SCRIBE.md", "line": 5},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            candidates = self.mod.find_candidates(
                root,
                state_path=state_path,
                min_age_hours=1,
                include_result_ok=True,
                now_ts=3700.0,
            )
            result = self.mod.archive_candidates(root, candidates, apply=True)

            self.assertEqual(result["archived"], [{"path": "tasks/INBOX/SCRIBE.md", "line": 5, "reason": "result_ok"}])
            active = inbox.read_text(encoding="utf-8")
            self.assertNotIn("Completed looking work.", active)
            self.assertIn("Keep this one.", active)
            archived_files = list((root / "tasks" / "INBOX" / "archive").glob("*/*.md"))
            self.assertEqual(len(archived_files), 1)
            self.assertIn("Completed looking work.", archived_files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
