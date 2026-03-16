from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch


class TestKalshiCyclePaperMode(unittest.TestCase):
    def _arg_value(self, argv: list[str], flag: str) -> str | None:
        try:
            i = argv.index(flag)
        except ValueError:
            return None
        if i + 1 >= len(argv):
            return None
        return argv[i + 1]

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
        with patch.dict("os.environ", {}, clear=True):
            paper = cyc._build_trade_argv(allow_live_writes=False, **base)
            live = cyc._build_trade_argv(allow_live_writes=True, **base)
        self.assertNotIn("--allow-write", paper)
        self.assertIn("--allow-write", live)
        self.assertIn("--ignore-zero-liquidity", paper)
        self.assertNotIn("--ignore-zero-liquidity", live)
        self.assertEqual(self._arg_value(paper, "--max-orders-per-run"), "6")
        self.assertEqual(self._arg_value(paper, "--max-contracts-per-order"), "3")
        self.assertEqual(self._arg_value(paper, "--max-notional-per-run-usd"), "20")
        self.assertEqual(self._arg_value(paper, "--max-notional-per-market-usd"), "12")
        self.assertEqual(self._arg_value(paper, "--max-open-contracts-per-ticker"), "8")

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

    def test_recent_run_health_quarantines_old_bad_json(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "tmp", "kalshi_ref_arb", "runs")
            os.makedirs(runs, exist_ok=True)
            good = os.path.join(runs, "1770000100.json")
            with open(good, "w", encoding="utf-8") as f:
                json.dump({"ts_unix": 1770000100, "balance_rc": 0, "trade_rc": 0, "post_rc": 0, "trade": {"status": "ok"}}, f)
            bad = os.path.join(runs, "1770000000.json")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("{broken")
            old = time.time() - 1000.0
            os.utime(bad, (old, old))

            h = cyc._recent_run_health(runs, lookback=10, min_ts_unix=0)
            self.assertEqual(int(h.get("runs") or 0), 1)
            self.assertFalse(os.path.exists(bad))
            self.assertTrue(os.path.isdir(os.path.join(td, "tmp", "kalshi_ref_arb", "runs_bad")))

    def test_series_rotation_triggers_on_dry_primary_rounds(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "tmp", "kalshi_ref_arb", "sweep_stats.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            now = int(time.time())
            entries = []
            for i in range(36):
                entries.append(
                    {
                        "ts_unix": now - (36 - i) * 60,
                        "series": "KXBTC",
                        "candidates_recommended": 0,
                        "placed_total": 0,
                        "blockers_top": ["liquidity_below_min"],
                    }
                )
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"window_s": 24 * 3600, "entries": entries}, f)

            old_env = dict(os.environ)
            try:
                os.environ["KALSHI_ARB_SERIES_ROTATION_ENABLED"] = "1"
                os.environ["KALSHI_ARB_SERIES_ROTATION_DRY_ROUNDS"] = "3"
                os.environ["KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES"] = "12"
                os.environ["KALSHI_ARB_SERIES_FALLBACKS"] = "KXETH"
                out, meta = cyc._maybe_expand_series_with_rotation(td, ["KXBTC"])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertIn("KXETH", out)
            self.assertTrue(bool(meta.get("triggered")))

    def test_detect_stuck_state_zero_placements(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "tmp", "kalshi_ref_arb", "sweep_stats.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            now = int(time.time())
            entries = []
            for i in range(30):
                entries.append(
                    {
                        "ts_unix": now - (30 - i) * 60,
                        "series": "KXBTC",
                        "candidates_recommended": 0,
                        "placed_total": 0,
                        "blockers_top": ["liquidity_below_min"],
                    }
                )
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"window_s": 24 * 3600, "entries": entries}, f)

            old_env = dict(os.environ)
            try:
                os.environ["KALSHI_ARB_STUCK_ENABLED"] = "1"
                os.environ["KALSHI_ARB_STUCK_MIN_CYCLES"] = "24"
                os.environ["KALSHI_ARB_STUCK_DOMINANT_BLOCKER_SHARE"] = "0.70"
                st = cyc._detect_stuck_state(td, now_unix=int(now))
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertTrue(bool(st.get("active")))
            self.assertEqual(str(st.get("dominant_blocker") or ""), "liquidity_below_min")

    def test_sum_entry_placed_total_backcompat(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        self.assertEqual(cyc._sum_entry_placed_total({"placed_total": 3, "placed_live": 1, "placed_paper": 1}), 3)
        self.assertEqual(cyc._sum_entry_placed_total({"placed_live": 1, "placed_paper": 2}), 3)

    def test_merge_series_lists_dedup(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        merged = cyc._merge_series_lists(["KXBTC", "KXETH"], ["KXETH", "KXBTCD"])
        self.assertEqual(merged, ["KXBTC", "KXETH", "KXBTCD"])

    def test_resolve_sigma_arg_falls_back_when_auto_unavailable(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        with patch.object(cyc, "conservative_sigma_auto", return_value=None):
            self.assertEqual(cyc._resolve_sigma_arg("KXSOL15M", sigma="auto", sigma_window_h=168), "0.8500")

    def test_scan_series_uses_numeric_sigma_when_auto_unavailable(self) -> None:
        import scripts.kalshi_autotrade_cycle as cyc

        captured: dict[str, list[str]] = {}

        def fake_run_cmd_json(argv: list[str], cwd: str, timeout_s: int):
            captured["argv"] = list(argv)
            return 0, "", {"inputs": {}, "signals": []}

        with tempfile.TemporaryDirectory() as td:
            with patch.object(cyc, "conservative_sigma_auto", return_value=None):
                with patch.object(cyc, "_run_cmd_json", side_effect=fake_run_cmd_json):
                    out = cyc._scan_series(
                        td,
                        "KXSOL15M",
                        sigma="auto",
                        sigma_window_h=168,
                        min_edge="200",
                        uncertainty="50",
                        min_liq="115",
                        max_spread="0.1",
                        min_tte="180",
                        min_px="0.05",
                        max_px="0.97",
                        min_notional="0.50",
                        min_notional_bypass="2500",
                    )

        self.assertEqual(captured["argv"][captured["argv"].index("--sigma-annual") + 1], "0.8500")
        self.assertEqual(out["_sigma_arg"], "0.8500")


if __name__ == "__main__":
    unittest.main()
