import json
import importlib.util
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path


class TestPogoBriefCommands(unittest.TestCase):
    def test_help_command_outputs_message(self):
        repo = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["python3", "scripts/pogo_brief_commands.py", "--cmd", "help"],
            cwd=str(repo),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)
        msg = payload.get("message", "")
        self.assertIn("/pogo_today", msg)
        self.assertIn("/pogo_status", msg)
        self.assertIn("/pogo_voice", msg)
        self.assertIn("/pogo_text", msg)

    def test_text_command_returns_direct_brief(self):
        repo = Path(__file__).resolve().parents[1]
        mod_path = repo / "scripts" / "pogo_brief_commands.py"
        spec = importlib.util.spec_from_file_location("pogo_brief_commands", mod_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        fake_data = {
            "pokemon": {
                "shinySignals": [{"title": "Shiny Pikachu spotlight"}],
                "todayEvents": [{"title": "Festival of Colors"}],
                "freshness": {"confidence": "high"},
            },
            "commute": {"check": {"note": "No shift found"}},
            "urgency": {"level": "low"},
        }

        with patch.object(module, "load_inputs", return_value=fake_data):
            out = module.cmd_text_send()

        self.assertIn("Pokemon GO Today (shiny-first)", out)
        self.assertIn("Shiny radar: Shiny Pikachu spotlight", out)
        self.assertIn("Today: Festival of Colors", out)

    def test_text_command_uses_cache_when_live_refresh_fails(self):
        repo = Path(__file__).resolve().parents[1]
        mod_path = repo / "scripts" / "pogo_brief_commands.py"
        spec = importlib.util.spec_from_file_location("pogo_brief_commands", mod_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        cached_data = {
            "pokemon": {
                "shinySignals": [{"title": "Cached shiny signal"}],
                "todayEvents": [{"title": "Cached event"}],
                "freshness": {"confidence": "medium"},
            },
            "commute": {"check": {"note": "Cached commute signal"}},
            "urgency": {"level": "medium"},
        }

        with patch.object(module, "load_inputs", side_effect=RuntimeError("timed out after 12s")):
            with patch.object(module, "load_cached_inputs", return_value=cached_data):
                out = module.cmd_text_send()

        self.assertIn("Pokemon GO Today (shiny-first)", out)
        self.assertIn("Shiny radar: Cached shiny signal", out)
        self.assertIn("Today: Cached event", out)
        self.assertIn("Note: using cached briefing data while live refresh is unavailable.", out)


if __name__ == "__main__":
    unittest.main()
