import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestNotifyInboxResults(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "notify_inbox_results.py"

    def _write_inbox(self, root: Path, agent: str, body: str) -> None:
        inbox = root / "tasks" / "INBOX"
        inbox.mkdir(parents=True, exist_ok=True)
        p = inbox / f"{agent}.md"
        p.write_text(f"# {agent} Inbox\n\n## Packets\n{body}", encoding="utf-8")

    def test_dry_run_notifies_only_notify_telegram(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            pkt1 = (
                "TASK_PACKET v1\n"
                "Owner: PIXEL\n"
                "Requester: ORION\n"
                "Notify: telegram\n"
                "Objective: Do the thing.\n"
                "Success Criteria:\n"
                "- done\n"
                "Constraints:\n"
                "- none\n"
                "Inputs:\n"
                "- (none)\n"
                "Risks:\n"
                "- low\n"
                "Stop Gates:\n"
                "- none\n"
                "Output Format:\n"
                "- short\n"
                "Result:\n"
                "- Status: OK\n"
                "- Found: it works.\n"
            )

            pkt2 = (
                "TASK_PACKET v1\n"
                "Owner: WIRE\n"
                "Requester: ORION\n"
                "Objective: Another thing.\n"
                "Success Criteria:\n"
                "- done\n"
                "Constraints:\n"
                "- none\n"
                "Inputs:\n"
                "- (none)\n"
                "Risks:\n"
                "- low\n"
                "Stop Gates:\n"
                "- none\n"
                "Output Format:\n"
                "- short\n"
                "Result:\n"
                "- Status: OK\n"
                "- This should not notify when require-notify-telegram is on.\n"
            )

            self._write_inbox(root, "PIXEL", pkt1)
            self._write_inbox(root, "WIRE", pkt2)

            env = dict(os.environ)
            env["NOTIFY_DRY_RUN"] = "1"
            r = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--state-path",
                    "tmp/state.json",
                    "--require-notify-telegram",
                    "--max-per-run",
                    "10",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("[PIXEL] Do the thing.", r.stdout)
            self.assertNotIn("[WIRE] Another thing.", r.stdout)

            # Second run should be idle due to saved state.
            r2 = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--state-path",
                    "tmp/state.json",
                    "--require-notify-telegram",
                    "--max-per-run",
                    "10",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertIn("NOTIFY_IDLE", r2.stdout)

    def test_state_file_is_json_dict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkt = (
                "TASK_PACKET v1\n"
                "Owner: PIXEL\n"
                "Requester: ORION\n"
                "Notify: telegram\n"
                "Objective: Do the thing.\n"
                "Success Criteria:\n"
                "- done\n"
                "Constraints:\n"
                "- none\n"
                "Inputs:\n"
                "- (none)\n"
                "Risks:\n"
                "- low\n"
                "Stop Gates:\n"
                "- none\n"
                "Output Format:\n"
                "- short\n"
                "Result:\n"
                "- Status: OK\n"
            )
            self._write_inbox(root, "PIXEL", pkt)

            env = dict(os.environ)
            env["NOTIFY_DRY_RUN"] = "1"
            state_rel = "tmp/state.json"
            subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--state-path",
                    state_rel,
                    "--require-notify-telegram",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            state_path = root / state_rel
            self.assertTrue(state_path.exists())
            obj = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIsInstance(obj, dict)

