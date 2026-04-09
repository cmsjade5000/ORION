import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestConsolidateSessionMemory(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "consolidate_session_memory.py"

    def test_preview_reports_slugged_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            (memory / "2026-04-06-gateway-update.md").write_text("# Session\n\nhello\n", encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["planned"], 1)
            self.assertEqual(Path(payload["candidates"][0]["target"]).name, "2026-04-06.md")

    def test_apply_merges_into_canonical_and_archives_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source = memory / "2026-04-06-gateway-update.md"
            source.write_text(
                "\n".join(
                    [
                        "# Session: 2026-04-06 14:54:10 UTC",
                        "",
                        "- **Session Key**: agent:main:main",
                        "- **Session ID**: bc14a20c-c1fd-41a7-99fa-46fdd996c4c9",
                        "- **Source**: gateway:agent",
                        "",
                        "## Conversation Summary",
                        "",
                        "user: Read HEARTBEAT.md if it exists (workspace context).",
                        "When reading HEARTBEAT.md, use workspace file /tmp/HEARTBEAT.md",
                        "Current time: Monday, April 6th, 2026",
                        "assistant: <tool_code",
                        'print(default_api.read(path = "/tmp/HEARTBEAT.md"))',
                        "",
                        "Conversation info (untrusted metadata):",
                        "```json",
                        '{\"message_id\":\"1\"}',
                        "```",
                        "",
                        "assistant: ORION update report",
                        "",
                        "OpenClaw gateway is now on 2026.4.5 and the runtime is healthy again.",
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            target = memory / "2026-04-06.md"
            self.assertTrue(target.exists())
            text = target.read_text(encoding="utf-8")
            self.assertIn("# Memory for 2026-04-06", text)
            self.assertIn("## Imported Session Summary: 2026-04-06-gateway-update.md", text)
            self.assertIn("assistant: ORION update report", text)
            self.assertIn("OpenClaw gateway is now on 2026.4.5", text)
            self.assertNotIn("Session ID", text)
            self.assertNotIn("Read HEARTBEAT.md", text)
            self.assertNotIn("Conversation info (untrusted metadata)", text)
            archived = root / "tasks" / "WORK" / "artifacts" / "session-memory-archive" / "2026-04-06" / "2026-04-06-gateway-update.md"
            self.assertTrue(archived.exists())
            self.assertFalse(source.exists())

    def test_apply_is_idempotent_when_target_already_contains_import(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source_name = "2026-04-06-gateway-update.md"
            content = "# Session\n\nhello\n"
            source = memory / source_name
            source.write_text(content, encoding="utf-8")

            first_apply = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(first_apply.returncode, 0, first_apply.stdout + first_apply.stderr)
            duplicate_source = memory / source_name
            duplicate_source.write_text(content, encoding="utf-8")

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["result"]["skipped"], 1)
            target = memory / "2026-04-06.md"
            self.assertEqual(target.read_text(encoding="utf-8").count("Imported Session Summary"), 1)

    def test_apply_drops_heartbeat_only_slugged_note_but_archives_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source = memory / "2026-04-08-heartbeat.md"
            source.write_text(
                "\n".join(
                    [
                        "## Conversation Summary",
                        "",
                        "user: [Tue 2026-04-07 21:11 EDT] Ping",
                        "assistant: HEARTBEAT_OK",
                        "",
                        "user: Ping",
                        "assistant: ORION_OK",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["result"]["archived"], 1)
            self.assertEqual(payload["result"]["merged"], 0)
            target = memory / "2026-04-08.md"
            self.assertFalse(target.exists())
            archived = root / "tasks" / "WORK" / "artifacts" / "session-memory-archive" / "2026-04-08" / source.name
            self.assertTrue(archived.exists())
            self.assertFalse(source.exists())

    def test_apply_strips_transport_and_control_noise_but_keeps_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source = memory / "2026-04-08-memory-ops.md"
            source.write_text(
                "\n".join(
                    [
                        "# Session: 2026-04-08 00:00:00 UTC",
                        "",
                        "## Conversation Summary",
                        "",
                        "{",
                        '  "label": "openclaw-control-ui",',
                        '  "id": "openclaw-control-ui"',
                        "}",
                        "",
                        "user: [Tue 2026-04-07 21:01 EDT] Ping",
                        "assistant: HEARTBEAT_OK",
                        "",
                        "assistant: Okay, let me break down what's happening here.",
                        "First, I need to check the transport lane before answering.",
                        "",
                        "assistant: ORION maintenance recap",
                        "",
                        "Judgment layer verification completed and the gateway lane is healthy.",
                        "",
                        "Sender (untrusted metadata):",
                        "```json",
                        '{"label":"Cory Stoner"}',
                        "```",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (memory / "2026-04-08.md").read_text(encoding="utf-8")
            self.assertIn("assistant: ORION maintenance recap", text)
            self.assertIn("Judgment layer verification completed and the gateway lane is healthy.", text)
            self.assertNotIn("openclaw-control-ui", text)
            self.assertNotIn("Ping", text)
            self.assertNotIn("HEARTBEAT_OK", text)
            self.assertNotIn("let me break down", text.lower())
            self.assertNotIn("Sender (untrusted metadata)", text)

    def test_apply_deduplicates_repeated_import_fragments_within_single_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            source = memory / "2026-04-08-gateway.md"
            source.write_text(
                "\n".join(
                    [
                        "## Conversation Summary",
                        "",
                        "assistant: ORION maintenance recap",
                        "Gateway healthy again.",
                        "",
                        "assistant: ORION maintenance recap",
                        "Gateway healthy again.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = (memory / "2026-04-08.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("assistant: ORION maintenance recap"), 1)
            self.assertEqual(text.count("Gateway healthy again."), 1)

    def test_rewrite_existing_sanitizes_canonical_daily_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            target = memory / "2026-04-06.md"
            target.write_text(
                "\n".join(
                    [
                        "# Memory for 2026-04-06",
                        "",
                        "<!-- openclaw-session-memory-import: 2026-04-06-gateway-update.md sha256=dbe3eda64f1830f7 -->",
                        "## Imported Session Summary: 2026-04-06-gateway-update.md",
                        "",
                        "# Session: 2026-04-06 14:54:10 UTC",
                        "",
                        "- **Session Key**: agent:main:main",
                        "- **Session ID**: bc14a20c-c1fd-41a7-99fa-46fdd996c4c9",
                        "- **Source**: gateway:agent",
                        "",
                        "user: Read HEARTBEAT.md if it exists (workspace context).",
                        "assistant: <tool_code",
                        'print(default_api.read(path = "/tmp/HEARTBEAT.md"))',
                        "",
                        "Sender (untrusted metadata):",
                        "```json",
                        '{"label":"Cory Stoner"}',
                        "```",
                        "",
                        "assistant: Okay, let me break down what's happening here.",
                        "The user is just checking if transport is fine.",
                        "",
                        "assistant: ORION update report",
                        "",
                        "Gateway healthy.",
                        "",
                        "Everything ok Orion?",
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--rewrite-existing", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["rewriteExisting"]["rewritten"], 1)
            rewritten = target.read_text(encoding="utf-8")
            self.assertIn("assistant: ORION update report", rewritten)
            self.assertIn("Gateway healthy.", rewritten)
            self.assertNotIn("Session ID", rewritten)
            self.assertNotIn("Read HEARTBEAT.md", rewritten)
            self.assertNotIn('print(default_api.read', rewritten)
            self.assertNotIn("Sender (untrusted metadata)", rewritten)
            self.assertNotIn("let me break down", rewritten.lower())
            self.assertNotIn("Everything ok Orion?", rewritten)

    def test_rewrite_existing_drops_empty_import_block_safely(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            memory.mkdir(parents=True, exist_ok=True)
            target = memory / "2026-04-08.md"
            target.write_text(
                "\n".join(
                    [
                        "# Memory for 2026-04-08",
                        "",
                        "<!-- openclaw-session-memory-import: 2026-04-08-heartbeat.md sha256=aaaaaaaaaaaaaaaa -->",
                        "## Imported Session Summary: 2026-04-08-heartbeat.md",
                        "",
                        "user: Ping",
                        "assistant: HEARTBEAT_OK",
                        "",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--rewrite-existing", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rewritten = target.read_text(encoding="utf-8")
            self.assertEqual(rewritten.strip(), "# Memory for 2026-04-08")
            self.assertNotIn("Imported Session Summary", rewritten)


if __name__ == "__main__":
    unittest.main()
