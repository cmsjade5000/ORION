from __future__ import annotations

import unittest
from unittest.mock import patch


class TestKalshiRuntime(unittest.TestCase):
    def test_runtime_defaults(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {}, clear=True):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertEqual(cfg.execution_mode, "paper")
        self.assertFalse(cfg.allow_live_writes)
        self.assertEqual(cfg.ref_feeds, ["coinbase", "kraken", "binance"])
        self.assertTrue(cfg.dynamic_edge_enabled)
        self.assertEqual(cfg.dynamic_edge_regime_mults.get("hot"), 1.2)
        self.assertTrue(cfg.reinvest_enabled)
        self.assertTrue(cfg.paper_exec_emulator)
        self.assertTrue(cfg.portfolio_allocator_enabled)
        self.assertAlmostEqual(cfg.portfolio_allocator_min_signal_fraction, 0.05, places=9)
        self.assertAlmostEqual(cfg.max_ref_quote_age_sec, 3.0, places=9)
        self.assertAlmostEqual(cfg.paper_exec_slippage_bps, 2.0, places=9)
        self.assertTrue(cfg.require_mapped_series)
        self.assertTrue(cfg.enable_strike_mono_arb)
        self.assertTrue(cfg.enable_time_mono_arb)
        self.assertTrue(cfg.enable_touch_ladder_arb)
        self.assertAlmostEqual(cfg.struct_min_edge_bps, 220.0, places=9)
        self.assertAlmostEqual(cfg.struct_min_liquidity_usd, 25.0, places=9)
        self.assertTrue(cfg.router_enabled)
        self.assertAlmostEqual(cfg.router_max_series_share, 0.35, places=9)
        self.assertEqual(cfg.router_min_obs, 12)
        self.assertEqual(cfg.dry_streak_loosen_step_bps, 15)
        self.assertEqual(cfg.dry_streak_loosen_every_cycles, 10)
        self.assertEqual(cfg.loosen_floor_edge_bps, 70)
        self.assertIsInstance(errs, list)

    def test_runtime_live_arm_gate(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {"KALSHI_ARB_EXECUTION_MODE": "live", "KALSHI_ARB_LIVE_ARMED": "1"}, clear=True):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertFalse(errs)
        self.assertEqual(cfg.execution_mode, "live")
        self.assertTrue(cfg.allow_live_writes)

    def test_runtime_invalid_values_fall_back(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {"KALSHI_ARB_EXECUTION_MODE": "oops", "KALSHI_ARB_RETRY_MAX_ATTEMPTS": "NaN"}, clear=True):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertEqual(cfg.execution_mode, "paper")
        self.assertEqual(cfg.retry_max_attempts, 4)
        self.assertTrue(errs)

    def test_runtime_dispersion_alias_and_regime_mult_parse(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict(
            "os.environ",
            {
                "KALSHI_ARB_MAX_REF_DISPERSION_BPS": "42",
                "KALSHI_ARB_DYNAMIC_EDGE_REGIME_MULTS": "calm:0.8,normal:1.0,hot:1.5",
                "KALSHI_ARB_PORTFOLIO_ALLOCATOR_EDGE_POWER": "1.3",
            },
            clear=True,
        ):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertFalse(errs)
        self.assertAlmostEqual(cfg.max_dispersion_bps, 42.0, places=9)
        self.assertAlmostEqual(cfg.dynamic_edge_regime_mults.get("calm") or 0.0, 0.8, places=9)
        self.assertAlmostEqual(cfg.dynamic_edge_regime_mults.get("hot") or 0.0, 1.5, places=9)
        self.assertAlmostEqual(cfg.portfolio_allocator_edge_power, 1.3, places=9)

    def test_runtime_rewrites_legacy_orion_metrics_path_to_current_repo(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict(
            "os.environ",
            {
                "KALSHI_ARB_METRICS_PATH": "/Users/corystoner/src/ORION/tmp/kalshi_ref_arb/metrics.prom",
            },
            clear=True,
        ):
            cfg, errs = load_runtime_from_env(repo_root="/Users/corystoner/Desktop/ORION")
        self.assertEqual(cfg.metrics_path, "/Users/corystoner/Desktop/ORION/tmp/kalshi_ref_arb/metrics.prom")
        self.assertTrue(any("another ORION checkout" in err for err in errs))


if __name__ == "__main__":
    unittest.main()
