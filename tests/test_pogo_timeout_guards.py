from pathlib import Path
import unittest


class TestPogoTimeoutGuards(unittest.TestCase):
    def test_pogo_inputs_uses_bounded_curl_timeouts(self):
        repo = Path(__file__).resolve().parents[1]
        content = (repo / "scripts" / "pogo_brief_inputs.sh").read_text(encoding="utf-8")
        self.assertIn("POGO_HTTP_CONNECT_TIMEOUT_SECONDS", content)
        self.assertIn("POGO_HTTP_MAX_TIME_SECONDS", content)
        self.assertIn("--connect-timeout", content)
        self.assertIn("--max-time", content)

    def test_calendar_fetch_has_osascript_watchdog_timeout(self):
        repo = Path(__file__).resolve().parents[1]
        content = (repo / "scripts" / "calendar_events_fetch.sh").read_text(encoding="utf-8")
        self.assertIn("CAL_OSASCRIPT_TIMEOUT_SECONDS", content)
        self.assertIn("watchdog_pid", content)
        self.assertIn("Calendar access timed out.", content)


if __name__ == "__main__":
    unittest.main()
