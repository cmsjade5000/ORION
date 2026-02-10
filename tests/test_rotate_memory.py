import subprocess
import tempfile
import unittest
from pathlib import Path


class TestRotateMemory(unittest.TestCase):
    def _repo_script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "rotate_memory.py"

    def test_generates_daily_file_and_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sessions = root / "memory" / "sessions"
            sessions.mkdir(parents=True, exist_ok=True)
            (sessions / "a.md").write_text("hello a", encoding="utf-8")
            (sessions / "b.md").write_text("hello b", encoding="utf-8")

            r = subprocess.run(
                [
                    "python3",
                    str(self._repo_script()),
                    "--repo-root",
                    str(root),
                    "--date",
                    "2026-02-10",
                    "--prune-sessions",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            out = root / "memory" / "2026-02-10.md"
            self.assertTrue(out.exists())
            txt = out.read_text(encoding="utf-8")
            self.assertIn("# Memory for 2026-02-10", txt)
            self.assertIn("### a.md", txt)
            self.assertIn("hello b", txt)

            archived = root / "memory" / "sessions" / "archive" / "2026-02-10"
            self.assertTrue((archived / "a.md").exists())
            self.assertTrue((archived / "b.md").exists())

    def test_refuses_overwrite_without_flag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            (root / "memory" / "2026-02-10.md").write_text("existing", encoding="utf-8")
            r = subprocess.run(
                [
                    "python3",
                    str(self._repo_script()),
                    "--repo-root",
                    str(root),
                    "--date",
                    "2026-02-10",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

