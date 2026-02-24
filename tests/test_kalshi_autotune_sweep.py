from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from unittest import mock


def _write_ledger(repo_root: str, orders: dict) -> None:
    p = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "closed_loop_ledger.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    obj = {"version": 1, "orders": orders, "unmatched_settlements": [], "settlement_hashes": []}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def _write_sweep(repo_root: str, entries: list[dict]) -> None:
    p = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "sweep_stats.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"entries": entries, "updated_ts_unix": int(time.time()), "window_s": 24 * 3600}, f)


class TestKalshiAutotuneSweep(unittest.TestCase):
    def test_sweep_tune_can_loosen_when_recommendations_zero(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = [
                {
                    "ts_unix": now - (30 - i) * 60,
                    "candidates_recommended": 0,
                    "placed_live": 0,
                    "blockers_top": ["liquidity_below_min"],
                }
                for i in range(30)
            ]
            _write_sweep(td, entries)

            env = {
                "KALSHI_ARB_TUNE_ENABLED": "1",
                "KALSHI_ARB_TUNE_MIN_SETTLED": "20",
                "KALSHI_ARB_EXECUTION_MODE": "paper",
                "KALSHI_ARB_LIVE_ARMED": "0",
                "KALSHI_ARB_MIN_LIQUIDITY_USD": "20",
                "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "900",
                "KALSHI_ARB_MIN_EDGE_BPS": "170",
                "KALSHI_ARB_MIN_NOTIONAL_USD": "0.50",
                "KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES": "24",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
                "KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S": "1",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                st = maybe_autotune(td)

            self.assertEqual(st.get("status"), "sweep_applied")
            ovp = os.path.join(td, "tmp", "kalshi_ref_arb", "params_override.json")
            self.assertTrue(os.path.exists(ovp))
            with open(ovp, "r", encoding="utf-8") as f:
                ov = json.load(f)
            params = ov.get("params") or {}
            self.assertLess(int(float(params.get("KALSHI_ARB_MIN_LIQUIDITY_USD", 20))), 20)

    def test_sweep_tune_can_tighten_when_recommendations_high(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = [
                {
                    "ts_unix": now - (30 - i) * 60,
                    "candidates_recommended": 2,
                    "placed_live": 0,
                    "blockers_top": [],
                }
                for i in range(30)
            ]
            _write_sweep(td, entries)

            env = {
                "KALSHI_ARB_TUNE_ENABLED": "1",
                "KALSHI_ARB_TUNE_MIN_SETTLED": "20",
                "KALSHI_ARB_EXECUTION_MODE": "paper",
                "KALSHI_ARB_LIVE_ARMED": "0",
                "KALSHI_ARB_MIN_EDGE_BPS": "170",
                "KALSHI_ARB_MIN_LIQUIDITY_USD": "13",
                "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "900",
                "KALSHI_ARB_MIN_NOTIONAL_USD": "0.50",
                "KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES": "24",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
                "KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S": "1",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                st = maybe_autotune(td)

            self.assertEqual(st.get("status"), "sweep_applied")
            ovp = os.path.join(td, "tmp", "kalshi_ref_arb", "params_override.json")
            with open(ovp, "r", encoding="utf-8") as f:
                ov = json.load(f)
            params = ov.get("params") or {}
            self.assertGreater(int(float(params.get("KALSHI_ARB_MIN_EDGE_BPS", 170))), 170)


if __name__ == "__main__":
    unittest.main()
