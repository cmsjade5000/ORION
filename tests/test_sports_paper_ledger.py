from __future__ import annotations

import tempfile
import time
import unittest


class TestSportsPaperLedger(unittest.TestCase):
    def test_add_settle_and_stats(self) -> None:
        from scripts.sports_paper.ledger import add_position, load_ledger, recompute_stats, save_ledger, settle_position

        with tempfile.TemporaryDirectory() as td:
            led = load_ledger(td)
            pid = add_position(
                led,
                {
                    "id": "p1",
                    "slug": "x-vs-y",
                    "shares": 10,
                    "sum_price": 0.97,
                    "side_mode": "yes",
                    "status": "open",
                },
            )
            self.assertEqual(pid, "p1")
            st = recompute_stats(led)
            self.assertEqual(int(st.get("open_positions") or 0), 1)
            ok = settle_position(led, "p1", settled_ts_unix=int(time.time()), pnl_usd=0.3, note="test")
            self.assertTrue(ok)
            st2 = recompute_stats(led)
            self.assertEqual(int(st2.get("settled_positions") or 0), 1)
            self.assertAlmostEqual(float(st2.get("realized_pnl_usd") or 0.0), 0.3, places=9)
            save_ledger(td, led)
            led2 = load_ledger(td)
            self.assertIn("p1", (led2.get("positions") or {}))


if __name__ == "__main__":
    unittest.main()

