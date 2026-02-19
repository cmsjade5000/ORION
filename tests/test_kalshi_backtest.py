from __future__ import annotations

import json
import os
import tempfile
import unittest


class TestKalshiBacktest(unittest.TestCase):
    def test_summarize_and_walk_forward(self) -> None:
        from scripts.arb.kalshi_backtest import summarize_rows, walk_forward

        rows = [
            {"ts_unix": 1, "pnl_raw_usd": 1.0, "pnl_adj_usd": 0.8},
            {"ts_unix": 2, "pnl_raw_usd": -1.0, "pnl_adj_usd": -1.2},
            {"ts_unix": 3, "pnl_raw_usd": 2.0, "pnl_adj_usd": 1.7},
            {"ts_unix": 4, "pnl_raw_usd": -0.5, "pnl_adj_usd": -0.7},
        ]
        s = summarize_rows(rows)
        self.assertEqual(s["count"], 4)
        self.assertIsInstance(s["win_rate"], float)
        self.assertIn("max_drawdown_pct", s)
        wf = walk_forward(rows, folds=3)
        self.assertIsInstance(wf, list)
        self.assertTrue(wf)

    def test_settled_rows_uses_ledger(self) -> None:
        from scripts.arb.kalshi_backtest import settled_rows

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "tmp", "kalshi_ref_arb", "closed_loop_ledger.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            now = 2_000_000_000
            obj = {
                "version": 1,
                "orders": {
                    "o1": {
                        "ts_unix": now - 60,
                        "ticker": "T1",
                        "side": "yes",
                        "fills": {"count": 1, "avg_price_dollars": 0.4},
                        "settlement": {"ts_seen": now - 10, "parsed": {"outcome_yes": True}},
                    }
                },
                "unmatched_settlements": [],
                "settlement_hashes": [],
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f)
            rows = settled_rows(td, window_hours=24 * 365 * 10, fee_bps=10.0, slippage_bps=5.0)
            self.assertEqual(len(rows), 1)
            self.assertGreater(rows[0]["pnl_raw_usd"], rows[0]["pnl_adj_usd"])


if __name__ == "__main__":
    unittest.main()
