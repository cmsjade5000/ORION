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

    def test_cycle_runs_runner_then_reconcile_then_notify(self):
        root = Path("/tmp/orion-cycle-test")
        calls = []

        def _runner(argv, text, capture_output, check):
            calls.append(argv)
            if argv[1].endswith("run_inbox_packets.py"):
                return SimpleNamespace(returncode=0, stdout="RUNNER_IDLE\n", stderr="")
            if argv[1].endswith("task_execution_loop.py"):
                return SimpleNamespace(returncode=0, stdout="TASK_LOOP_OK stale=0 actions=1 apply=1\n", stderr="")
            if argv[1].endswith("notify_inbox_results.py"):
                return SimpleNamespace(returncode=0, stdout="NOTIFY_OK\n", stderr="")
            raise AssertionError(f"Unexpected argv: {argv}")

        stdout = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stdout(stdout):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8)

        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[0][1].endswith("run_inbox_packets.py"))
        self.assertTrue(calls[1][1].endswith("task_execution_loop.py"))
        self.assertTrue(calls[2][1].endswith("notify_inbox_results.py"))
        out = stdout.getvalue()
        self.assertIn("RUNNER_IDLE", out)
        self.assertIn("TASK_LOOP_OK", out)
        self.assertIn("NOTIFY_OK", out)

    def test_cycle_stops_on_first_nonzero_step(self):
        root = Path("/tmp/orion-cycle-test")
        calls = []

        def _runner(argv, text, capture_output, check):
            calls.append(argv)
            if argv[1].endswith("run_inbox_packets.py"):
                return SimpleNamespace(returncode=2, stdout="", stderr="runner failed\n")
            raise AssertionError(f"Unexpected argv after failure: {argv}")

        stderr = io.StringIO()
        with mock.patch.object(self.mod.subprocess, "run", side_effect=_runner):
            with contextlib.redirect_stderr(stderr):
                rc = self.mod.run(root, runner_max_packets=4, stale_hours=24.0, notify_max_per_run=8)

        self.assertEqual(rc, 2)
        self.assertEqual(len(calls), 1)
        self.assertIn("runner failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
