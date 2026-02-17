import unittest
from pathlib import Path


class TestNoPytestDependency(unittest.TestCase):
    def test_no_pytest_imports_in_tests(self):
        repo_root = Path(__file__).resolve().parents[1]
        tests_dir = repo_root / "tests"
        offenders = []
        for p in sorted(tests_dir.glob("test_*.py")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            for ln in txt.splitlines():
                s = ln.strip()
                if s.startswith("import pytest") or s.startswith("from pytest"):
                    offenders.append(str(p))
                    break
        self.assertEqual(offenders, [], f"pytest imports found in: {offenders}")
