import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_inbox_state():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "inbox_state.py"
    spec = importlib.util.spec_from_file_location("inbox_state", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestInboxState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = _load_inbox_state()

    def test_parse_notify_channels(self):
        p = self.s.parse_notify_channels
        self.assertEqual(p(""), set())
        self.assertEqual(p("none"), set())
        self.assertEqual(p("telegram"), {"telegram"})
        self.assertEqual(p("telegram,discord"), {"telegram", "discord"})
        self.assertEqual(p("telegram discord"), {"telegram", "discord"})
        # Unknown tokens are ignored.
        self.assertEqual(p("telegram,sms"), {"telegram"})

    def test_kv_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            st = {"a": 1.0, "b": 2.5}
            self.s.save_kv_state(p, st)
            got = self.s.load_kv_state(p)
            self.assertEqual(got, st)

    def test_kv_state_tolerates_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            p.write_text("{not json", encoding="utf-8")
            got = self.s.load_kv_state(p)
            self.assertEqual(got, {})

    def test_sha256_lines_stable(self):
        h1 = self.s.sha256_lines(["a", "b"])
        h2 = self.s.sha256_lines(["a", "b"])
        h3 = self.s.sha256_lines(["a", "b", "c"])
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

