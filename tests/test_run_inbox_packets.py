import importlib.util
import re
import sys
import tempfile
import unittest
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
        command: str = "scripts/diagnose_gateway.sh",
        include_result_placeholder: bool = False,
    ) -> str:
        lines = [
            "TASK_PACKET v1",
            "Owner: PIXEL",
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
                    with mock.patch.object(self.runner, "miniapp_emit", return_value=False), mock.patch.object(
                        self.runner.subprocess,
                        "run",
                    ) as run_mock:
                        rc = self.runner.run(root, max_packets=10)
                    self.assertEqual(rc, 0)
                    self.assertEqual(run_mock.call_count, 0)
                    self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_skips_packet_without_read_only_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(include_read_only=False))
            with mock.patch.object(self.runner, "miniapp_emit", return_value=False), mock.patch.object(
                self.runner.subprocess,
                "run",
            ) as run_mock:
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 0)
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_skips_packet_with_non_allowlisted_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet(command="scripts/not_allowlisted.sh"))
            with mock.patch.object(self.runner, "miniapp_emit", return_value=False), mock.patch.object(
                self.runner.subprocess,
                "run",
            ) as run_mock:
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 0)
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_processes_valid_packet_and_writes_non_empty_result_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = self._write_inbox(root, "PIXEL", self._packet())
            proc = SimpleNamespace(
                returncode=0,
                stdout="Gateway target: localhost\n",
                stderr="",
            )
            with mock.patch.object(self.runner, "miniapp_emit", return_value=False), mock.patch.object(
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

            match = re.search(r"  - (tmp/inbox_runner/PIXEL/[^\n]+\.log)", text)
            self.assertIsNotNone(match)
            artifact = root / str(match.group(1))
            self.assertTrue(artifact.exists())
            self.assertGreater(len(artifact.read_text(encoding="utf-8").strip()), 0)

    def test_replaces_existing_empty_result_placeholder_without_duplication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet = self._packet(include_result_placeholder=True)
            inbox = self._write_inbox(root, "PIXEL", packet)
            proc = SimpleNamespace(returncode=0, stdout="Session store: sqlite\n", stderr="")
            with mock.patch.object(self.runner, "miniapp_emit", return_value=False), mock.patch.object(
                self.runner.subprocess,
                "run",
                return_value=proc,
            ):
                rc = self.runner.run(root, max_packets=10)

            self.assertEqual(rc, 0)
            text = inbox.read_text(encoding="utf-8")
            self.assertEqual(text.count("Result:"), 1)
            self.assertIn("Status: OK", text)


if __name__ == "__main__":
    unittest.main()
