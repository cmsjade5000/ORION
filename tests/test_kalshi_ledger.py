from __future__ import annotations

import os
import tempfile
import time
import unittest


class TestKalshiLedger(unittest.TestCase):
    def test_update_from_run_records_order_and_fills(self) -> None:
        from scripts.arb.kalshi_ledger import load_ledger, save_ledger, update_from_run

        with tempfile.TemporaryDirectory() as td:
            # Minimal repo_root structure
            os.makedirs(os.path.join(td, "tmp", "kalshi_ref_arb"), exist_ok=True)
            save_ledger(td, {"version": 1, "orders": {}, "unmatched_settlements": [], "settlement_hashes": []})

            ts = int(time.time())
            trade = {
                "placed": [
                    {
                        "mode": "live",
                        "order_id": "O1",
                        "order": {"ticker": "T1", "side": "yes", "action": "buy", "count": 2, "price_dollars": "0.10"},
                        "edge_bps": 150.0,
                        "effective_edge_bps": 150.0,
                        "uncertainty_bps": 50.0,
                        "p_yes": 0.8,
                        "p_no": 0.2,
                        "t_years": 0.01,
                        "spot_ref": 50000.0,
                        "sigma_annual": 0.9,
                        "strike": 51000.0,
                        "strike_type": "greater",
                        "expected_expiration_time": "2030-01-01T00:00:00Z",
                    }
                ]
            }
            post = {
                "fills": {"fills": [{"order_id": "O1", "ticker": "T1", "count": 2, "price_dollars": "0.10"}]},
                "settlements": {"settlements": []},
            }

            update_from_run(td, ts_unix=ts, trade=trade, post=post)
            led = load_ledger(td)
            self.assertIn("O1", led["orders"])
            o = led["orders"]["O1"]
            self.assertEqual(o.get("ticker"), "T1")
            self.assertIn("fills", o)
            self.assertEqual(int(o["fills"]["count"]), 2)

    def test_update_from_run_attributes_settlement_with_cents_outcome(self) -> None:
        from scripts.arb.kalshi_ledger import load_ledger, save_ledger, update_from_run

        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "tmp", "kalshi_ref_arb"), exist_ok=True)
            save_ledger(td, {"version": 1, "orders": {}, "unmatched_settlements": [], "settlement_hashes": []})

            ts = int(time.time())
            trade = {
                "placed": [
                    {
                        "mode": "live",
                        "order_id": "O2",
                        "order": {"ticker": "T2", "side": "no", "action": "buy", "count": 1, "price_dollars": "0.40"},
                    }
                ]
            }
            post = {
                "fills": {"fills": [{"order_id": "O2", "ticker": "T2", "count": 1, "price_dollars": "0.40"}]},
                "settlements": {"settlements": [{"market_ticker": "T2", "side": "no", "count": 1, "settlement_price_cents": 0}]},
            }

            update_from_run(td, ts_unix=ts, trade=trade, post=post)
            led = load_ledger(td)
            o = led["orders"]["O2"]
            self.assertIn("settlement", o)
            st = o["settlement"]
            self.assertIsInstance(st.get("parsed"), dict)
            self.assertIn("outcome_yes", st["parsed"])

    def test_update_from_run_ignores_zero_count_settlements(self) -> None:
        from scripts.arb.kalshi_ledger import load_ledger, save_ledger, update_from_run

        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "tmp", "kalshi_ref_arb"), exist_ok=True)
            save_ledger(td, {"version": 1, "orders": {}, "unmatched_settlements": [], "settlement_hashes": []})

            ts = int(time.time())
            trade = {"placed": []}
            post = {
                "fills": {"fills": []},
                "settlements": {
                    "settlements": [
                        {
                            "ticker": "T0",
                            "event_ticker": "E0",
                            "yes_count": 0,
                            "no_count": 0,
                            "revenue": 0,
                            "yes_total_cost": 0,
                            "no_total_cost": 0,
                        }
                    ]
                },
            }

            update_from_run(td, ts_unix=ts, trade=trade, post=post)
            led = load_ledger(td)
            self.assertEqual(list(led.get("unmatched_settlements") or []), [])
            self.assertEqual(list(led.get("settlement_hashes") or []), [])


if __name__ == "__main__":
    unittest.main()
