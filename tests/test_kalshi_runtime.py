from __future__ import annotations

import unittest
from unittest.mock import patch


class TestKalshiRuntime(unittest.TestCase):
    def test_runtime_defaults(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {}, clear=False):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertEqual(cfg.execution_mode, "paper")
        self.assertFalse(cfg.allow_live_writes)
        self.assertEqual(cfg.ref_feeds, ["coinbase", "kraken", "binance"])
        self.assertIsInstance(errs, list)

    def test_runtime_live_arm_gate(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {"KALSHI_ARB_EXECUTION_MODE": "live", "KALSHI_ARB_LIVE_ARMED": "1"}, clear=False):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertFalse(errs)
        self.assertEqual(cfg.execution_mode, "live")
        self.assertTrue(cfg.allow_live_writes)

    def test_runtime_invalid_values_fall_back(self) -> None:
        from scripts.arb.kalshi_runtime import load_runtime_from_env

        with patch.dict("os.environ", {"KALSHI_ARB_EXECUTION_MODE": "oops", "KALSHI_ARB_RETRY_MAX_ATTEMPTS": "NaN"}, clear=False):
            cfg, errs = load_runtime_from_env(repo_root="/tmp")
        self.assertEqual(cfg.execution_mode, "paper")
        self.assertEqual(cfg.retry_max_attempts, 4)
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()

