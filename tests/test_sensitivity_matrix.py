import importlib.util
import sys
import unittest
from pathlib import Path


def _load_mod():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "sensitivity_matrix.py"
    spec = importlib.util.spec_from_file_location("sensitivity_matrix", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestSensitivityMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_mod()

    def test_parse_options(self):
        obj = {
            "options": [
                {"name": "A", "scenarios": {"best": 3, "base": 2, "worst": 1}},
                {"name": "B", "scenarios": {"best": 2, "base": 2, "worst": 2}},
            ],
            "unit": "pts",
        }
        opts = self.m.parse_options(obj)  # type: ignore[attr-defined]
        self.assertEqual(len(opts), 2)
        self.assertEqual(opts[0].name, "A")
        self.assertEqual(opts[0].best, 3.0)

    def test_format_table_contains_headers(self):
        obj = {"options": [{"name": "A", "scenarios": {"best": 1, "base": 1, "worst": 1}}]}
        opts = self.m.parse_options(obj)  # type: ignore[attr-defined]
        txt = self.m._fmt_table(opts, "value")  # type: ignore[attr-defined]
        self.assertIn("UNIT:", txt)
        self.assertIn("option", txt)
        self.assertIn("best", txt)
        self.assertIn("worst", txt)

