import importlib.util
import sys
import unittest
from pathlib import Path


def _load_linter():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "scribe_lint.py"
    spec = importlib.util.spec_from_file_location("scribe_lint", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestScribeLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_linter()

    def test_ok_telegram(self):
        txt = "TELEGRAM_MESSAGE:\nHello.\n"
        errs = self.m.lint(txt)  # type: ignore[attr-defined]
        self.assertEqual(errs, [])

    def test_blocks_text_before_header(self):
        txt = "oops\nTELEGRAM_MESSAGE:\nHello.\n"
        errs = self.m.lint(txt)  # type: ignore[attr-defined]
        self.assertTrue(errs)

    def test_email_requires_body(self):
        txt = "EMAIL_SUBJECT:\nSubject only\n"
        errs = self.m.lint(txt)  # type: ignore[attr-defined]
        self.assertTrue(any("EMAIL_BODY" in e.message for e in errs), errs)

    def test_newsish_requires_url_and_tag(self):
        txt = "SLACK_MESSAGE:\nLatest update: thing changed.\n"
        errs = self.m.lint(txt)  # type: ignore[attr-defined]
        self.assertTrue(any("URL" in e.message for e in errs), errs)
        self.assertTrue(any("evidence tags" in e.message for e in errs), errs)

    def test_newsish_ok_with_url_and_tag(self):
        txt = "SLACK_MESSAGE:\nLatest update (supported): see https://example.com\n"
        errs = self.m.lint(txt)  # type: ignore[attr-defined]
        self.assertEqual(errs, [])

