import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_inbox_cycle():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "inbox_cycle.py"
    spec = importlib.util.spec_from_file_location("inbox_cycle", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestInboxCycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_inbox_cycle()

    def test_cycle_runs_runner_reconcile_notify_archive_then_doctor(self):
        root = Path("/tmp/orion-cycle-test")
        calls = []

        def _runner(argv, text, capture_output, check):
            calls.append(argv)
            if argv[1].endswith("run_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout="RUNNER_IDLE\n", stderr="")
            if argv[1].endswith("email_reply_worker.py"):
                return SimpleNamespace(returncode=0, stdout="EMAIL_REPLY_WORKER processed=0\nEMAIL_REPLY_STUCK_ALERTS alerted=0\n", stderr="")
            if argv[1].endswith("task_execution_loop.py"):
                return SimpleNamespace(returncode=0, stdout="TASK_LOOP_OK stale=0 actions=1 apply=1\n", stderr="")
            if argv[1].endswith("notify_inbox_results.py"):
                return SimpleNamespace(returncode=0, stdout="NOTIFY_OK\n", stderr="")
            if argv[1].endswith("archive_completed_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout='{"archived_count": 0, "older_than_hours": 48.0}\n', stderr="")
            if argv[1].endswith("inbox_doctor.py"):
                return SimpleNamespace(returncode=0, stdout='{"ok": true, "issues": []}\n', stderr="")
            raise AssertionError(f"Unexpected argv: {argv}")

        stdout = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stdout(stdout):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8)

        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 6)
        self.assertTrue(calls[0][1].endswith("run_inbox_packets.py"))
        self.assertTrue(calls[1][1].endswith("email_reply_worker.py"))
        self.assertIn("--alert-stuck", calls[1])
        self.assertTrue(calls[2][1].endswith("task_execution_loop.py"))
        self.assertTrue(calls[3][1].endswith("notify_inbox_results.py"))
        self.assertNotIn("--notify-queued", calls[3])
        self.assertTrue(calls[4][1].endswith("archive_completed_inbox_packets.py"))
        self.assertTrue(calls[5][1].endswith("inbox_doctor.py"))
        out = stdout.getvalue()
        self.assertIn("RUNNER_IDLE", out)
        self.assertIn("EMAIL_REPLY_WORKER", out)
        self.assertIn("TASK_LOOP_OK", out)
        self.assertIn("NOTIFY_OK", out)
        self.assertIn("ARCHIVE_COMPLETED archived=0", out)
        self.assertIn("INBOX_DOCTOR OK", out)

    def test_cycle_json_output_is_machine_readable(self):
        root = Path("/tmp/orion-cycle-test")

        def _runner(argv, text, capture_output, check):
            if argv[1].endswith("archive_completed_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout='{"archived_count": 1, "older_than_hours": 48.0}\n', stderr="")
            if argv[1].endswith("inbox_doctor.py"):
                return SimpleNamespace(returncode=0, stdout='{"ok": true, "issues": []}\n', stderr="")
            return SimpleNamespace(returncode=0, stdout="OK\n", stderr="")

        stdout = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stdout(stdout):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8, json_output=True)

        self.assertEqual(rc, 0)
        payload = self.mod.json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["returncode"], 0)
        self.assertEqual([step["name"] for step in payload["steps"]], [
            "runner",
            "email-reply-worker",
            "reconcile",
            "notify",
            "archive",
            "reconcile-after-archive",
            "doctor",
        ])
        self.assertEqual(payload["steps"][4]["parsed"]["archived_count"], 1)

    def test_cycle_stops_on_first_nonzero_step(self):
        root = Path("/tmp/orion-cycle-test")
        calls = []

        def _runner(argv, text, capture_output, check):
            calls.append(argv)
            if argv[1].endswith("run_inbox_packets.py"):
                return SimpleNamespace(returncode=2, stdout="", stderr="runner failed\n")
            if argv[1].endswith("inbox_doctor.py"):
                return SimpleNamespace(returncode=0, stdout='{"ok": true, "issues": []}\n', stderr="")
            raise AssertionError(f"Unexpected argv after failure: {argv}")

        stderr = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stderr(stderr):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8)

        self.assertEqual(rc, 2)
        self.assertEqual(len(calls), 2)
        self.assertIn("runner failed", stderr.getvalue())

    def test_cycle_continues_when_email_reply_worker_fails(self):
        root = Path("/tmp/orion-cycle-test")
        calls = []

        def _runner(argv, text, capture_output, check):
            calls.append(argv)
            if argv[1].endswith("run_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout="RUNNER_IDLE\n", stderr="")
            if argv[1].endswith("email_reply_worker.py"):
                return SimpleNamespace(returncode=1, stdout="EMAIL_REPLY_WORKER processed=0\n", stderr="EMAIL_REPLY_ERROR stale\n")
            if argv[1].endswith("task_execution_loop.py"):
                return SimpleNamespace(returncode=0, stdout="TASK_LOOP_OK stale=0 actions=1 apply=1\n", stderr="")
            if argv[1].endswith("notify_inbox_results.py"):
                return SimpleNamespace(returncode=0, stdout="NOTIFY_OK\n", stderr="")
            if argv[1].endswith("archive_completed_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout='{"archived_count": 0, "older_than_hours": 48.0}\n', stderr="")
            if argv[1].endswith("inbox_doctor.py"):
                return SimpleNamespace(returncode=0, stdout='{"ok": true, "issues": []}\n', stderr="")
            raise AssertionError(f"Unexpected argv: {argv}")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8)

        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 6)
        self.assertIn("EMAIL_REPLY_ERROR stale", stderr.getvalue())
        self.assertTrue(any(argv[1].endswith("task_execution_loop.py") for argv in calls))
        self.assertIn("INBOX_DOCTOR OK", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
