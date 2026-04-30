from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "process_polaris_packets.py"
    spec = importlib.util.spec_from_file_location("process_polaris_packets", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestProcessPolarisPackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def _init_repo(self, root: Path) -> None:
        (root / "tasks" / "INBOX").mkdir(parents=True)
        (root / "tasks" / "INTAKE").mkdir(parents=True)
        (root / "tasks" / "INTAKE" / "capture.md").write_text(
            "Follow up on delegated ORION work.\nOwner: ATLAS\nState: blocked\n",
            encoding="utf-8",
        )
        (root / "tasks" / "INBOX" / "POLARIS.md").write_text(
            "\n".join(
                [
                    "# POLARIS Inbox",
                    "",
                    "## Packets",
                    "TASK_PACKET v1",
                    "Owner: POLARIS",
                    "Requester: ORION",
                    "Notify: telegram",
                    "Opened: 2026-04-30",
                    "Due: 2026-05-02",
                    "Execution Mode: direct",
                    "Tool Scope: read-only",
                    "Objective: Triage and file Cory's captured admin item into the correct assistant workflow.",
                    "Success Criteria:",
                    "- done",
                    "Constraints:",
                    "- no external side effects",
                    "Inputs:",
                    "- tasks/INTAKE/capture.md",
                    "- Capture text:",
                    "  Follow up on delegated ORION work.",
                    "  Owner: ATLAS",
                    "  State: blocked",
                    "Risks:",
                    "- low",
                    "Stop Gates:",
                    "- external side effects",
                    "Output Format:",
                    "- Result block with classification, proposed next step, and any approval gate.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_processes_read_only_direct_polaris_capture(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            rc = self.mod.run(root, max_packets=1)

            self.assertEqual(rc, 0)
            text = (root / "tasks" / "INBOX" / "POLARIS.md").read_text(encoding="utf-8")
            self.assertIn("Result:\nStatus: OK", text)
            self.assertIn("Classification: follow-up", text)
            self.assertIn("Approval gate:", text)
            self.assertEqual(text.count("Result:\nStatus: OK"), 1)


if __name__ == "__main__":
    unittest.main()
