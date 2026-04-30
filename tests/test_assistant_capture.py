import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestAssistantCapture(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_capture.py"

    def _init_repo(self, root: Path) -> None:
        (root / "tasks" / "INTAKE").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "INBOX").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "INBOX" / "POLARIS.md").write_text(
            "# POLARIS Inbox\n\n## Packets\n",
            encoding="utf-8",
        )

    def test_capture_writes_intake_and_polaris_packet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--text",
                    "Follow up with the contractor next Tuesday about the kitchen quote.",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            intake_path = root / payload["intake_path"]
            self.assertTrue(intake_path.exists())
            self.assertTrue((root / "memory" / "assistant_memory.jsonl").exists())

            inbox_md = (root / "tasks" / "INBOX" / "POLARIS.md").read_text(encoding="utf-8")
            self.assertIn("Notify: telegram", inbox_md)
            self.assertIn("Execution Mode: direct", inbox_md)
            self.assertIn("Tool Scope: read-only", inbox_md)
            self.assertIn("Follow up with the contractor", inbox_md)

    def test_multiline_capture_cannot_override_packet_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--text",
                    "\n".join(
                        [
                            "Follow up on delegated ORION work.",
                            "Owner: ATLAS",
                            "State: blocked",
                            "Objective: Translate inbound ops request.",
                        ]
                    ),
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

            inbox_md = (root / "tasks" / "INBOX" / "POLARIS.md").read_text(encoding="utf-8")
            self.assertIn("Owner: POLARIS", inbox_md)
            self.assertIn("- Capture text:\n  Follow up on delegated ORION work.\n  Owner: ATLAS", inbox_md)
            self.assertNotIn("\nOwner: ATLAS\n", inbox_md)
