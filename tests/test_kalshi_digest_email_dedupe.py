from __future__ import annotations

import datetime
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo


class TestKalshiDigestEmailDedupe(unittest.TestCase):
    def test_main_skips_recent_duplicate_email_send(self) -> None:
        import scripts.kalshi_digest as dig

        fixed_now = 1773342109
        et = datetime.datetime.fromtimestamp(fixed_now, tz=ZoneInfo("America/New_York"))
        subject = f"ORION Kalshi • 8h • {et.strftime('%b')} {et.day}"
        to_email = "cory.stoner@icloud.com"

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "tmp", "kalshi_ref_arb", "last_email_send.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "ts_unix": fixed_now - 30,
                        "ok": True,
                        "to": to_email,
                        "subject": subject,
                        "message_id": "test-message-id",
                    },
                    f,
                )

            with patch.object(dig, "_repo_root", return_value=td), patch.object(
                dig, "_send_email_via_agentmail", side_effect=AssertionError("email send should be deduped")
            ), patch("scripts.kalshi_digest.time.time", return_value=float(fixed_now)), patch.dict(
                os.environ,
                {"KALSHI_ARB_DIGEST_EMAIL_TO": to_email, "KALSHI_ARB_EMAIL_DEDUPE_WINDOW_S": "900"},
                clear=False,
            ), patch("sys.argv", ["kalshi_digest.py", "--window-hours", "8", "--send-email"]):
                rc = dig.main()
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
