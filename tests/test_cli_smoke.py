import datetime as dt
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestCLISmoke(unittest.TestCase):
    def test_evidence_check_cli_ok_and_fail(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "evidence_check.py"
        now = dt.datetime.now(dt.timezone.utc)
        published = (now - dt.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        ok_payload = {
            "time_window_hours": 24,
            "items": [
                {
                    "title": "T",
                    "source": "S",
                    "url": "https://example.com/x",
                    "published_at": published,
                    "claim": "C",
                    "source_tier": "secondary",
                    "confidence": "medium",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "evidence.json"
            p.write_text(json.dumps(ok_payload), encoding="utf-8")
            r = subprocess.run(
                ["python3", str(script), "--input", str(p)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("OK", r.stdout)

            bad = dict(ok_payload)
            bad["items"] = [dict(ok_payload["items"][0])]
            bad["items"][0].pop("url")
            p.write_text(json.dumps(bad), encoding="utf-8")
            r2 = subprocess.run(
                ["python3", str(script), "--input", str(p)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertNotEqual(r2.returncode, 0)

    def test_scribe_lint_cli_ok_and_fail(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "scribe_lint.py"

        ok = "TELEGRAM_MESSAGE:\nHello.\n"
        r = subprocess.run(
            ["python3", str(script)],
            input=ok,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK", r.stdout)

        bad = "oops\nTELEGRAM_MESSAGE:\nHello.\n"
        r2 = subprocess.run(
            ["python3", str(script)],
            input=bad,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertNotEqual(r2.returncode, 0)

