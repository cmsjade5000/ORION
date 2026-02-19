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

    def test_tca_by_variant_aggregates_rows(self) -> None:
        from scripts.kalshi_digest import _tca_by_variant

        rows = [
            {"variant": "champion", "fills_count": 2, "edge_bps": 180, "slippage_bps": 4, "avg_fill_price": 0.6, "fee_total_usd": 0.01},
            {"variant": "champion", "fills_count": 1, "edge_bps": 120, "slippage_bps": 2, "avg_fill_price": 0.5, "fee_total_usd": 0.00},
            {"variant": "challenger", "fills_count": 1, "edge_bps": 200, "slippage_bps": 6, "avg_fill_price": 0.7, "fee_total_usd": 0.02},
        ]
        out = _tca_by_variant(rows)
        self.assertIn("champion", out)
        self.assertIn("challenger", out)
        self.assertEqual(int(out["champion"]["placed_orders"]), 2)
        self.assertEqual(int(out["champion"]["filled_contracts"]), 3)
        self.assertAlmostEqual(float(out["champion"]["avg_slippage_bps"]), 3.0, places=9)


if __name__ == "__main__":
    unittest.main()
