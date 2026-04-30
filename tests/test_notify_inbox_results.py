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

    def _write_jobs_summary(self, root: Path, payload: dict) -> None:
        jobs_dir = root / "tasks" / "JOBS"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        (jobs_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

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

    def test_policy_block_mode_blocks_outbound_even_in_dry_run(self):
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

            cfg = root / "config"
            cfg.mkdir(parents=True, exist_ok=True)
            rules = {
                "version": 1,
                "name": "notify_block_test",
                "default_mode": "audit",
                "rules": [
                    {
                        "id": "NB1",
                        "description": "force miss",
                        "severity": "critical",
                        "mode": "block",
                        "validator": "phrase_contract",
                        "applies_to": ["automated_summary"],
                        "trigger_tags_any": ["automated_outbound"],
                        "required_all": ["THIS_PHRASE_WILL_NOT_EXIST"],
                        "remediation": "add phrase"
                    }
                ]
            }
            (cfg / "orion_policy_rules.json").write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")

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
                    "--policy-rules",
                    "config/orion_policy_rules.json",
                    "--policy-mode",
                    "block",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("blocked by policy gate", r.stderr.lower())
            reports = list((root / "eval" / "history").glob("policy-gate-notify-telegram-*.json"))
            self.assertTrue(reports)

    def test_dry_run_strips_internal_artifact_lines_from_result_preview(self):
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
                '- OLCALL>[{"name":"sessions_spawn","arguments":{"agentId":"polaris"}}]ALL>\n'
            )
            self._write_inbox(root, "PIXEL", pkt)

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
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("OLCALL>", r.stdout)

    def test_dry_run_includes_blocked_workflow_alerts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jobs_dir = root / "tasks" / "JOBS"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            (jobs_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workflows": [
                            {
                                "workflow_id": "wf-123",
                                "state": "blocked",
                                "owners": ["ATLAS", "NODE"],
                                "job_count": 2,
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

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
            self.assertIn("Workflow alerts:", r.stdout)
            self.assertIn("state=blocked owners=ATLAS, NODE jobs=2", r.stdout)
            self.assertIn("workflow: wf-123", r.stdout)

    def test_telegram_required_workflow_alerts_do_not_emit_discord_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_jobs_summary(
                root,
                {
                    "version": 1,
                    "jobs": [],
                    "workflows": [
                        {
                            "workflow_id": "wf-telegram-only",
                            "state": "blocked",
                            "owners": ["ATLAS"],
                            "job_count": 1,
                        }
                    ],
                },
            )

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
            self.assertIn("TELEGRAM:", r.stdout)
            self.assertIn("workflow: wf-telegram-only", r.stdout)
            self.assertNotIn("DISCORD:", r.stdout)
            state = json.loads((root / "tmp" / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(any(key.startswith("telegram:workflow:") for key in state))
            self.assertFalse(any(key.startswith("discord:workflow:") for key in state))
            self.assertTrue(any(key.startswith("workflow:telegram:") for key in state))
            self.assertFalse(any(key.startswith("workflow:discord:") for key in state))

    def test_dry_run_prefers_job_summary_artifacts_without_inbox_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_jobs_summary(
                root,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "job_id": "pkt-queued",
                            "workflow_id": "wf-q",
                            "state": "queued",
                            "state_reason": "pending_packet",
                            "owner": "POLARIS",
                            "objective": "Prepare today's agenda.",
                            "notify": "telegram",
                            "notify_channels": ["telegram"],
                            "queued_digest": "digest-queued",
                            "result_digest": None,
                            "result": {"status": "pending", "job_state": "queued", "present": False, "raw_status": None},
                            "inbox": {"path": "tasks/INBOX/POLARIS.md", "line": 4},
                        },
                        {
                            "job_id": "pkt-result",
                            "workflow_id": "wf-r",
                            "state": "pending_verification",
                            "state_reason": "result_ok_waiting_done",
                            "owner": "WIRE",
                            "objective": "Summarize research.",
                            "notify": "telegram",
                            "notify_channels": ["telegram"],
                            "queued_digest": "digest-old",
                            "result_digest": "digest-result",
                            "result": {
                                "status": "ok",
                                "job_state": "pending_verification",
                                "present": True,
                                "raw_status": "OK",
                                "preview_lines": ["Status: OK", "Summary: all set"],
                            },
                            "inbox": {"path": "tasks/INBOX/WIRE.md", "line": 9},
                        },
                    ],
                    "workflows": [],
                },
            )

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
                    "--notify-queued",
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
            self.assertIn("[POLARIS] Prepare today's agenda.", r.stdout)
            self.assertIn("[WIRE] Summarize research.", r.stdout)

    def test_dry_run_sends_only_scribe_telegram_message_body(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_jobs_summary(
                root,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "job_id": "pkt-scribe",
                            "workflow_id": "wf-scribe",
                            "state": "pending_verification",
                            "state_reason": "result_ok_waiting_done",
                            "owner": "SCRIBE",
                            "objective": "Draft a Telegram message for Cory.",
                            "notify": "telegram",
                            "notify_channels": ["telegram"],
                            "queued_digest": "digest-old",
                            "result_digest": "digest-scribe",
                            "result": {
                                "status": "ok",
                                "job_state": "pending_verification",
                                "present": True,
                                "raw_status": "OK",
                                "preview_lines": [
                                    "Status: OK",
                                    "TELEGRAM_MESSAGE:",
                                    "Wrapped up recent ORION platform changes:",
                                    "- Strengthened Task Packet validation.",
                                    "- Verified test suite passes.",
                                ],
                            },
                            "inbox": {"path": "tasks/INBOX/SCRIBE.md", "line": 9},
                        },
                    ],
                    "workflows": [],
                },
            )

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
            self.assertIn("Wrapped up recent ORION platform changes:", r.stdout)
            self.assertIn("- Strengthened Task Packet validation.", r.stdout)
            self.assertNotIn("Inbox update:", r.stdout)
            self.assertNotIn("Results:", r.stdout)
            self.assertNotIn("[SCRIBE] Draft a Telegram message", r.stdout)
            self.assertNotIn("Status: OK", r.stdout)
            self.assertNotIn("TELEGRAM_MESSAGE:", r.stdout)
            self.assertNotIn("file: tasks/INBOX/SCRIBE.md:9", r.stdout)

    def test_dry_run_hides_scribe_wrapper_inside_mixed_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_jobs_summary(
                root,
                {
                    "version": 1,
                    "jobs": [
                        {
                            "job_id": "pkt-wire",
                            "workflow_id": "wf-wire",
                            "state": "pending_verification",
                            "owner": "WIRE",
                            "objective": "Check current status.",
                            "notify": "telegram",
                            "notify_channels": ["telegram"],
                            "result_digest": "digest-wire",
                            "result": {
                                "status": "ok",
                                "present": True,
                                "preview_lines": ["Status: OK", "Summary: working"],
                            },
                            "inbox": {"path": "tasks/INBOX/WIRE.md", "line": 4},
                        },
                        {
                            "job_id": "pkt-scribe",
                            "workflow_id": "wf-scribe",
                            "state": "pending_verification",
                            "owner": "SCRIBE",
                            "objective": "Draft a Telegram message for Cory.",
                            "notify": "telegram",
                            "notify_channels": ["telegram"],
                            "result_digest": "digest-scribe",
                            "result": {
                                "status": "ok",
                                "present": True,
                                "preview_lines": [
                                    "Status: OK",
                                    "TELEGRAM_MESSAGE:",
                                    "Clean body only.",
                                ],
                            },
                            "inbox": {"path": "tasks/INBOX/SCRIBE.md", "line": 9},
                        },
                    ],
                    "workflows": [],
                },
            )

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
            self.assertIn("[WIRE] Check current status.", r.stdout)
            self.assertIn("Clean body only.", r.stdout)
            self.assertNotIn("[SCRIBE] Draft a Telegram message", r.stdout)
            self.assertNotIn("TELEGRAM_MESSAGE:", r.stdout)
            self.assertNotIn("file: tasks/INBOX/SCRIBE.md:9", r.stdout)
