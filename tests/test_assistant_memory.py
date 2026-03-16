import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestAssistantMemory(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_memory.py"

    def test_remember_and_recall_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            memory_path = Path(td) / "assistant_memory.jsonl"

            remember = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--path",
                    str(memory_path),
                    "remember",
                    "--text",
                    "Cory prefers bounded proactive follow-through and Work, Events, Birthdays calendars.",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(remember.returncode, 0, remember.stdout + remember.stderr)

            recall = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--path",
                    str(memory_path),
                    "recall",
                    "--query",
                    "bounded proactive calendars",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(recall.returncode, 0, recall.stdout + recall.stderr)
            payload = json.loads(recall.stdout)
            self.assertTrue(payload["matches"])
            self.assertIn("bounded proactive", payload["matches"][0]["text"].lower())

