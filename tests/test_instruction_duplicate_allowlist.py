import json
import re
import unittest
from pathlib import Path


def _normalize(text: str) -> str:
    folded = text.casefold()
    folded = folded.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", folded).strip()


class TestInstructionDuplicateAllowlist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cfg_path = repo / "src" / "core" / "shared" / "instruction_duplicate_allowlist.json"
        cls.cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cls.repo = repo

        cls.canonical_files: list[str] = cls.cfg["canonical_files"]
        cls.canonical_text: dict[str, str] = {}
        for rel in cls.canonical_files:
            path = repo / rel
            if not path.exists():
                raise AssertionError(f"missing canonical file: {rel}")
            cls.canonical_text[rel] = _normalize(path.read_text(encoding="utf-8"))

    def _files_with_phrase(self, phrase: str) -> list[str]:
        needle = _normalize(phrase)
        return [rel for rel, text in self.canonical_text.items() if needle in text]

    def test_policy_shape(self):
        for key in ("canonical_files", "allowed_duplicates", "blocked_reintroductions"):
            self.assertIn(key, self.cfg)

        ids = set()
        for section in ("allowed_duplicates", "blocked_reintroductions"):
            for rule in self.cfg[section]:
                rid = rule["id"]
                self.assertNotIn(rid, ids, f"duplicate rule id: {rid}")
                ids.add(rid)

    def test_allowed_duplicate_counts(self):
        for rule in self.cfg["allowed_duplicates"]:
            files = self._files_with_phrase(rule["phrase"])
            count = len(files)
            self.assertGreaterEqual(
                count,
                rule["min_files"],
                f'{rule["id"]} below min_files; found in {files}',
            )
            self.assertLessEqual(
                count,
                rule["max_files"],
                f'{rule["id"]} above max_files; found in {files}',
            )

    def test_blocked_reintroductions(self):
        for rule in self.cfg["blocked_reintroductions"]:
            files = self._files_with_phrase(rule["phrase"])
            count = len(files)
            self.assertLessEqual(
                count,
                rule["max_files"],
                f'{rule["id"]} reintroduced in {files}',
            )


if __name__ == "__main__":
    unittest.main()
