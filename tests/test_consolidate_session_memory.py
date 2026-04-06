import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestConsolidateSessionMemory(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "consolidate_session_memory.py"

    def test_preview_reports_slugged_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            (memory / "2026-04-06-gateway-update.md").write_text("# Session\n\nhello\n", encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["planned"], 1)
            self.assertEqual(Path(payload["candidates"][0]["target"]).name, "2026-04-06.md")

    def test_apply_merges_into_canonical_and_archives_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source = memory / "2026-04-06-gateway-update.md"
            source.write_text("# Session\n\nhello\n", encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            target = memory / "2026-04-06.md"
            self.assertTrue(target.exists())
            text = target.read_text(encoding="utf-8")
            self.assertIn("# Memory for 2026-04-06", text)
            self.assertIn("## Imported Session Summary: 2026-04-06-gateway-update.md", text)
            self.assertIn("# Session", text)
            archived = root / "tasks" / "WORK" / "artifacts" / "session-memory-archive" / "2026-04-06" / "2026-04-06-gateway-update.md"
            self.assertTrue(archived.exists())
            self.assertFalse(source.exists())

    def test_apply_is_idempotent_when_target_already_contains_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source_name = "2026-04-06-gateway-update.md"
            content = "# Session\n\nhello\n"
            source = memory / source_name
            source.write_text(content, encoding="utf-8")

            first_apply = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(first_apply.returncode, 0, first_apply.stdout + first_apply.stderr)
            duplicate_source = memory / source_name
            duplicate_source.write_text(content, encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["result"]["skipped"], 1)
            target = memory / "2026-04-06.md"
            self.assertEqual(target.read_text(encoding="utf-8").count("Imported Session Summary"), 1)


if __name__ == "__main__":
    unittest.main()
