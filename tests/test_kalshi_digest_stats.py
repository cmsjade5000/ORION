from __future__ import annotations

import unittest


class TestKalshiDigestStats(unittest.TestCase):
    def test_extract_stats_does_not_count_scan_failed_as_error(self) -> None:
        from scripts.kalshi_digest import _extract_stats

        run_objs = [
            {
                "ts_unix": 1,
                "balance_rc": 0,
                "trade_rc": 2,
                "post_rc": 0,
                "trade": {"mode": "trade", "status": "refused", "reason": "scan_failed"},
            }
        ]
        s = _extract_stats(run_objs)
        self.assertEqual(int(s.errors), 0)

    def test_extract_stats_counts_real_trade_error(self) -> None:
        from scripts.kalshi_digest import _extract_stats

        run_objs = [
            {
                "ts_unix": 1,
                "balance_rc": 0,
                "trade_rc": 1,
                "post_rc": 0,
                "trade": {"mode": "trade", "status": "error", "reason": "exception"},
            }
        ]
        s = _extract_stats(run_objs)
        self.assertEqual(int(s.errors), 1)


if __name__ == "__main__":
    unittest.main()

