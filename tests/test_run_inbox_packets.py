from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from subprocess import TimeoutExpired
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_runner_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_inbox_packets.py"
    spec = importlib.util.spec_from_file_location("run_inbox_packets", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestRunInboxPackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner_module()

    def _write_inbox(self, root: Path, agent: str, packet_body: str) -> Path:
        inbox_dir = root / "tasks" / "INBOX"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        inbox = inbox_dir / f"{agent}.md"
        inbox.write_text(f"# {agent} Inbox\n\n## Packets\n{packet_body}", encoding="utf-8")
        return inbox

    def _packet(
        self,
        *,
        notify: str | None = "telegram",
        include_read_only: bool = True,
        owner: str = "PIXEL",
        command: str = "scripts/diagnose_gateway.sh",
        include_result_placeholder: bool = False,
    ) -> str:
        lines = [
            "TASK_PACKET v1",
            f"Owner: {owner}",
            "Requester: ORION",
        ]
        if notify is not None:
            lines.append(f"Notify: {notify}")
        lines.extend(
            [
                "Objective: Validate packet runner behavior.",
                "Success Criteria:",
                "- Packet is handled correctly.",
                "Constraints:",
                "- Read-only." if include_read_only else "- No special constraints.",
                "Commands to run:",
                f"- {command}",
                "Output Format:",
                "- Short checklist.",
            ]
        )
        if include_result_placeholder:
            lines.append("Result:")
        return "\n".join(lines) + "\n"

    def test_skips_packet_when_notify_missing_or_unsupported(self):
        cases = [(None, "missing"), ("email", "unsupported")]
        for notify, _label in cases:
            with self.subTest(notify=notify):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    inbox = self._write_inbox(root, "PIXEL", self._packet(notify=notify))
                    with mock.patch.object(self.runner.subprocess, "run") as run_mock:
                        rc = self.runner.run(root, max_packets=10)
                    self.assertEqual(rc, 0)
                    self.assertEqual(run_mock.call_count, 0)
                    self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_skips_specialist_packet_with_telegram_notify(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(owner="PIXEL"))
            with mock.patch.object(self.runner.subprocess, "run") as run_mock:
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 0)
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_skips_packet_without_read_only_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(include_read_only=False))
            with mock.patch.object(self.runner.subprocess, "run") as run_mock:
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 0)
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_skips_packet_with_non_allowlisted_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(command="scripts/not_allowlisted.sh"))
            with mock.patch.object(self.runner.subprocess, "run") as run_mock:
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 0)
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_processes_valid_packet_and_writes_non_empty_result_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "ORION", self._packet(owner="ORION"))
            proc = SimpleNamespace(
                returncode=0,
                stdout="Gateway target: localhost\n",
                stderr="",
            )
            with mock.patch.object(
                self.runner.subprocess,
                "run",
                return_value=proc,
            ) as run_mock, mock.patch.object(self.runner.time, "strftime", return_value="20260101-120000"):
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 1)

            text = inbox.read_text(encoding="utf-8")
            self.assertIn("Result:\nStatus: OK", text)
            self.assertRegex(text, r"Findings:\n  - .+")

            match = re.search(r"  - (tmp/inbox_runner/ORION/[^\n]+\.log)", text)
            self.assertIsNotNone(match)
            artifact = root / str(match.group(1))
            self.assertTrue(artifact.exists())
            self.assertGreater(len(artifact.read_text(encoding="utf-8").strip()), 0)

    def test_replaces_existing_empty_result_placeholder_without_duplication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet = self._packet(owner="ORION", include_result_placeholder=True)
            inbox = self._write_inbox(root, "PIXEL", packet)
            proc = SimpleNamespace(returncode=0, stdout="Session store: sqlite\n", stderr="")
            with mock.patch.object(self.runner.subprocess, "run", return_value=proc):
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            text = inbox.read_text(encoding="utf-8")
            self.assertEqual(text.count("Result:"), 1)
            self.assertIn("Status: OK", text)

    def test_updates_packet_by_identity_after_inbox_shifts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(owner="ORION", include_result_placeholder=True))
            lines = inbox.read_text(encoding="utf-8").splitlines()
            packets_header_idx = next(i for i, line in enumerate(lines) if line.strip() == "## Packets")
            start_idx, end_idx, pkt_lines = self.runner._split_packets(lines[packets_header_idx + 1 :])[0]
            pref = self.runner.PacketRef(
                inbox_path=inbox,
                packet_start_line=(packets_header_idx + 1) + start_idx + 1,
                packet_end_line=(packets_header_idx + 1) + end_idx,
                fields=self.runner._parse_fields(pkt_lines),
                raw_lines=pkt_lines,
            )

            inbox.write_text(
                "# PIXEL Inbox\n\nNote: manual edit before packet.\n\n## Packets\n" + self._packet(owner="ORION", include_result_placeholder=True),
                encoding="utf-8",
            )
            proc = SimpleNamespace(returncode=0, stdout="Gateway target: localhost\n", stderr="")
            with mock.patch.object(self.runner.subprocess, "run", return_value=proc):
                updated = self.runner._process_one_packet(root, pref, state_path=(root / "tmp" / "runner-state.json"))

            self.assertTrue(updated)
            text = inbox.read_text(encoding="utf-8")
            self.assertEqual(text.count("Result:"), 1)
            self.assertIn("Status: OK", text)

    def test_marks_packet_failed_when_allowlisted_command_times_out(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "ORION", self._packet(owner="ORION"))
            timeout_exc = TimeoutExpired(
                cmd=["bash", "-lc", "scripts/diagnose_gateway.sh"],
                timeout=120,
                output="partial stdout",
                stderr="partial stderr",
            )
            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=timeout_exc,
            ) as run_mock, mock.patch.object(self.runner.time, "strftime", return_value="20260101-120000"):
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 1)
            self.assertEqual(run_mock.call_args.kwargs.get("timeout"), 120.0)

            text = inbox.read_text(encoding="utf-8")
            self.assertIn("Result:\nStatus: FAILED", text)

            match = re.search(r"  - (tmp/inbox_runner/ORION/[^\n]+\.log)", text)
            self.assertIsNotNone(match)
            artifact = root / str(match.group(1))
            self.assertTrue(artifact.exists())
            artifact_text = artifact.read_text(encoding="utf-8")
            self.assertIn("command timed out after 120.0s", artifact_text)


if __name__ == "__main__":
    unittest.main()
