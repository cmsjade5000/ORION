import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest import mock


def _load_loop_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "task_execution_loop.py"
    assert script_path.exists(), f"Missing script: {script_path}"
    spec = importlib.util.spec_from_file_location("task_execution_loop", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestTaskExecutionLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = _load_loop_module()

    def _init_repo(self, root: Path) -> None:
        for lane in ("backlog", "in-progress", "testing", "done"):
            (root / "tasks" / "WORK" / lane).mkdir(parents=True, exist_ok=True)
        (root / "tasks" / "INBOX").mkdir(parents=True, exist_ok=True)
        notes_dir = root / "tasks" / "NOTES"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / "status.md").write_text("# Status\n\n- (empty)\n", encoding="utf-8")
        (notes_dir / "plan.md").write_text("# Plan\n\n- (empty)\n", encoding="utf-8")

    def _write_ticket(self, root: Path, *, lane: str, num: int, slug: str, status: str) -> Path:
        p = root / "tasks" / "WORK" / lane / f"{num:04d}-{slug}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "\n".join(
                [
                    f"# {num:04d}-{slug}",
                    "",
                    "Owner: ORION",
                    f"Status: {status}",
                    "",
                    "## Context",
                    "- (test fixture)",
                    "",
                    "## Notes",
                    "- 2026-03-11: created for test",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return p

    def _write_inbox(self, root: Path, agent: str, packet_body: str) -> Path:
        inbox = root / "tasks" / "INBOX" / f"{agent}.md"
        inbox.write_text(f"# {agent} Inbox\n\n## Packets\n{packet_body}\n", encoding="utf-8")
        return inbox

    def _run_loop(self, root: Path, *, apply: bool, strict: bool, stale_seconds: int) -> int:
        if hasattr(self.loop, "run"):
            run_fn = self.loop.run
            params = inspect.signature(run_fn).parameters
            kwargs: dict[str, object] = {}

            if "repo_root" in params:
                kwargs["repo_root"] = root
            elif "root" in params:
                kwargs["root"] = root
            elif "tasks_dir" in params:
                kwargs["tasks_dir"] = root / "tasks"

            flag_values = {
                "apply": apply,
                "apply_mode": apply,
                "apply_changes": apply,
                "strict": strict,
                "strict_mode": strict,
                "strict_stale": strict,
                "stale_seconds": stale_seconds,
                "stale_after_seconds": stale_seconds,
                "pending_stale_seconds": stale_seconds,
                "max_pending_age_seconds": stale_seconds,
                "threshold_seconds": stale_seconds,
                "stale_hours": stale_seconds / 3600.0,
            }
            for key, value in flag_values.items():
                if key in params:
                    kwargs[key] = value

            if "max_packets" in params:
                kwargs["max_packets"] = 50
            if "state_path" in params:
                kwargs["state_path"] = (root / "tmp" / "task_execution_loop_state.json").resolve()

            result = run_fn(**kwargs)
            if isinstance(result, int):
                return result
            if result is None:
                return 0
            if isinstance(result, tuple) and result and isinstance(result[0], int):
                return result[0]
            raise AssertionError(f"Unexpected run() return type: {type(result)}")

        argv = [
            "task_execution_loop.py",
            "--repo-root",
            str(root),
            "--stale-hours",
            str(stale_seconds / 3600.0),
        ]
        if apply:
            argv.append("--apply")
        if strict:
            argv.append("--strict-stale")

        with mock.patch.object(sys, "argv", argv):
            try:
                result = self.loop.main()
            except SystemExit as exc:
                return int(exc.code or 0)
        return int(result) if isinstance(result, int) else 0

    def _run_with_fixed_time(self, root: Path, *, apply: bool, strict: bool, stale_seconds: int, now: float = 1700000000.0) -> int:
        time_patch = (
            mock.patch.object(self.loop.time, "time", return_value=now)
            if hasattr(self.loop, "time") and hasattr(self.loop.time, "time")
            else mock.patch("time.time", return_value=now)
        )
        with self._mock_openclaw(), time_patch:
            return self._run_loop(root, apply=apply, strict=strict, stale_seconds=stale_seconds)

    def _mock_openclaw(self):
        command_map = {
            ("openclaw", "gateway", "health"): mock.Mock(returncode=0, stdout="Gateway Health\nOK (123ms)\nTelegram: ok\nDiscord: degraded\n", stderr=""),
            (
                "openclaw",
                "gateway",
                "status",
                "--json",
            ): mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "rpc": {"ok": True},
                        "health": {"healthy": True},
                        "service": {"runtime": {"status": "running"}},
                    }
                ),
                stderr="",
            ),
            (
                "openclaw",
                "channels",
                "status",
                "--probe",
                "--json",
            ): mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "channels": {
                            "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                            "discord": {
                                "configured": True,
                                "running": False,
                                "lastError": "stale socket",
                                "probe": {"ok": True},
                            },
                            "slack": {"configured": True, "running": False, "lastError": "disabled"},
                        }
                    }
                ),
                stderr="",
            ),
            ("openclaw", "tasks", "list", "--json"): mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "tasks": [
                            {"label": "assistant-task-loop", "status": "failed", "error": "approval-timeout"},
                            {"label": "ledger-cycle", "status": "running"},
                        ]
                    }
                ),
                stderr="",
            ),
            ("openclaw", "tasks", "audit", "--json"): mock.Mock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "summary": {"warnings": 2, "errors": 1, "byCode": {"inconsistent_timestamps": 2}},
                        "findings": [{"code": "inconsistent_timestamps"}, {"code": "lost"}],
                    }
                ),
                stderr="",
            ),
        }

        def _runner(argv, capture_output, text, check, timeout):
            key = tuple(argv)
            if key not in command_map:
                raise AssertionError(f"Unexpected command: {argv}")
            return command_map[key]

        return mock.patch.object(self.loop.subprocess, "run", side_effect=_runner)

    def test_strict_mode_fails_on_stale_pending_packet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="backlog", num=1, slug="strict-stale", status="queued")
            packet_lines = [
                "TASK_PACKET v1",
                "Owner: PIXEL",
                "Requester: ORION",
                "Objective: Validate stale strict behavior.",
                "Inputs: tasks/WORK/backlog/0001-strict-stale.md",
            ]
            self._write_inbox(root, "PIXEL", "\n".join(packet_lines))
            now = 1700000000.0
            pending_key = "pending:" + self.loop.sha256_lines(packet_lines)
            state_path = root / "tmp" / "task_execution_loop_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({pending_key: now - 7200.0}) + "\n", encoding="utf-8")

            rc = self._run_with_fixed_time(root, apply=False, strict=True, stale_seconds=300, now=now)
            self.assertNotEqual(rc, 0)

    def test_lane_status_reconciliation_rewrites_status_to_match_lane(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            ticket = self._write_ticket(root, lane="testing", num=1, slug="lane-reconcile", status="queued")

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            md = ticket.read_text(encoding="utf-8")
            self.assertIn("Status: testing", md)
            self.assertNotIn("Status: queued", md)

    def test_pending_packet_moves_backlog_ticket_to_in_progress_in_apply_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="backlog", num=1, slug="move-on-pending", status="queued")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Start ticket from backlog.",
                        "Inputs: tasks/WORK/backlog/0001-move-on-pending.md",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            backlog_ticket = root / "tasks" / "WORK" / "backlog" / "0001-move-on-pending.md"
            in_progress_ticket = root / "tasks" / "WORK" / "in-progress" / "0001-move-on-pending.md"
            self.assertFalse(backlog_ticket.exists())
            self.assertTrue(in_progress_ticket.exists())
            self.assertIn("Status: in-progress", in_progress_ticket.read_text(encoding="utf-8"))

    def test_terminal_packet_moves_in_progress_ticket_to_testing_in_apply_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="in-progress", num=2, slug="promote-on-result", status="in-progress")
            self._write_inbox(
                root,
                "WIRE",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: WIRE",
                        "Requester: ORION",
                        "Objective: Finish ticket and report.",
                        "Inputs: tasks/WORK/in-progress/0002-promote-on-result.md",
                        "Result:",
                        "Status: OK",
                        "Summary: completed implementation",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            in_progress_ticket = root / "tasks" / "WORK" / "in-progress" / "0002-promote-on-result.md"
            testing_ticket = root / "tasks" / "WORK" / "testing" / "0002-promote-on-result.md"
            self.assertFalse(in_progress_ticket.exists())
            self.assertTrue(testing_ticket.exists())
            self.assertIn("Status: testing", testing_ticket.read_text(encoding="utf-8"))

    def test_writes_durable_delegated_job_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="backlog", num=1, slug="pending-job", status="queued")
            self._write_ticket(root, lane="testing", num=2, slug="result-job", status="testing")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Start delegated job.",
                        "Notify: telegram",
                        "Inputs: tasks/WORK/backlog/0001-pending-job.md",
                    ]
                ),
            )
            self._write_inbox(
                root,
                "WIRE",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: WIRE",
                        "Requester: ORION",
                        "Objective: Finish delegated job.",
                        "Notify: telegram",
                        "Inputs: tasks/WORK/testing/0002-result-job.md",
                        "Result:",
                        "Status: OK",
                        "Summary: completed",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            jobs_dir = root / "tasks" / "JOBS"
            records = list(jobs_dir.glob("*.json"))
            self.assertGreaterEqual(len(records), 3)  # two jobs + summary

            payloads = []
            for path in records:
                if path.name == "summary.json" or path.name.startswith("wf-"):
                    continue
                payloads.append(json.loads(path.read_text(encoding="utf-8")))

            by_objective = {item["objective"]: item for item in payloads}
            self.assertEqual(by_objective["Start delegated job."]["state"], "in_progress")
            self.assertEqual(by_objective["Start delegated job."]["state_reason"], "ticket_in_progress")
            self.assertEqual(by_objective["Start delegated job."]["notify_channels"], ["telegram"])
            self.assertTrue(by_objective["Start delegated job."]["queued_digest"])
            self.assertEqual(by_objective["Finish delegated job."]["state"], "pending_verification")
            self.assertEqual(by_objective["Finish delegated job."]["state_reason"], "result_ok_waiting_done")
            self.assertEqual(by_objective["Finish delegated job."]["result"]["status"], "ok")
            self.assertTrue(by_objective["Finish delegated job."]["result_digest"])
            self.assertEqual(by_objective["Finish delegated job."]["result"]["preview_lines"][0], "Status: OK")

            summary = json.loads((jobs_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["job_count"], 2)
            self.assertEqual(summary["counts"]["in_progress"], 1)
            self.assertEqual(summary["counts"]["pending_verification"], 1)
            self.assertEqual(summary["result_counts"]["pending"], 1)
            self.assertEqual(summary["result_counts"]["ok"], 1)
            self.assertEqual(summary["workflow_count"], 2)
            summary_job = next(item for item in summary["jobs"] if item["objective"] == "Finish delegated job.")
            self.assertEqual(summary_job["state_reason"], "result_ok_waiting_done")
            self.assertTrue(summary_job["result_digest"])

    def test_terminal_packet_appends_next_packet_exactly_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="in-progress", num=4, slug="handoff", status="in-progress")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Finish first stage.",
                        "Inputs: tasks/WORK/in-progress/0004-handoff.md",
                        "Result:",
                        "Status: OK",
                        "Summary: finished",
                        "Next Packet Owner: NODE",
                        "Next Packet Requester: ATLAS",
                        "Next Packet Objective: Continue second stage.",
                        "Next Packet Success Criteria:",
                        "- Continue work.",
                        "Next Packet Constraints:",
                        "- Read-only.",
                        "Next Packet Inputs:",
                        "- tasks/WORK/testing/0004-handoff.md",
                        "Next Packet Risks:",
                        "- low",
                        "Next Packet Stop Gates:",
                        "- Any destructive command.",
                        "Next Packet Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            node_inbox = root / "tasks" / "INBOX" / "NODE.md"
            self.assertTrue(node_inbox.exists())
            node_text = node_inbox.read_text(encoding="utf-8")
            self.assertIn("Owner: NODE", node_text)
            self.assertIn("Requester: ATLAS", node_text)
            self.assertIn("Objective: Continue second stage.", node_text)
            self.assertIn("Handoff Source: tasks/INBOX/ATLAS.md:4", node_text)
            self.assertIn("Idempotency Key: handoff:", node_text)
            self.assertIn("Parent Packet ID:", node_text)
            self.assertIn("Root Packet ID:", node_text)
            self.assertIn("Workflow ID:", node_text)
            self.assertEqual(node_text.count("TASK_PACKET v1"), 1)

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            node_text_2 = node_inbox.read_text(encoding="utf-8")
            self.assertEqual(node_text_2.count("TASK_PACKET v1"), 1)

    def test_next_packet_trigger_matrix(self):
        cases = [
            ("OK", None, True),
            ("FAILED", "FAILED", True),
            ("BLOCKED", "BLOCKED", True),
            ("FAILED", "ANY", True),
            ("FAILED", None, False),
            ("OK", "FAILED", False),
        ]
        for result_status, trigger, should_fire in cases:
            with self.subTest(result_status=result_status, trigger=trigger, should_fire=should_fire):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._init_repo(root)
                    self._write_ticket(root, lane="in-progress", num=5, slug="trigger", status="in-progress")
                    lines = [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Trigger handoff.",
                        "Inputs: tasks/WORK/in-progress/0005-trigger.md",
                        "Result:",
                        f"Status: {result_status}",
                        "Summary: terminal",
                    ]
                    if trigger:
                        lines.append(f"Next Packet On Result: {trigger}")
                    lines.extend(
                        [
                            "Next Packet Owner: NODE",
                            "Next Packet Requester: ATLAS",
                            "Next Packet Objective: Follow-on work.",
                            "Next Packet Success Criteria:",
                            "- Continue work.",
                            "Next Packet Constraints:",
                            "- Read-only.",
                            "Next Packet Inputs:",
                            "- tasks/WORK/testing/0005-trigger.md",
                            "Next Packet Risks:",
                            "- low",
                            "Next Packet Stop Gates:",
                            "- Any destructive command.",
                            "Next Packet Output Format:",
                            "- Short checklist.",
                        ]
                    )
                    self._write_inbox(root, "ATLAS", "\n".join(lines))

                    rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
                    self.assertEqual(rc, 0)

                    node_inbox = root / "tasks" / "INBOX" / "NODE.md"
                    self.assertEqual(node_inbox.exists(), should_fire)

    def test_next_packet_polaris_follow_on_preserves_required_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="in-progress", num=6, slug="polaris", status="in-progress")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Prepare POLARIS handoff.",
                        "Inputs: tasks/WORK/in-progress/0006-polaris.md",
                        "Result:",
                        "Status: OK",
                        "Summary: ready",
                        "Next Packet Owner: POLARIS",
                        "Next Packet Requester: ORION",
                        "Next Packet Notify: telegram",
                        "Next Packet Opened: 2026-04-09",
                        "Next Packet Due: 2026-04-10",
                        "Next Packet Execution Mode: delegate",
                        "Next Packet Tool Scope: write",
                        "Next Packet Objective: Follow up with admin workflow.",
                        "Next Packet Success Criteria:",
                        "- Continue work.",
                        "Next Packet Constraints:",
                        "- Keep it bounded.",
                        "Next Packet Inputs:",
                        "- tasks/WORK/testing/0006-polaris.md",
                        "Next Packet Risks:",
                        "- low",
                        "Next Packet Stop Gates:",
                        "- Any destructive command.",
                        "Next Packet Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            polaris_inbox = root / "tasks" / "INBOX" / "POLARIS.md"
            text = polaris_inbox.read_text(encoding="utf-8")
            self.assertIn("Owner: POLARIS", text)
            self.assertIn("Requester: ORION", text)
            self.assertIn("Notify: telegram", text)
            self.assertIn("Opened: 2026-04-09", text)
            self.assertIn("Due: 2026-04-10", text)
            self.assertIn("Execution Mode: delegate", text)
            self.assertIn("Tool Scope: write", text)

    def test_next_packet_dedupes_on_generated_idempotency_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="in-progress", num=7, slug="dedupe", status="in-progress")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Generate handoff once.",
                        "Inputs: tasks/WORK/in-progress/0007-dedupe.md",
                        "Result:",
                        "Status: OK",
                        "Summary: done",
                        "Next Packet Owner: NODE",
                        "Next Packet Requester: ATLAS",
                        "Next Packet Objective: Deduped follow-on.",
                        "Next Packet Success Criteria:",
                        "- Continue work.",
                        "Next Packet Constraints:",
                        "- Read-only.",
                        "Next Packet Inputs:",
                        "- tasks/WORK/testing/0007-dedupe.md",
                        "Next Packet Risks:",
                        "- low",
                        "Next Packet Stop Gates:",
                        "- Any destructive command.",
                        "Next Packet Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )

            # First pass generates the handoff.
            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)
            node_inbox = root / "tasks" / "INBOX" / "NODE.md"
            generated = node_inbox.read_text(encoding="utf-8")
            idem_line = next(line for line in generated.splitlines() if line.startswith("Idempotency Key: "))

            # Simulate a target inbox where the dedupe marker exists but the source line does not.
            node_inbox.write_text("# NODE Inbox\n\n## Packets\nTASK_PACKET v1\nOwner: NODE\nRequester: ATLAS\nObjective: Deduped follow-on.\n" + idem_line + "\n", encoding="utf-8")

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)
            self.assertEqual(node_inbox.read_text(encoding="utf-8").count("TASK_PACKET v1"), 1)

    def test_next_packet_append_is_lock_safe_under_contention(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Contended handoff.",
                        "Result:",
                        "Status: OK",
                        "Summary: done",
                        "Next Packet Owner: NODE",
                        "Next Packet Requester: ATLAS",
                        "Next Packet Objective: Only append once.",
                        "Next Packet Success Criteria:",
                        "- Continue work.",
                        "Next Packet Constraints:",
                        "- Read-only.",
                        "Next Packet Inputs:",
                        "- tasks/WORK/testing/0008-lock.md",
                        "Next Packet Risks:",
                        "- low",
                        "Next Packet Stop Gates:",
                        "- Any destructive command.",
                        "Next Packet Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )
            packet = self.loop._load_packets(root)[0]
            barrier = threading.Barrier(2)
            results = []

            def _worker():
                barrier.wait()
                results.append(self.loop._append_next_packet_if_needed(root, packet))

            t1 = threading.Thread(target=_worker)
            t2 = threading.Thread(target=_worker)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            node_inbox = root / "tasks" / "INBOX" / "NODE.md"
            self.assertTrue(node_inbox.exists())
            self.assertEqual(node_inbox.read_text(encoding="utf-8").count("TASK_PACKET v1"), 1)
            self.assertEqual(sum(1 for item in results if item is not None), 1)

    def test_workflow_summary_groups_multi_hop_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="testing", num=9, slug="workflow", status="testing")
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Objective: Root workflow stage.",
                        "Result:",
                        "Status: OK",
                        "Summary: finished",
                        "Next Packet Owner: NODE",
                        "Next Packet Requester: ATLAS",
                        "Next Packet Objective: Continue workflow stage.",
                        "Next Packet Success Criteria:",
                        "- Continue work.",
                        "Next Packet Constraints:",
                        "- Read-only.",
                        "Next Packet Inputs:",
                        "- tasks/WORK/testing/0009-workflow.md",
                        "Next Packet Risks:",
                        "- low",
                        "Next Packet Stop Gates:",
                        "- Any destructive command.",
                        "Next Packet Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            node_text = (root / "tasks" / "INBOX" / "NODE.md").read_text(encoding="utf-8")
            workflow_id = next(line.split(":", 1)[1].strip() for line in node_text.splitlines() if line.startswith("Workflow ID:"))
            jobs_summary = json.loads((root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
            workflow_entry = next(item for item in jobs_summary["workflows"] if item["workflow_id"] == workflow_id)
            self.assertEqual(workflow_entry["job_count"], 2)
            self.assertEqual(workflow_entry["state"], "in_progress")

    def test_stale_pending_packet_appends_recovery_packet_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_inbox(
                root,
                "NODE",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: NODE",
                        "Requester: ATLAS",
                        "Objective: Stale specialist task.",
                        "Constraints:",
                        "- Read-only.",
                        "Inputs:",
                        "- tasks/WORK/in-progress/0010-stale.md",
                        "Risks:",
                        "- low",
                        "Stop Gates:",
                        "- Any destructive command.",
                        "Success Criteria:",
                        "- Continue work.",
                        "Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )
            state_path = root / "tmp" / "task_execution_loop_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            pkt = self.loop._load_packets(root)[0]
            state_path.write_text(json.dumps({pkt.pending_key: 1700000000.0 - 90000.0}) + "\n", encoding="utf-8")

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=24 * 3600, now=1700000000.0)
            self.assertEqual(rc, 0)

            atlas_inbox = root / "tasks" / "INBOX" / "ATLAS.md"
            self.assertTrue(atlas_inbox.exists())
            atlas_text = atlas_inbox.read_text(encoding="utf-8")
            self.assertIn("Idempotency Key: recovery:stale:", atlas_text)
            self.assertIn("Recovery Source: tasks/INBOX/NODE.md:4", atlas_text)

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=24 * 3600, now=1700000000.0)
            self.assertEqual(rc, 0)
            self.assertEqual(atlas_inbox.read_text(encoding="utf-8").count("Idempotency Key: recovery:stale:"), 1)

            jobs_summary = json.loads((root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
            stale_entry = next(item for item in jobs_summary["jobs"] if item["objective"] == "Stale specialist task.")
            self.assertEqual(stale_entry["state"], "blocked")
            self.assertEqual(stale_entry["state_reason"], "stale_pending")

    def test_terminal_source_cancels_pending_recovery_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Idempotency Key: source-work",
                        "Packet ID: pkt-source",
                        "Objective: Complete source workflow.",
                        "Result:",
                        "Status: OK",
                        "Summary: source complete",
                        "",
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Idempotency Key: recovery:stale:pkt-source",
                        "Packet ID: pkt-recovery",
                        "Parent Packet ID: pkt-source",
                        "Root Packet ID: pkt-source",
                        "Workflow ID: pkt-source",
                        "Objective: Recover stale delegated workflow for completed source.",
                        "Success Criteria:",
                        "- Recovery closes cleanly.",
                        "Constraints:",
                        "- Read-only.",
                        "Inputs:",
                        "- Source packet: tasks/INBOX/ATLAS.md:4",
                        "Risks:",
                        "- low",
                        "Stop Gates:",
                        "- Any destructive command.",
                        "Output Format:",
                        "- Short checklist.",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            atlas_text = (root / "tasks" / "INBOX" / "ATLAS.md").read_text(encoding="utf-8")
            self.assertIn("Status: CANCELLED", atlas_text)
            self.assertIn("Reason: superseded_by_terminal_source", atlas_text)
            jobs_summary = json.loads((root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
            recovery = next(item for item in jobs_summary["jobs"] if item["objective"] == "Recover stale delegated workflow for completed source.")
            self.assertEqual(recovery["state"], "cancelled")
            self.assertEqual(recovery["state_reason"], "result_cancelled")

    def test_notify_script_can_send_from_job_artifacts_after_loop_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="testing", num=12, slug="notify-summary", status="testing")
            self._write_inbox(
                root,
                "WIRE",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: WIRE",
                        "Requester: ORION",
                        "Notify: telegram",
                        "Objective: Summarize finished delegated work.",
                        "Inputs: tasks/WORK/testing/0012-notify-summary.md",
                        "Result:",
                        "Status: OK",
                        "Summary: finished",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            (root / "tasks" / "INBOX" / "WIRE.md").unlink()
            notify_script = Path(__file__).resolve().parents[1] / "scripts" / "notify_inbox_results.py"
            env = dict(os.environ)
            env["NOTIFY_DRY_RUN"] = "1"
            proc = subprocess.run(
                [
                    "python3",
                    str(notify_script),
                    "--repo-root",
                    str(root),
                    "--state-path",
                    "tmp/state.json",
                    "--require-notify-telegram",
                    "--max-per-run",
                    "10",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("[WIRE] Summarize finished delegated work.", proc.stdout)

    def test_notes_status_and_plan_are_regenerated_with_non_empty_summaries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            self._write_ticket(root, lane="backlog", num=3, slug="notes-refresh", status="queued")
            self._write_inbox(
                root,
                "QUEST",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: QUEST",
                        "Requester: ORION",
                        "Objective: Kick off notes refresh flow.",
                        "Inputs: tasks/WORK/backlog/0003-notes-refresh.md",
                    ]
                ),
            )

            rc = self._run_with_fixed_time(root, apply=True, strict=False, stale_seconds=86400)
            self.assertEqual(rc, 0)

            status_md = (root / "tasks" / "NOTES" / "status.md").read_text(encoding="utf-8").strip()
            plan_md = (root / "tasks" / "NOTES" / "plan.md").read_text(encoding="utf-8").strip()

            self.assertTrue(status_md)
            self.assertTrue(plan_md)
            self.assertNotEqual(status_md, "# Status\n\n- (empty)")
            self.assertNotEqual(plan_md, "# Plan\n\n- (empty)")
            self.assertNotIn("(empty)", status_md.lower())
            self.assertNotIn("(empty)", plan_md.lower())
            self.assertIn("## OpenClaw Runtime", status_md)
            self.assertIn("## OpenClaw Tasks", status_md)
            self.assertIn("Alert: discord: stale socket", status_md)
            self.assertIn("Canonical cron issues: 1", status_md)

    def test_task_summary_accepts_list_payloads_from_tasks_list(self):
        snapshot = self.loop.OpenClawSnapshot(
            gateway_health=self.loop.CommandSnapshot(["openclaw"], 0, "", "", None),
            gateway_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}), "", {"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}),
            channels_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"channels": {}}), "", {"channels": {}}),
            tasks_list=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "list", "--json"],
                0,
                json.dumps(
                    [
                        {"label": "assistant-task-loop", "status": "running"},
                        {"label": "other-task", "status": "failed"},
                    ]
                ),
                "",
                [
                    {"label": "assistant-task-loop", "status": "running"},
                    {"label": "other-task", "status": "failed"},
                ],
            ),
            tasks_audit=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "audit", "--json"],
                0,
                json.dumps({"summary": {"warnings": 0, "errors": 0}, "findings": []}),
                "",
                {"summary": {"warnings": 0, "errors": 0}, "findings": []},
            ),
        )

        summary = self.loop._task_summary(snapshot)

        self.assertEqual(summary["counts"]["total"], 2)
        self.assertEqual(summary["counts"]["running"], 1)
        self.assertEqual(summary["counts"]["failed"], 1)

    def test_task_summary_counts_orion_ops_bundle_as_canonical(self):
        snapshot = self.loop.OpenClawSnapshot(
            gateway_health=self.loop.CommandSnapshot(["openclaw"], 0, "", "", None),
            gateway_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}), "", {"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}),
            channels_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"channels": {}}), "", {"channels": {}}),
            tasks_list=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "list", "--json"],
                0,
                json.dumps(
                    {
                        "tasks": [
                            {"label": "orion-ops-bundle", "status": "lost", "error": "backing session missing"},
                        ]
                    }
                ),
                "",
                {
                    "tasks": [
                        {"label": "orion-ops-bundle", "status": "lost", "error": "backing session missing"},
                    ]
                },
            ),
            tasks_audit=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "audit", "--json"],
                0,
                json.dumps({"summary": {"warnings": 0, "errors": 1, "byCode": {"lost": 1}}, "findings": [{"code": "lost"}]}),
                "",
                {"summary": {"warnings": 0, "errors": 1, "byCode": {"lost": 1}}, "findings": [{"code": "lost"}]},
            ),
        )

        summary = self.loop._task_summary(snapshot)

        self.assertEqual(summary["counts"]["canonical_issues"], 1)
        self.assertIn("orion-ops-bundle: lost", summary["recent_failures"])

    def test_task_summary_uses_latest_canonical_run_for_issue_count(self):
        snapshot = self.loop.OpenClawSnapshot(
            gateway_health=self.loop.CommandSnapshot(["openclaw"], 0, "", "", None),
            gateway_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}), "", {"rpc": {"ok": True}, "health": {"healthy": True}, "service": {"runtime": {"status": "running"}}}),
            channels_status=self.loop.CommandSnapshot(["openclaw"], 0, json.dumps({"channels": {}}), "", {"channels": {}}),
            tasks_list=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "list", "--json"],
                0,
                json.dumps(
                    {
                        "tasks": [
                            {"label": "assistant-task-loop", "status": "failed", "createdAt": 10, "lastEventAt": 20},
                            {"label": "assistant-task-loop", "status": "succeeded", "createdAt": 30, "lastEventAt": 40},
                        ]
                    }
                ),
                "",
                {
                    "tasks": [
                        {"label": "assistant-task-loop", "status": "failed", "createdAt": 10, "lastEventAt": 20},
                        {"label": "assistant-task-loop", "status": "succeeded", "createdAt": 30, "lastEventAt": 40},
                    ]
                },
            ),
            tasks_audit=self.loop.CommandSnapshot(
                ["openclaw", "tasks", "audit", "--json"],
                0,
                json.dumps({"summary": {"warnings": 0, "errors": 0, "byCode": {}}, "findings": []}),
                "",
                {"summary": {"warnings": 0, "errors": 0, "byCode": {}}, "findings": []},
            ),
        )

        summary = self.loop._task_summary(snapshot)

        self.assertEqual(summary["counts"]["canonical_issues"], 0)
        self.assertIn("assistant-task-loop: failed", summary["recent_failures"])

    def test_run_capture_returns_timeout_snapshot(self):
        with mock.patch.object(
            self.loop.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["openclaw", "tasks", "list", "--json"], timeout=1.5),
        ):
            snapshot = self.loop._run_capture(["openclaw", "tasks", "list", "--json"])

        self.assertEqual(snapshot.returncode, 124)
        self.assertEqual(snapshot.stdout, "")
        self.assertIn("command timed out after", snapshot.stderr)
        self.assertIsNone(snapshot.data)

    def test_run_completes_when_openclaw_snapshot_times_out(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            command_map = {
                ("openclaw", "gateway", "health"): mock.Mock(returncode=0, stdout="Gateway Health\nOK (123ms)\n", stderr=""),
                (
                    "openclaw",
                    "gateway",
                    "status",
                    "--json",
                ): mock.Mock(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "rpc": {"ok": True},
                            "health": {"healthy": True},
                            "service": {"runtime": {"status": "running"}},
                        }
                    ),
                    stderr="",
                ),
                (
                    "openclaw",
                    "channels",
                    "status",
                    "--probe",
                    "--json",
                ): mock.Mock(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "channels": {
                                "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                            }
                        }
                    ),
                    stderr="",
                ),
            }

            def _runner(argv, capture_output, text, check, timeout):
                key = tuple(argv)
                if key in {
                    ("openclaw", "tasks", "list", "--json"),
                    ("openclaw", "tasks", "audit", "--json"),
                }:
                    raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
                if key not in command_map:
                    raise AssertionError(f"Unexpected command: {argv}")
                return command_map[key]

            with mock.patch.object(self.loop.subprocess, "run", side_effect=_runner):
                rc = self._run_loop(root, apply=True, strict=False, stale_seconds=86400)

            self.assertEqual(rc, 0)
            status_md = (root / "tasks" / "NOTES" / "status.md").read_text(encoding="utf-8")
            self.assertIn("## OpenClaw Tasks", status_md)
            self.assertIn("total=0", status_md)

    def test_collect_openclaw_snapshot_runs_in_parallel(self):
        started = []

        def _fake_capture(argv):
            started.append(tuple(argv))
            time.sleep(0.2)
            return self.loop.CommandSnapshot(argv=argv, returncode=0, stdout="", stderr="", data=None)

        with mock.patch.object(self.loop, "_run_capture", side_effect=_fake_capture):
            t0 = time.perf_counter()
            snapshot = self.loop._collect_openclaw_snapshot()
            elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.6)
        self.assertEqual(len(started), 5)
        self.assertEqual(snapshot.gateway_health.argv, ["openclaw", "gateway", "health"])
        self.assertEqual(snapshot.tasks_audit.argv, ["openclaw", "tasks", "audit", "--json"])

    def test_notes_status_parses_json_with_leading_warning_noise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            warning_prefix = "warning: gateway token audit pending\n"
            command_map = {
                ("openclaw", "gateway", "health"): mock.Mock(returncode=0, stdout="Gateway Health\nOK (123ms)\n", stderr=""),
                (
                    "openclaw",
                    "gateway",
                    "status",
                    "--json",
                ): mock.Mock(
                    returncode=0,
                    stdout=warning_prefix + json.dumps(
                        {
                            "rpc": {"ok": True},
                            "health": {"healthy": True},
                            "service": {"runtime": {"status": "running"}},
                        }
                    ),
                    stderr="",
                ),
                (
                    "openclaw",
                    "channels",
                    "status",
                    "--probe",
                    "--json",
                ): mock.Mock(
                    returncode=0,
                    stdout=warning_prefix
                    + json.dumps(
                        {
                            "channels": {
                                "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                                "discord": {"configured": True, "running": False, "lastError": "stale socket", "probe": {"ok": True}},
                            }
                        }
                    ),
                    stderr="",
                ),
                ("openclaw", "tasks", "list", "--json"): mock.Mock(
                    returncode=0,
                    stdout=warning_prefix
                    + json.dumps(
                        {
                            "tasks": [
                                {"label": "assistant-task-loop", "status": "failed", "error": "approval-timeout"},
                                {"label": "assistant-inbox-notify", "status": "running"},
                            ]
                        }
                    ),
                    stderr="",
                ),
                ("openclaw", "tasks", "audit", "--json"): mock.Mock(
                    returncode=0,
                    stdout=warning_prefix
                    + json.dumps(
                        {
                            "summary": {"warnings": 1, "errors": 1, "byCode": {"stale_running": 1}},
                            "findings": [{"code": "stale_running"}],
                        }
                    ),
                    stderr="",
                ),
            }

            def _runner(argv, capture_output, text, check, timeout):
                key = tuple(argv)
                if key not in command_map:
                    raise AssertionError(f"Unexpected command: {argv}")
                return command_map[key]

            with mock.patch.object(self.loop.subprocess, "run", side_effect=_runner):
                rc = self._run_loop(root, apply=False, strict=False, stale_seconds=86400)

            self.assertEqual(rc, 0)
            status_md = (root / "tasks" / "NOTES" / "status.md").read_text(encoding="utf-8")
            self.assertIn("running=1", status_md)
            self.assertIn("failed=1", status_md)
            self.assertIn("warnings=1 errors=1 findings=1", status_md)
            self.assertIn("Stale running: unknown: stuck", status_md)


if __name__ == "__main__":
    unittest.main()
