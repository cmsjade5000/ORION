import unittest
from pathlib import Path


class TestDiscordSelfcheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = (Path(__file__).resolve().parents[1] / "scripts" / "discord_selfcheck.sh").read_text(encoding="utf-8")

    def test_selfcheck_requires_running_true_and_reports_transport_fields(self):
        self.assertIn('if [[ "${running}" == "true" ]]; then', self.script)
        self.assertIn('bad "discord running=${running}', self.script)
        self.assertIn("lastError=${last_error:-none}", self.script)
        self.assertIn("reconnectAttempts=${reconnect_attempts}", self.script)
        self.assertIn("lastStartAt=${last_start_at:-unknown}", self.script)
        self.assertIn("lastStopAt=${last_stop_at:-unknown}", self.script)


if __name__ == "__main__":
    unittest.main()
