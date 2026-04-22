import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importlib.util
import sys


class TestAssistantStatus(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_status.py"

    def _memory_script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "assistant_memory.py"

    @classmethod
    def setUpClass(cls):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "assistant_status.py"
        sys.path.insert(0, str(script_path.parent))
        spec = importlib.util.spec_from_file_location("assistant_status_module", script_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        cls.mod = mod

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

    def test_today_surfaces_specialist_telegram_direct_delivery_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            packets = root / "tasks" / "INBOX"
            packets.mkdir(parents=True, exist_ok=True)
            (packets / "PIXEL.md").write_text(
                "# PIXEL Inbox\n\n## Packets\n"
                "TASK_PACKET v1\n"
                "Owner: PIXEL\n"
                "Requester: ATLAS\n"
                "Notify: telegram\n"
                "Objective: Build sample specialist packet.\n"
                "Success Criteria:\n- done\n"
                "Constraints:\n- none\n"
                "Inputs:\n- (none)\n"
                "Risks:\n- low\n"
                "Stop Gates:\n- none\n"
                "Output Format:\n- short\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "today", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            message = payload["message"]

            self.assertIn("Delegation safety checks:", message)
            self.assertIn("Potential direct specialist Telegram delivery: PIXEL", message)

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

    def test_followups_includes_delegated_workflow_followups(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            jobs_dir = root / "tasks" / "JOBS"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            (jobs_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "workflows": [
                            {
                                "workflow_id": "wf-manual",
                                "state": "manual_required",
                                "owners": ["ATLAS"],
                                "job_count": "seven",
                            },
                            {
                                "workflow_id": "wf-blocked",
                                "state": "blocked",
                                "owners": ["PIXEL", "ATLAS"],
                                "job_count": 3,
                            },
                            {
                                "workflow_id": "wf-complete",
                                "state": "complete",
                                "owners": ["PIXEL"],
                                "job_count": 1,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "followups", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            message = payload["message"]

            self.assertIn("Delegated workflow follow-ups:", message)
            self.assertIn("blocked: workflow wf-blocked (owners=PIXEL, ATLAS, jobs=3)", message)
            self.assertIn("manual_required: workflow wf-manual (owners=ATLAS, jobs=0)", message)
            self.assertNotIn("complete:", message)
            self.assertLess(
                message.find("blocked: workflow wf-blocked"),
                message.find("manual_required: workflow wf-manual"),
            )

    def test_today_reads_pending_work_from_job_summary_without_inbox_packet_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            jobs_dir = root / "tasks" / "JOBS"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            (jobs_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "pkt-123",
                                "workflow_id": "wf-123",
                                "state": "queued",
                                "state_reason": "pending_packet",
                                "owner": "POLARIS",
                                "objective": "Prepare today's agenda from summary.",
                                "notify": "telegram",
                                "notify_channels": ["telegram"],
                                "queued_digest": "digest-123",
                                "result_digest": None,
                                "result": {"status": "pending", "job_state": "queued", "present": False, "raw_status": None},
                                "inbox": {"path": "tasks/INBOX/POLARIS.md", "line": 4},
                            }
                        ],
                        "workflows": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "tasks" / "INBOX" / "POLARIS.md").unlink()

            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--cmd", "today", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("Prepare today's agenda from summary.", payload["message"])

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

    def test_dreaming_status_summarizes_runtime_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            with mock.patch.object(
                self.mod,
                "_run_text_command",
                side_effect=[
                    (True, "memory-core"),
                    (True, "true"),
                ],
            ), mock.patch.object(
                self.mod,
                "run_json_command",
                return_value=[
                    {
                        "status": {"sources": ["memory", "sessions"]},
                        "audit": {
                            "exists": True,
                            "entryCount": 3,
                            "updatedAt": "2026-04-06T15:31:57.432Z",
                            "storePath": "/tmp/short-term-recall.json",
                        },
                    }
                ],
            ):
                message = self.mod._render_dreaming_status(root)

            self.assertIn("Memory slot: memory-core", message)
            self.assertIn("Dreaming config: enabled", message)
            self.assertIn("ORION memory sources: memory, sessions", message)
            self.assertIn("Recall entries: 3", message)

    def test_dreaming_toggle_reports_restart_requirement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            with mock.patch.object(
                self.mod,
                "_dreaming_status_payload",
                return_value={"slot": "memory-core", "enabled": False},
            ), mock.patch.object(
                self.mod,
                "_run_text_command",
                side_effect=[
                    (True, "updated"),
                    (True, "true"),
                ],
            ), mock.patch.object(
                self.mod,
                "run_json_command",
                return_value={"valid": True},
            ):
                message = self.mod._set_dreaming_enabled(root, True)

            self.assertIn("Dreaming config is now enabled.", message)
            self.assertIn("Restart the gateway to apply.", message)
