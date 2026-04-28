from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_worker():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "email_reply_worker.py"
    spec = importlib.util.spec_from_file_location("email_reply_worker", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _load_task_loop():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "task_execution_loop.py"
    spec = importlib.util.spec_from_file_location("task_execution_loop", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestEmailReplyWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = _load_worker()

    def _root(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory()

    def _write_inbox(self, root: Path, *, overrides: dict[str, str] | None = None) -> Path:
        inbox = root / "tasks" / "INBOX" / "SCRIBE.md"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        fields = {
            "Owner": "SCRIBE",
            "Requester": "ORION",
            "Objective": "Create a send-ready draft response from the inbound request context.",
            "Notify": "telegram",
            "Idempotency Key": "4022ed2e1626dbabfe1a",
            "Message ID": "<3AB951E4-A854-4DCB-8F02-D91DE5335824@icloud.com>",
            "Timestamp": "2026-04-28T00:43:32.000Z",
            "Sender": "Cory Stoner <cory.stoner@icloud.com>",
            "Sender Domain": "icloud.com",
            "Subject": "Orion, reply",
            "Request Summary": "Subject: Orion, reply. Ask: Hi orion, This is a test.",
            "Link Domains": "(none)",
            "Attachment Types": "(none)",
            "Risks": "\nlow",
        }
        if overrides:
            fields.update(overrides)
        lines = [
            "# SCRIBE Inbox",
            "",
            "## Packets",
            "TASK_PACKET v1",
            f"Owner: {fields['Owner']}",
            f"Requester: {fields['Requester']}",
            f"Objective: {fields['Objective']}",
            f"Notify: {fields['Notify']}",
            f"Idempotency Key: {fields['Idempotency Key']}",
            "Success Criteria:",
            "- Risk preflight is documented (sender, link domains only, attachment types only).",
            "Constraints:",
            "- Do not click email links or open/execute attachments from this packet.",
            "- Do not send external email or perform side effects without explicit Cory approval via ORION.",
            "Inputs:",
            f"- Message ID: {fields['Message ID']}",
            f"- Timestamp: {fields['Timestamp']}",
            f"- Sender: {fields['Sender']}",
            f"- Sender Domain: {fields['Sender Domain']}",
            f"- Subject: {fields['Subject']}",
            f"- Request Summary: {fields['Request Summary']}",
            f"- Link Domains: {fields['Link Domains']}",
            f"- Attachment Types: {fields['Attachment Types']}",
            "Risks:",
        ]
        for risk in str(fields["Risks"]).splitlines():
            if risk.strip():
                lines.append(f"- {risk.strip()}")
        inbox.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return inbox

    def _subprocess_success(self, argv, cwd, text, capture_output, check):
        if argv[:2] == ["openclaw", "agent"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"text": "Hi Cory - test received."}), stderr="")
        if argv[:3] == ["node", "skills/agentmail/cli.js", "list-messages"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "messages": [
                            {
                                "message_id": "<3AB951E4-A854-4DCB-8F02-D91DE5335824@icloud.com>",
                                "from": "Cory Stoner <cory.stoner@icloud.com>",
                                "labels": ["received", "unread"],
                            }
                        ]
                    }
                ),
                stderr="",
            )
        if argv[:3] == ["node", "skills/agentmail/cli.js", "reply-last"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "repliedTo": {"message_id": "<3AB951E4-A854-4DCB-8F02-D91DE5335824@icloud.com>"},
                        "sent": {"message_id": "<sent-1@email.amazonses.com>"},
                    }
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected argv: {argv}")

    def test_low_risk_cory_packet_is_sent_and_completed(self):
        with self._root() as td:
            root = Path(td)
            inbox = self._write_inbox(root)
            with mock.patch.object(self.worker.subprocess, "run", side_effect=self._subprocess_success):
                result = self.worker.process_replies(
                    root,
                    max_packets=1,
                    from_inbox="orion_gatewaybot@agentmail.to",
                    trusted_sender="cory.stoner@icloud.com",
                )

            self.assertEqual(result["processed_count"], 1)
            text = inbox.read_text(encoding="utf-8")
            self.assertIn("Result:\nStatus: OK", text)
            self.assertIn("Sent message id: <sent-1@email.amazonses.com>", text)
            self.assertIn("Replied-to message id: <3AB951E4-A854-4DCB-8F02-D91DE5335824@icloud.com>", text)

    def test_completed_packet_terminalizes_in_job_summary(self):
        loop = _load_task_loop()
        with self._root() as td:
            root = Path(td)
            self._write_inbox(root)
            for sub in ("tasks/WORK/backlog", "tasks/WORK/in-progress", "tasks/WORK/testing", "tasks/WORK/done", "tasks/NOTES"):
                (root / sub).mkdir(parents=True, exist_ok=True)

            with mock.patch.object(self.worker.subprocess, "run", side_effect=self._subprocess_success):
                self.worker.process_replies(
                    root,
                    max_packets=1,
                    from_inbox="orion_gatewaybot@agentmail.to",
                    trusted_sender="cory.stoner@icloud.com",
                )

            snapshot = loop.OpenClawSnapshot(
                gateway_health=loop.CommandSnapshot([], 0, "", "", {}),
                gateway_status=loop.CommandSnapshot([], 0, "", "", {}),
                channels_status=loop.CommandSnapshot([], 0, "", "", {}),
                tasks_list=loop.CommandSnapshot([], 0, "", "", []),
                tasks_audit=loop.CommandSnapshot([], 0, json.dumps({"summary": {"warnings": 0, "errors": 0}, "findings": []}), "", {"summary": {"warnings": 0, "errors": 0}, "findings": []}),
            )
            with mock.patch.object(loop, "_collect_openclaw_snapshot", return_value=snapshot):
                rc = loop.run(root, apply_changes=True, stale_hours=24.0, strict_stale=False, state_path=root / "tmp" / "task_state.json")

            self.assertEqual(rc, 0)
            summary = json.loads((root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
            job = next(item for item in summary["jobs"] if item["objective"] == "Create a send-ready draft response from the inbound request context.")
            self.assertEqual(job["state"], "complete")
            self.assertEqual(job["result"]["status"], "ok")

    def test_negative_gates_do_not_send_or_complete(self):
        cases = [
            {"Sender": "Other <other@example.com>", "Sender Domain": "example.com"},
            {"Link Domains": "example.com"},
            {"Attachment Types": "pdf"},
            {"Risks": "\npayment coercion language detected"},
            {"Message ID": ""},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self._root() as td:
                    root = Path(td)
                    inbox = self._write_inbox(root, overrides=overrides)
                    with mock.patch.object(self.worker.subprocess, "run", side_effect=AssertionError("send should not run")):
                        result = self.worker.process_replies(
                            root,
                            max_packets=1,
                            from_inbox="orion_gatewaybot@agentmail.to",
                            trusted_sender="cory.stoner@icloud.com",
                        )
                    self.assertEqual(result["processed_count"], 0)
                    self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_send_without_message_id_does_not_mark_complete(self):
        with self._root() as td:
            root = Path(td)
            inbox = self._write_inbox(root)

            def _runner(argv, cwd, text, capture_output, check):
                if argv[:2] == ["openclaw", "agent"]:
                    return SimpleNamespace(returncode=0, stdout=json.dumps({"text": "Hello."}), stderr="")
                if argv[:3] == ["node", "skills/agentmail/cli.js", "list-messages"]:
                    return self._subprocess_success(argv, cwd, text, capture_output, check)
                if argv[:3] == ["node", "skills/agentmail/cli.js", "reply-last"]:
                    return SimpleNamespace(returncode=0, stdout=json.dumps({"sent": {}}), stderr="")
                raise AssertionError(argv)

            with mock.patch.object(self.worker.subprocess, "run", side_effect=_runner):
                with self.assertRaisesRegex(RuntimeError, "no sent message_id"):
                    self.worker.process_replies(
                        root,
                        max_packets=1,
                        from_inbox="orion_gatewaybot@agentmail.to",
                        trusted_sender="cory.stoner@icloud.com",
                    )
            self.assertNotIn("Result:\nStatus:", inbox.read_text(encoding="utf-8"))

    def test_stuck_alert_fires_once(self):
        with self._root() as td:
            root = Path(td)
            self._write_inbox(root)
            sent: list[str] = []

            def _send(chat_id, token, text):
                sent.append(text)

            with (
                mock.patch.object(self.worker, "_get_telegram_chat_id", return_value="123"),
                mock.patch.object(self.worker, "_get_telegram_bot_token", return_value="tok"),
                mock.patch.object(self.worker, "_telegram_send_message", side_effect=_send),
            ):
                first = self.worker.alert_stuck(
                    root,
                    trusted_sender="cory.stoner@icloud.com",
                    threshold_minutes=15,
                    now_ts=1777338000.0,
                )
                second = self.worker.alert_stuck(
                    root,
                    trusted_sender="cory.stoner@icloud.com",
                    threshold_minutes=15,
                    now_ts=1777338060.0,
                )

            self.assertEqual(first["alerted_count"], 1)
            self.assertEqual(second["alerted_count"], 0)
            self.assertEqual(len(sent), 1)
            self.assertIn("ORION email reply is stuck queued", sent[0])


if __name__ == "__main__":
    unittest.main()
