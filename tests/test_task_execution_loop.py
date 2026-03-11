import importlib.util
import inspect
import json
import sys
import tempfile
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
        if hasattr(self.loop, "time") and hasattr(self.loop.time, "time"):
            with mock.patch.object(self.loop.time, "time", return_value=now):
                return self._run_loop(root, apply=apply, strict=strict, stale_seconds=stale_seconds)
        with mock.patch("time.time", return_value=now):
            return self._run_loop(root, apply=apply, strict=strict, stale_seconds=stale_seconds)

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


if __name__ == "__main__":
    unittest.main()
