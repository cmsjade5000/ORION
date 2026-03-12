import datetime as dt
import unittest
from zoneinfo import ZoneInfo

import scripts.kalshi_digest_reliability as rel


class TestKalshiDigestReliability(unittest.TestCase):
    def setUp(self) -> None:
        self.tz = ZoneInfo("America/New_York")

    def _run(self, y: int, m: int, d: int, h: int, minute: int = 0, status: str = "ok") -> rel.CronRun:
        at = dt.datetime(y, m, d, h, minute, 5, tzinfo=self.tz)
        return rel.CronRun(run_at=at, status=status, summary="", error="", run_at_ms=int(at.timestamp() * 1000))

    def _email(self, y: int, m: int, d: int, h: int, minute: int, sec: int = 0) -> rel.SentEmail:
        ts = dt.datetime(y, m, d, h, minute, sec, tzinfo=self.tz)
        return rel.SentEmail(ts=ts, subject="ORION Kalshi • 8h • Test", to=("cory.stoner@icloud.com",), message_id="m1")

    def test_morning_guard_missing_email_when_run_ok(self) -> None:
        day = dt.date(2026, 3, 2)
        runs = [self._run(2026, 3, 2, 7, status="ok")]
        emails: list[rel.SentEmail] = []
        status, run, email = rel.evaluate_morning_guard(
            runs,
            emails,
            day=day,
            morning_hour=7,
            grace_minutes=10,
        )
        self.assertEqual(status, "missing_email")
        self.assertIsNotNone(run)
        self.assertIsNone(email)

    def test_morning_guard_ok_when_email_within_window(self) -> None:
        day = dt.date(2026, 3, 2)
        runs = [self._run(2026, 3, 2, 7, status="ok")]
        emails = [self._email(2026, 3, 2, 7, 9, 0)]
        status, run, email = rel.evaluate_morning_guard(
            runs,
            emails,
            day=day,
            morning_hour=7,
            grace_minutes=10,
        )
        self.assertEqual(status, "ok")
        self.assertIsNotNone(run)
        self.assertIsNotNone(email)

    def test_render_daily_report_includes_missing_slot(self) -> None:
        day = dt.date(2026, 3, 1)
        runs = [
            self._run(2026, 3, 1, 7, status="ok"),
            self._run(2026, 3, 1, 15, status="ok"),
        ]
        emails = [
            self._email(2026, 3, 1, 7, 0, 12),
            self._email(2026, 3, 1, 15, 0, 8),
        ]
        report = rel.render_daily_report(
            day=day,
            runs=runs,
            emails=emails,
            slot_hours=[7, 15, 23],
            match_minutes=30,
            tz_name="America/New_York",
        )
        self.assertIn("Slots expected: 3 | delivered: 2 | missing: 1", report)
        self.assertIn("23:00 run=missing email=missing", report)

    def test_render_daily_report_accepts_delayed_slot_minute(self) -> None:
        day = dt.date(2026, 3, 11)
        runs = [
            self._run(2026, 3, 11, 7, minute=6, status="error"),
            self._run(2026, 3, 11, 15, minute=1, status="ok"),
            self._run(2026, 3, 11, 23, minute=1, status="ok"),
        ]
        emails = [
            self._email(2026, 3, 11, 15, 1, 14),
            self._email(2026, 3, 11, 23, 1, 59),
        ]
        report = rel.render_daily_report(
            day=day,
            runs=runs,
            emails=emails,
            slot_hours=[7, 15, 23],
            match_minutes=30,
            tz_name="America/New_York",
        )
        self.assertIn("Slots expected: 3 | delivered: 2 | missing: 1 | run_errors: 1", report)
        self.assertIn("07:00 run=error email=missing", report)
        self.assertIn("15:00 run=ok email=15:01:14", report)
        self.assertIn("23:00 run=ok email=23:01:59", report)

    def test_parse_slot_hours_validation(self) -> None:
        self.assertEqual(rel._parse_slot_hours("7,15,23"), [7, 15, 23])
        with self.assertRaises(ValueError):
            rel._parse_slot_hours("7,99")


if __name__ == "__main__":
    unittest.main()
