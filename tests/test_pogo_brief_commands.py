import json
import subprocess
import unittest
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


if __name__ == "__main__":
    unittest.main()
