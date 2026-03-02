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
    def test_bounded_uses_paper_floor_overrides_only_in_paper(self) -> None:
        from scripts.arb import kalshi_autotune as ka

        params = {
            "KALSHI_ARB_MIN_EDGE_BPS": "50",
            "KALSHI_ARB_MIN_LIQUIDITY_USD": "4",
            "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "90",
        }

        env_paper = {
            "KALSHI_ARB_EXECUTION_MODE": "paper",
            "KALSHI_ARB_LIVE_ARMED": "0",
            "KALSHI_ARB_TUNE_PAPER_MIN_EDGE_BPS_FLOOR": "70",
            "KALSHI_ARB_TUNE_PAPER_MIN_LIQUIDITY_USD_FLOOR": "5",
            "KALSHI_ARB_TUNE_PAPER_MIN_SECONDS_TO_EXPIRY_FLOOR": "180",
        }
        with mock.patch.dict(os.environ, env_paper, clear=False):
            out_paper = ka._bounded(params)
        self.assertEqual(str(out_paper.get("KALSHI_ARB_MIN_EDGE_BPS")), "70")
        self.assertEqual(str(out_paper.get("KALSHI_ARB_MIN_LIQUIDITY_USD")), "5")
        self.assertEqual(str(out_paper.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY")), "180")

        env_live = {
            "KALSHI_ARB_EXECUTION_MODE": "live",
            "KALSHI_ARB_LIVE_ARMED": "1",
            "KALSHI_ARB_TUNE_PAPER_MIN_EDGE_BPS_FLOOR": "70",
            "KALSHI_ARB_TUNE_PAPER_MIN_LIQUIDITY_USD_FLOOR": "5",
            "KALSHI_ARB_TUNE_PAPER_MIN_SECONDS_TO_EXPIRY_FLOOR": "180",
        }
        with mock.patch.dict(os.environ, env_live, clear=False):
            out_live = ka._bounded(params)
        self.assertEqual(str(out_live.get("KALSHI_ARB_MIN_EDGE_BPS")), "80")
        self.assertEqual(str(out_live.get("KALSHI_ARB_MIN_LIQUIDITY_USD")), "8")
        self.assertEqual(str(out_live.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY")), "300")

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
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
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
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
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

    def test_sweep_tune_waits_until_next_completed_round(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = [
                {
                    "ts_unix": now - (24 - i) * 60,
                    "candidates_recommended": 0,
                    "placed_live": 0,
                    "blockers_top": ["liquidity_below_min"],
                }
                for i in range(24)
            ]
            _write_sweep(td, entries)

            env = {
                "KALSHI_ARB_TUNE_ENABLED": "1",
                "KALSHI_ARB_TUNE_MIN_SETTLED": "20",
                "KALSHI_ARB_EXECUTION_MODE": "paper",
                "KALSHI_ARB_LIVE_ARMED": "0",
                "KALSHI_ARB_MIN_LIQUIDITY_USD": "20",
                "KALSHI_ARB_MIN_EDGE_BPS": "170",
                "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "900",
                "KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES": "12",
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
                "KALSHI_ARB_TUNE_SWEEP_GROUPS_LOOKBACK": "2",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                st1 = maybe_autotune(td)
            self.assertEqual(st1.get("status"), "sweep_applied")

            # Force cooldown bypass while preserving round id: should wait for next round boundary.
            tsp = os.path.join(td, "tmp", "kalshi_ref_arb", "tune_state.json")
            with open(tsp, "r", encoding="utf-8") as f:
                ts = json.load(f)
            stn = ts.get("sweep_tune") if isinstance(ts.get("sweep_tune"), dict) else {}
            stn["last_apply_ts"] = 0
            ts["sweep_tune"] = stn
            with open(tsp, "w", encoding="utf-8") as f:
                json.dump(ts, f)

            with mock.patch.dict(os.environ, env, clear=False):
                st2 = maybe_autotune(td)
            self.assertEqual(st2.get("status"), "sweep_round_wait")
            self.assertEqual((st2.get("sweep_tune") or {}).get("status"), "round_wait")

    def test_weighted_selection_prefers_dominant_blocker(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = []
            for i in range(30):
                blockers = ["liquidity_below_min"]
                if i % 6 == 0:
                    blockers = ["too_close_to_expiry"]
                entries.append(
                    {
                        "ts_unix": now - (30 - i) * 60,
                        "candidates_recommended": 0,
                        "placed_live": 0,
                        "blockers_top": blockers,
                    }
                )
            _write_sweep(td, entries)

            env = {
                "KALSHI_ARB_TUNE_ENABLED": "1",
                "KALSHI_ARB_TUNE_MIN_SETTLED": "20",
                "KALSHI_ARB_EXECUTION_MODE": "paper",
                "KALSHI_ARB_LIVE_ARMED": "0",
                "KALSHI_ARB_MIN_LIQUIDITY_USD": "20",
                "KALSHI_ARB_MIN_EDGE_BPS": "170",
                "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "900",
                "KALSHI_ARB_MIN_NOTIONAL_USD": "0.50",
                "KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES": "24",
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
                "KALSHI_ARB_TUNE_SWEEP_GROUPS_LOOKBACK": "3",
                "KALSHI_ARB_TUNE_SWEEP_MAX_CHANGES_PER_ROUND": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                st = maybe_autotune(td)

            self.assertEqual(st.get("status"), "sweep_applied")
            ovp = os.path.join(td, "tmp", "kalshi_ref_arb", "params_override.json")
            with open(ovp, "r", encoding="utf-8") as f:
                ov = json.load(f)
            recs = (((ov.get("meta") or {}).get("recs")) or [])
            self.assertTrue(recs)
            self.assertEqual(recs[0].get("env"), "KALSHI_ARB_MIN_LIQUIDITY_USD")

    def test_sweep_tune_tightens_when_placements_exceed_target(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = [
                {
                    "ts_unix": now - (30 - i) * 60,
                    "candidates_recommended": 0,
                    "placed_live": 0,
                    "placed_paper": 1,
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
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_PLACED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_PLACED": "2",
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

    def test_sweep_tune_respects_paper_liquidity_floor(self) -> None:
        from scripts.arb.kalshi_autotune import maybe_autotune

        with tempfile.TemporaryDirectory() as td:
            _write_ledger(td, {})
            now = int(time.time())
            entries = [
                {
                    "ts_unix": now - (30 - i) * 60,
                    "candidates_recommended": 0,
                    "placed_live": 0,
                    "placed_paper": 0,
                    "blockers_top": ["liquidity_below_min"],
                }
                for i in range(30)
            ]
            _write_sweep(td, entries)

            env = {
                "KALSHI_ARB_TUNE_ENABLED": "1",
                "KALSHI_ARB_EXECUTION_MODE": "paper",
                "KALSHI_ARB_LIVE_ARMED": "0",
                "KALSHI_ARB_TUNE_MIN_SETTLED": "20",
                "KALSHI_ARB_MIN_EDGE_BPS": "90",
                "KALSHI_ARB_MIN_LIQUIDITY_USD": "6",
                "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY": "900",
                "KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES": "24",
                "KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS": "1",
                "KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES": "12",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED": "1",
                "KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED": "8",
                "KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S": "1",
                "KALSHI_ARB_TUNE_PAPER_MIN_LIQUIDITY_USD_FLOOR": "5",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                st = maybe_autotune(td)

            self.assertEqual(st.get("status"), "sweep_applied")
            ovp = os.path.join(td, "tmp", "kalshi_ref_arb", "params_override.json")
            with open(ovp, "r", encoding="utf-8") as f:
                ov = json.load(f)
            params = ov.get("params") or {}
            self.assertEqual(str(params.get("KALSHI_ARB_MIN_LIQUIDITY_USD")), "5")


if __name__ == "__main__":
    unittest.main()
