from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch


class TestPolymarketSportsPaperCycle(unittest.TestCase):
    def test_lock_acquire_release_and_stale_recovery(self) -> None:
        import scripts.polymarket_sports_paper_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            lock_path = os.path.join(td, "tmp", "polymarket_sports_paper", "cycle.lock")
            ok1, reason1 = cyc._acquire_cycle_lock(lock_path, stale_after_s=600)
            self.assertTrue(ok1)
            self.assertEqual(reason1, "acquired")

            ok2, reason2 = cyc._acquire_cycle_lock(lock_path, stale_after_s=600)
            self.assertFalse(ok2)
            self.assertEqual(reason2, "lock_held")

            cyc._release_cycle_lock(lock_path)
            ok3, reason3 = cyc._acquire_cycle_lock(lock_path, stale_after_s=600)
            self.assertTrue(ok3)
            self.assertEqual(reason3, "acquired")
            cyc._release_cycle_lock(lock_path)

            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump({"pid": 9999, "ts_unix": int(time.time()) - 3600}, f)
            ok4, reason4 = cyc._acquire_cycle_lock(lock_path, stale_after_s=60)
            self.assertTrue(ok4)
            self.assertEqual(reason4, "acquired")
            cyc._release_cycle_lock(lock_path)

    def test_notification_cooldown(self) -> None:
        import scripts.polymarket_sports_paper_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            sig_a = "rc=124|err=timeout"
            sig_b = "rc=1|err=http_500"
            self.assertTrue(cyc._should_send_error_notification(td, signature=sig_a, now_unix=1_000, cooldown_s=900))
            cyc._mark_error_notification_sent(td, signature=sig_a, now_unix=1_000)
            self.assertFalse(cyc._should_send_error_notification(td, signature=sig_a, now_unix=1_100, cooldown_s=900))
            self.assertTrue(cyc._should_send_error_notification(td, signature=sig_b, now_unix=1_101, cooldown_s=900))
            self.assertTrue(cyc._should_send_error_notification(td, signature=sig_a, now_unix=1_901, cooldown_s=900))

    def test_main_skips_when_lock_held(self) -> None:
        import scripts.polymarket_sports_paper_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            lock_path = os.path.join(td, "tmp", "polymarket_sports_paper", "cycle.lock")
            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump({"pid": 123, "ts_unix": int(time.time())}, f)

            with patch.object(cyc, "_repo_root", return_value=td):
                rc = cyc.main()
            self.assertEqual(rc, 0)

            st_path = os.path.join(td, "tmp", "polymarket_sports_paper", "last_cycle_status.json")
            with open(st_path, "r", encoding="utf-8") as f:
                st = json.load(f)
            self.assertEqual(st.get("status"), "skipped_lock")


if __name__ == "__main__":
    unittest.main()

