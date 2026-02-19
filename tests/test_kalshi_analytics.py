from __future__ import annotations

import argparse
import os
import tempfile
import time
import unittest
from unittest import mock
from types import SimpleNamespace


class TestKalshiAnalytics(unittest.TestCase):
    def _mk_signal(self, mod, ticker: str, eff_edge: float, edge_threshold: float = 120.0):
        return mod.Signal(
            ticker=ticker,
            strike_type="greater",
            strike=1.0,
            expected_expiration_time="2030-01-01T00:00:00Z",
            spot_ref=50_000.0,
            t_years=0.01,
            sigma_annual=0.8,
            p_yes=0.55,
            yes_bid=0.49,
            yes_ask=0.50,
            no_bid=0.49,
            no_ask=0.50,
            edge_bps_buy_yes=eff_edge,
            edge_bps_buy_no=-50.0,
            recommended={
                "side": "yes",
                "limit_price": 0.50,
                "edge_bps": eff_edge + 20.0,
                "effective_edge_bps": eff_edge,
                "edge_threshold_bps": edge_threshold,
            },
            filters={},
            rejected_reasons=[],
        )

    def test_extract_market_position_counts_handles_common_shapes(self) -> None:
        from scripts.arb.kalshi_analytics import extract_market_position_counts

        post = {
            "positions": {
                "market_positions": [
                    {"ticker": "T1", "side": "yes", "count": 3},
                    {"ticker": "T1", "side": "no", "count": 2},
                    {"ticker": "T2", "yes_count": 5, "no_count": 0},
                    {"ticker": "T3", "position": {"yes": 7, "no": 1}},
                ]
            }
        }
        out = extract_market_position_counts(post)
        self.assertEqual(out["T1"]["yes"], 3)
        self.assertEqual(out["T1"]["no"], 2)
        self.assertEqual(out["T2"]["yes"], 5)
        self.assertEqual(out["T2"]["no"], 0)
        self.assertEqual(out["T3"]["yes"], 7)
        self.assertEqual(out["T3"]["no"], 1)

    def test_extract_market_position_counts_handles_signed_net_position(self) -> None:
        from scripts.arb.kalshi_analytics import extract_market_position_counts

        post = {"positions": {"market_positions": [{"ticker": "TYES", "position": 3}, {"ticker": "TNO", "position": -2}]}}
        out = extract_market_position_counts(post)
        self.assertEqual(out["TYES"]["yes"], 3)
        self.assertEqual(out["TYES"]["no"], 0)
        self.assertEqual(out["TNO"]["yes"], 0)
        self.assertEqual(out["TNO"]["no"], 2)

    def test_match_fills_for_order_aggregates_counts_and_avg(self) -> None:
        from scripts.arb.kalshi_analytics import match_fills_for_order

        post = {
            "fills": {
                "fills": [
                    {"order_id": "O1", "ticker": "T1", "count": 2, "price_dollars": "0.10"},
                    {"order_id": "O1", "ticker": "T1", "count": 1, "price_dollars": "0.20"},
                    {"order_id": "O2", "ticker": "T1", "count": 9, "price_dollars": "0.99"},
                ]
            }
        }
        m = match_fills_for_order(post, "O1")
        self.assertEqual(m["fills_count"], 3)
        self.assertAlmostEqual(float(m["avg_price_dollars"]), (0.10 * 2 + 0.20 * 1) / 3.0, places=12)

    def test_settlement_cash_delta_usd_sums_explicit_fields(self) -> None:
        from scripts.arb.kalshi_analytics import settlement_cash_delta_usd

        post = {
            "settlements": {
                "settlements": [
                    {"ticker": "A", "cash_delta_dollars": "1.25"},
                    {"ticker": "B", "cash_delta_dollars": 0.75},
                ]
            }
        }
        s = settlement_cash_delta_usd(post)
        self.assertAlmostEqual(float(s["cash_delta_usd"]), 2.0, places=12)

    def test_settlement_cash_delta_usd_handles_cents_variants(self) -> None:
        from scripts.arb.kalshi_analytics import settlement_cash_delta_usd

        post = {"settlements": {"settlements": [{"ticker": "A", "profit_cents": 125}, {"ticker": "B", "netCents": -25}]}}
        s = settlement_cash_delta_usd(post)
        self.assertAlmostEqual(float(s["cash_delta_usd"]), 1.0, places=12)

    def test_trade_diagnostics_best_candidate_ignores_untradable_price_bounds(self) -> None:
        import argparse
        import scripts.kalshi_ref_arb as mod

        args = argparse.Namespace(
            uncertainty_bps=50.0,
            min_edge_bps=80.0,
            min_seconds_to_expiry=900,
            min_liquidity_usd=200.0,
            max_spread=0.05,
            min_price=0.05,
            max_price=0.95,
            min_notional_usd=0.0,
            min_notional_bypass_edge_bps=0.0,
        )

        # Candidate A: higher effective edge but untradable due to ask=1.0 (out of bounds)
        s1 = mod.Signal(
            ticker="T_BAD",
            strike_type="greater",
            strike=1.0,
            expected_expiration_time="2030-01-01T00:00:00Z",
            spot_ref=50_000.0,
            t_years=0.01,
            sigma_annual=0.8,
            p_yes=0.9,
            yes_bid=0.99,
            yes_ask=1.0,
            no_bid=0.01,
            no_ask=0.02,
            edge_bps_buy_yes=200.0,
            edge_bps_buy_no=0.0,
            recommended=None,
            filters={"liquidity_dollars": 10_000.0, "yes_spread": 0.01, "no_spread": 0.01},
            rejected_reasons=[],
        )

        # Candidate B: lower edge but tradable within bounds.
        s2 = mod.Signal(
            ticker="T_OK",
            strike_type="greater",
            strike=1.0,
            expected_expiration_time="2030-01-01T00:00:00Z",
            spot_ref=50_000.0,
            t_years=0.01,
            sigma_annual=0.8,
            p_yes=0.7,
            yes_bid=0.49,
            yes_ask=0.50,
            no_bid=0.50,
            no_ask=0.51,
            edge_bps_buy_yes=150.0,
            edge_bps_buy_no=0.0,
            recommended=None,
            filters={"liquidity_dollars": 10_000.0, "yes_spread": 0.01, "no_spread": 0.01},
            rejected_reasons=[],
        )

        d = mod._compute_trade_diagnostics([s1, s2], args, markets_fetched=2, candidates_recommended=0)
        best = d.get("best_effective_edge_pass_filters")
        self.assertIsInstance(best, dict)
        assert isinstance(best, dict)
        self.assertEqual(best.get("ticker"), "T_OK")

    def test_signal_filters_gate_recommended_side(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.kalshi import KalshiMarket

        exp = time.gmtime(time.time() + 3600)
        exp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", exp)

        m = KalshiMarket(
            ticker="T",
            series_ticker="KXBTC",
            event_ticker="E",
            title="",
            subtitle="",
            status="open",
            strike_type="greater",
            floor_strike=1.0,
            expected_expiration_time=exp_iso,
            yes_bid=0.09,
            yes_ask=0.10,
            no_bid=0.89,
            no_ask=0.90,
            liquidity_dollars=10_000.0,
        )

        with mock.patch.object(mod, "_ref_spot_for_series", return_value=50_000.0), mock.patch.object(
            mod, "prob_lognormal_greater", return_value=0.90
        ):
            s = mod._signal_for_market(
                m,
                series="KXBTC",
                sigma_annual=0.85,
                min_edge_bps=50.0,
                uncertainty_bps=0.0,
                min_liquidity_usd=200.0,
                max_spread=0.05,
                min_seconds_to_expiry=900,
                min_price=0.05,
                max_price=0.95,
                min_notional_usd=0.0,
                min_notional_bypass_edge_bps=0.0,
            )
            self.assertIsNotNone(s)
            assert s is not None
            self.assertIsNotNone(s.recommended)
            assert s.recommended is not None
            self.assertEqual(s.recommended["side"], "yes")

            # Wide spread should remove recommendation on that side.
            m2 = KalshiMarket(**{**m.__dict__, "yes_bid": 0.01, "yes_ask": 0.10})
            s2 = mod._signal_for_market(
                m2,
                series="KXBTC",
                sigma_annual=0.85,
                min_edge_bps=50.0,
                uncertainty_bps=0.0,
                min_liquidity_usd=200.0,
                max_spread=0.05,
                min_seconds_to_expiry=900,
                min_price=0.05,
                max_price=0.95,
                min_notional_usd=0.0,
                min_notional_bypass_edge_bps=0.0,
            )
            self.assertIsNotNone(s2)
            assert s2 is not None
            self.assertIsNone(s2.recommended)

    def test_portfolio_allocator_prefers_stronger_signal(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.risk import RiskConfig, RiskState

        with tempfile.TemporaryDirectory() as td:
            state = RiskState(os.path.join(td, "state.json"))
            cfg = RiskConfig(
                max_orders_per_run=2,
                max_contracts_per_order=10,
                max_notional_per_run_usd=10.0,
                max_notional_per_market_usd=10.0,
                kill_switch_path="tmp/kalshi_ref_arb.KILL",
            )
            args = argparse.Namespace(min_edge_bps=120.0, max_market_concentration_fraction=0.8)
            rt = SimpleNamespace(
                portfolio_allocator_enabled=True,
                portfolio_allocator_min_signal_fraction=0.05,
                portfolio_allocator_edge_power=1.0,
                portfolio_allocator_confidence_power=1.0,
            )
            signals = [
                self._mk_signal(mod, "T_STRONG", 280.0),
                self._mk_signal(mod, "T_WEAK", 140.0),
            ]
            plan = mod._build_portfolio_allocator_plan(
                signals=signals,
                state=state,
                cfg=cfg,
                args=args,
                rt_cfg=rt,
                cash_usd=100.0,
                drawdown_mult=1.0,
            )
            self.assertTrue(plan.enabled)
            self.assertAlmostEqual(float(plan.run_budget_usd), 10.0, places=9)
            self.assertGreater(float(plan.per_ticker_target_usd.get("T_STRONG") or 0.0), float(plan.per_ticker_target_usd.get("T_WEAK") or 0.0))

    def test_portfolio_allocator_respects_existing_market_notional_cap(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.risk import RiskConfig, RiskState

        with tempfile.TemporaryDirectory() as td:
            state = RiskState(os.path.join(td, "state.json"))
            state.add_market_notional_usd("T_CAPPED", 9.6)
            cfg = RiskConfig(
                max_orders_per_run=2,
                max_contracts_per_order=10,
                max_notional_per_run_usd=12.0,
                max_notional_per_market_usd=10.0,
                kill_switch_path="tmp/kalshi_ref_arb.KILL",
            )
            args = argparse.Namespace(min_edge_bps=120.0, max_market_concentration_fraction=0.9)
            rt = SimpleNamespace(
                portfolio_allocator_enabled=True,
                portfolio_allocator_min_signal_fraction=0.05,
                portfolio_allocator_edge_power=1.0,
                portfolio_allocator_confidence_power=1.0,
            )
            signals = [self._mk_signal(mod, "T_CAPPED", 300.0)]
            plan = mod._build_portfolio_allocator_plan(
                signals=signals,
                state=state,
                cfg=cfg,
                args=args,
                rt_cfg=rt,
                cash_usd=100.0,
                drawdown_mult=1.0,
            )
            self.assertLessEqual(float(plan.per_ticker_target_usd.get("T_CAPPED") or 0.0), 0.4 + 1e-9)


if __name__ == "__main__":
    unittest.main()
