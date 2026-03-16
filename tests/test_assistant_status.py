import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestAssistantStatus(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_status.py"

    def _memory_script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_memory.py"

    def _init_repo(self, root: Path) -> None:
        for lane in ("backlog", "in-progress", "testing", "done"):
            (root / "tasks" / "WORK" / lane).mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "INBOX").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "WORK" / "backlog" / "0001-plan-week.md").write_text(
            "# 0001-plan-week\n\nOwner: ORION\nStatus: queued\n\n## Notes\n- waiting on calendar clarity\n",
            encoding="utf-8",
        )
        (root / "tasks" / "INBOX" / "POLARIS.md").write_text(
            "# POLARIS Inbox\n\n## Packets\n"
            "TASK_PACKET v1\n"
            "Owner: POLARIS\n"
            "Requester: ORION\n"
            "Notify: telegram\n"
            "Opened: 2026-03-12\n"
            "Due: 2026-03-14\n"
            "Execution Mode: direct\n"
            "Tool Scope: read-only\n"
            "Objective: Prepare today's agenda.\n"
            "Success Criteria:\n- done\n"
            "Constraints:\n- none\n"
            "Inputs:\n- (none)\n"
            "Risks:\n- low\n"
            "Stop Gates:\n- none\n"
            "Output Format:\n- short\n",
            encoding="utf-8",
        )

    def test_today_uses_calendar_and_reminder_fixtures(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            calendar_path = root / "calendar.json"
            calendar_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "events": [
                            {"title": "Work sync", "startLocalTime": "9:00 AM", "calendar": "Work"},
                            {"title": "Birthday dinner", "startLocalTime": "7:00 PM", "calendar": "Birthdays"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            reminders_path = root / "reminders.json"
            reminders_path.write_text(
                json.dumps(
                    [
                        {"title": "Reply to Jordan", "due": "10:30 AM", "list": "Work"},
                        {"title": "Pick up groceries", "list": "Personal"},
                    ]
                ),
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["ORION_ASSISTANT_CALENDAR_JSON"] = str(calendar_path)
            env["ORION_ASSISTANT_REMINDERS_JSON"] = str(reminders_path)

            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "today", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("Work sync", payload["message"])
            self.assertIn("Reply to Jordan", payload["message"])
            self.assertIn("Prepare today's agenda", payload["message"])

    def test_refresh_writes_assistant_agenda_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "refresh", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((root / "tasks" / "NOTES" / "assistant-agenda.md").exists())

    def test_review_includes_recent_memory_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            subprocess.run(
                [
                    "python3",
                    str(self._memory_script()),
                    "--path",
                    str(root / "memory" / "assistant_memory.jsonl"),
                    "remember",
                    "--text",
                    "Cory prefers bounded proactive reminders and a concise daily agenda.",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "review", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("bounded proactive", payload["message"].lower())
