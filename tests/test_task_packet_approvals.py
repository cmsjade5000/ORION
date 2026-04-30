import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_script():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "task_packet_approvals.py"
    spec = importlib.util.spec_from_file_location("task_packet_approvals", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestTaskPacketApprovals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_script()

    def _root(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "tasks" / "JOBS").mkdir(parents=True)
        (root / "tasks" / "INBOX").mkdir(parents=True)
        (root / "tasks" / "INBOX" / "ATLAS.md").write_text("# ATLAS Inbox\n\n## Packets\n", encoding="utf-8")
        (root / "tasks" / "JOBS" / "summary.json").write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "job_id": "job-1",
                            "workflow_id": "wf-1",
                            "state": "blocked",
                            "owner": "ATLAS",
                            "objective": "Restart a safe test service.",
                            "inbox": {"path": "tasks/INBOX/ATLAS.md", "line": 3},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return td, root

    def test_approve_once_logs_decision_and_queues_followup_packet(self):
        td, root = self._root()
        try:
            payload = self.mod.decide(root, job_id="job-1", decision="approve_once", actor="telegram:1 Cory")
            self.assertTrue(payload["ok"])
            self.assertIn("approved once", payload["message"])
            log_text = (root / "tasks" / "APPROVALS" / "task-packet-approvals.jsonl").read_text(encoding="utf-8")
            self.assertIn('"decision": "approve_once"', log_text)
            inbox_text = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertIn("Approval Gate: CORY_MINIAPP_APPROVED", inbox_text)
            self.assertIn("task-packet-approvals.jsonl", inbox_text)
        finally:
            td.cleanup()

    def test_deny_logs_without_queuing_followup_packet(self):
        td, root = self._root()
        try:
            payload = self.mod.decide(root, job_id="job-1", decision="deny", actor="telegram:1 Cory")
            self.assertTrue(payload["ok"])
            self.assertIn("denied", payload["message"])
            log_text = (root / "tasks" / "APPROVALS" / "task-packet-approvals.jsonl").read_text(encoding="utf-8")
            self.assertIn('"decision": "deny"', log_text)
            inbox_text = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertNotIn("Approval Gate: CORY_MINIAPP_APPROVED", inbox_text)
        finally:
            td.cleanup()

    def test_seed_tests_adds_safe_blocked_packets(self):
        td, root = self._root()
        try:
            payload = self.mod.seed_tests(root)
            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["seeded"]), 4)
            inbox_text = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertIn("miniapp-approval-test-dry-run-20260430", inbox_text)
            self.assertIn("miniapp-approval-test-deny-path-20260430", inbox_text)
            self.assertIn("miniapp-approval-test-visible-approve-20260430b", inbox_text)
            self.assertIn("miniapp-approval-test-visible-deny-20260430b", inbox_text)
            self.assertEqual(inbox_text.count("Status: BLOCKED"), 4)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
