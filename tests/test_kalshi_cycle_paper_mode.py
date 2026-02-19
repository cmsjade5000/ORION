from __future__ import annotations

import json
import os
import tempfile
import unittest


class TestKalshiCyclePaperMode(unittest.TestCase):
    def test_build_trade_argv_paper_vs_live(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        base = dict(
            selected_series="KXBTC",
            sigma_arg="0.5",
            min_edge="120",
            uncertainty="50",
            min_liq="200",
            max_spread="0.05",
            min_tte="900",
            min_px="0.05",
            max_px="0.95",
            min_notional="0.2",
            min_notional_bypass="4000",
            persist="2",
            persist_win="30",
            sizing_mode="fixed",
            kelly_fraction="0.1",
            kelly_cap_fraction="0.1",
            bayes_prior_k="20",
            bayes_obs_k_max="30",
            vol_anomaly="0",
            vol_anomaly_window_h="24",
            max_market_concentration_fraction="0.35",
        )
        paper = cyc._build_trade_argv(allow_live_writes=False, **base)
        live = cyc._build_trade_argv(allow_live_writes=True, **base)
        self.assertNotIn("--allow-write", paper)
        self.assertIn("--allow-write", live)

    def test_write_cycle_status_and_metrics(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            cyc._write_cycle_status(td, status="skipped_lock", detail="lock held")
            p = os.path.join(td, "tmp", "kalshi_ref_arb", "last_cycle_status.json")
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            self.assertEqual(obj["status"], "skipped_lock")

            mpath = os.path.join(td, "tmp", "kalshi_ref_arb", "metrics.prom")
            artifact = {
                "ts_unix": 123,
                "balance_rc": 0,
                "trade_rc": 0,
                "post_rc": 0,
                "cycle_inputs": {"allow_live_writes": False},
                "trade": {"status": "ok", "placed": [], "skipped": []},
            }
            cyc._write_prom_metrics(td, metrics_path=mpath, enabled=True, artifact=artifact)
            with open(mpath, "r", encoding="utf-8") as f:
                text = f.read()
            self.assertIn("kalshi_cycle_last_ts_unix 123", text)
            self.assertIn("kalshi_cycle_allow_live_writes 0", text)


if __name__ == "__main__":
    unittest.main()
