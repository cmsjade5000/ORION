from __future__ import annotations

import unittest
import os
import tempfile
import time


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

    def test_param_recommendations_can_use_sweep_rollup_without_settled(self) -> None:
        from scripts.kalshi_digest import _param_recommendations

        recs = _param_recommendations(
            {},
            current_inputs={
                "min_liquidity_usd": 200,
                "min_edge_bps": 120,
                "min_notional_usd": 0.20,
            },
            sweep_roll={
                "cycles": 120,
                "placed_live": 0,
                "best_eff_edge_bps_max": 112.0,
                "top_blockers": [
                    {"reason": "liquidity_below_min", "count": 40},
                    {"reason": "no_edge_below_min", "count": 18},
                    {"reason": "yes_notional_below_min", "count": 16},
                ],
            },
        )
        envs = {str(r.get("env")) for r in recs if isinstance(r, dict)}
        self.assertIn("KALSHI_ARB_MIN_LIQUIDITY_USD", envs)
        self.assertIn("KALSHI_ARB_MIN_EDGE_BPS", envs)
        self.assertIn("KALSHI_ARB_MIN_NOTIONAL_USD", envs)

    def test_load_run_obj_quarantines_old_malformed_json(self) -> None:
        from scripts.kalshi_digest import _load_run_obj

        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "tmp", "kalshi_ref_arb", "runs")
            os.makedirs(runs, exist_ok=True)
            bad = os.path.join(runs, "1770000000.json")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("{invalid json")
            # Make it old enough to quarantine.
            old = time.time() - 1000.0
            os.utime(bad, (old, old))

            obj, moved = _load_run_obj(bad, quarantine_bad=True)
            self.assertIsNone(obj)
            self.assertTrue(bool(moved))
            self.assertFalse(os.path.exists(bad))
            bad_dir = os.path.join(td, "tmp", "kalshi_ref_arb", "runs_bad")
            self.assertTrue(os.path.isdir(bad_dir))
            self.assertTrue(any(name.endswith(".json") for name in os.listdir(bad_dir)))


if __name__ == "__main__":
    unittest.main()
