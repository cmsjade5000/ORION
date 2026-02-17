import importlib.util
import json
import sys
import unittest
from pathlib import Path


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestScribeScaffoldScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        cls.scaffold = _load(repo_root / "scripts" / "scribe_scaffold.py", "scribe_scaffold")
        cls.score = _load(repo_root / "scripts" / "scribe_score.py", "scribe_score")

    def test_scaffold_telegram_has_header(self):
        payload = {"goal": "Test goal", "tone": "calm"}
        out = self.scaffold.scaffold("telegram", payload)  # type: ignore[attr-defined]
        self.assertTrue(out.startswith("TELEGRAM_MESSAGE:"))

    def test_score_returns_struct(self):
        txt = "TELEGRAM_MESSAGE:\nHello.\n"
        sc = self.score.score(txt)  # type: ignore[attr-defined]
        self.assertTrue(hasattr(sc, "total"))
        self.assertGreaterEqual(sc.total, 0)

