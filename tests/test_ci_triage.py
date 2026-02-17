import importlib.util
import sys
import unittest
from pathlib import Path


def _load_ci_triage():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "ci_triage.py"
    spec = importlib.util.spec_from_file_location("ci_triage", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestCITriage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_ci_triage()

    def test_classify_pytest_missing(self):
        tri = self.m.classify_failed_log("ModuleNotFoundError: No module named pytest")  # type: ignore[attr-defined]
        self.assertIn(tri.category, {"test-runner-mismatch", "deps/import"})

    def test_classify_deps_import(self):
        tri = self.m.classify_failed_log("ModuleNotFoundError: No module named foo")  # type: ignore[attr-defined]
        self.assertEqual(tri.category, "deps/import")

    def test_classify_network_timeout(self):
        tri = self.m.classify_failed_log("ETIMEDOUT while fetching")  # type: ignore[attr-defined]
        self.assertEqual(tri.category, "network/timeout")

