import importlib.util
import sys
import unittest
from pathlib import Path


def _load_runner():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_inbox_packets.py"
    spec = importlib.util.spec_from_file_location("run_inbox_packets", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestRunInboxPacketsRetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _load_runner()

    def test_retry_params_defaults(self):
        m, base, mult, maxb = self.r._retry_params({})  # type: ignore[attr-defined]
        self.assertEqual(m, 1)
        self.assertGreaterEqual(base, 0.0)
        self.assertGreaterEqual(mult, 1.0)
        self.assertGreaterEqual(maxb, base)

    def test_retry_params_parse(self):
        fields = {
            "Retry Max Attempts": "3",
            "Retry Backoff Seconds": "5",
            "Retry Backoff Multiplier": "2",
            "Retry Max Backoff Seconds": "60",
        }
        m, base, mult, maxb = self.r._retry_params(fields)  # type: ignore[attr-defined]
        self.assertEqual(m, 3)
        self.assertEqual(base, 5.0)
        self.assertEqual(mult, 2.0)
        self.assertEqual(maxb, 60.0)

