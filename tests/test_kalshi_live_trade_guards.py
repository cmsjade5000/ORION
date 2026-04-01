from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch


def _runtime_stub() -> SimpleNamespace:
    return SimpleNamespace(
        require_mapped_series=False,
        ref_feeds=["coinbase", "kraken", "binance"],
        enable_funding_filter=False,
        enable_regime_filter=False,
        max_ref_quote_age_sec=3.0,
        max_dispersion_bps=35.0,
        max_vol_anomaly_ratio=1.8,
        dynamic_edge_enabled=True,
        dynamic_edge_regime_mults={"calm": 0.9, "normal": 1.0, "hot": 1.2},
        reinvest_enabled=False,
        reinvest_max_fraction=0.08,
        drawdown_throttle_pct=5.0,
        paper_exec_emulator=True,
        paper_exec_latency_ms=250,
        paper_exec_slippage_bps=5.0,
        portfolio_allocator_enabled=False,
        portfolio_allocator_min_signal_fraction=0.05,
        portfolio_allocator_edge_power=1.0,
        portfolio_allocator_confidence_power=1.0,
        enable_strike_mono_arb=False,
        enable_time_mono_arb=False,
        enable_touch_ladder_arb=False,
        struct_min_edge_bps=220.0,
        struct_min_liquidity_usd=100.0,
    )


class FakeKalshiClient:
    def __init__(self, *, market_map, order_responses, fills_by_order_id):
        self.market_map = dict(market_map)
        self.order_responses = list(order_responses)
        self.fills_by_order_id = dict(fills_by_order_id)
        self.created_orders = []

    def get_balance(self):
        return {"balance": 10_000_00}

    def get_positions(self, limit=200):
        return {"market_positions": []}

    def get_market(self, ticker):
        return self.market_map.get(ticker)

    def create_order(self, order):
        self.created_orders.append(order)
        if not self.order_responses:
            raise AssertionError("unexpected create_order call")
        return self.order_responses.pop(0)

    def get_fills(self, limit=50, order_id="", min_ts=None, max_ts=None, cursor="", ticker="", subaccount=None):
        return self.fills_by_order_id.get(order_id, {"fills": []})


class TestKalshiLiveTradeGuards(unittest.TestCase):
    def _signal(self, mod, *, ticker: str, strike: float, p_yes: float, ask: float, edge_threshold_bps: float):
        return mod.Signal(
            ticker=ticker,
            strike_type="greater",
            strike=float(strike),
            expected_expiration_time="2030-01-01T00:00:00Z",
            spot_ref=100.0,
            t_years=0.5,
            sigma_annual=0.5,
            p_yes=float(p_yes),
            yes_bid=max(0.0, float(ask) - 0.01),
            yes_ask=float(ask),
            no_bid=max(0.0, 1.0 - float(ask) - 0.02),
            no_ask=max(0.0, 1.0 - float(ask) - 0.01),
            edge_bps_buy_yes=(float(p_yes) - float(ask)) * 10_000.0,
            edge_bps_buy_no=((1.0 - float(p_yes)) - max(0.0, 1.0 - float(ask) - 0.01)) * 10_000.0,
            recommended={
                "action": "buy",
                "side": "yes",
                "limit_price": f"{float(ask):.4f}",
                "edge_bps": (float(p_yes) - float(ask)) * 10_000.0,
                "effective_edge_bps": (float(p_yes) - float(ask)) * 10_000.0,
                "edge_threshold_bps": float(edge_threshold_bps),
            },
            filters={"liquidity_dollars": 1000.0, "yes_spread": 0.01, "no_spread": 0.01},
            rejected_reasons=[],
        )

    def _run_trade(self, *, signal, markets, client, extra_args=None, extra_env=None):
        import scripts.kalshi_ref_arb as mod

        argv = [
            "kalshi_ref_arb.py",
            "trade",
            "--series",
            "KXBTC",
            "--allow-write",
            "--max-contracts-per-order",
            "1",
            "--max-open-contracts-per-ticker",
            "0",
        ]
        if extra_args:
            argv.extend(extra_args)

        buf = io.StringIO()
        env = dict(extra_env or {})
        td = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, td, True)
        with patch.object(mod, "_repo_root", return_value=td):
            with patch.object(mod, "load_runtime_from_env", return_value=(_runtime_stub(), [])):
                with patch.object(mod, "_ref_spot_for_series", return_value=(100.0, {})):
                    with patch.object(mod, "_build_signals_for_markets", return_value=([signal], [signal])):
                        with patch.object(mod, "_list_markets_cached", return_value=(markets, False)):
                            with patch.object(mod, "_record_persistence_observations", return_value=None):
                                with patch.object(mod, "_compute_trade_diagnostics", return_value={}):
                                    with patch.object(mod, "KalshiClient", return_value=client):
                                        with patch.object(mod, "live_spot", return_value=None):
                                            with patch.object(mod, "_model_p_yes", return_value=signal.p_yes):
                                                with patch("sys.argv", argv):
                                                    with patch.dict("os.environ", env, clear=False):
                                                        with redirect_stdout(buf):
                                                            rc = mod.main()
        out = json.loads(buf.getvalue())
        return rc, out, td

    def test_live_recheck_uses_effective_edge_threshold(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.kalshi import KalshiMarket

        signal = self._signal(mod, ticker="KXBTC-PRIMARY", strike=101.0, p_yes=0.51, ask=0.48, edge_threshold_bps=150.0)
        primary_market = KalshiMarket(
            ticker="KXBTC-PRIMARY",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t",
            subtitle="s",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.49,
            yes_ask=0.50,
            no_bid=0.49,
            no_ask=0.50,
            liquidity_dollars=1000.0,
            floor_strike=101.0,
            cap_strike=None,
        )
        client = FakeKalshiClient(
            market_map={"KXBTC-PRIMARY": primary_market},
            order_responses=[],
            fills_by_order_id={},
        )

        rc, out, _ = self._run_trade(signal=signal, markets=[primary_market], client=client)
        self.assertEqual(rc, 0)
        self.assertEqual(len(client.created_orders), 0)
        self.assertEqual(out["skipped"][0]["detail"], "effective_edge_below_min")
        self.assertEqual(float(out["skipped"][0]["edge_threshold_bps"]), 150.0)

    def test_paired_hedge_requires_primary_fill_confirmation(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.kalshi import KalshiMarket

        signal = self._signal(mod, ticker="KXBTC-PRIMARY", strike=100.0, p_yes=0.62, ask=0.40, edge_threshold_bps=80.0)
        primary_market = KalshiMarket(
            ticker="KXBTC-PRIMARY",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t",
            subtitle="s",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.39,
            yes_ask=0.40,
            no_bid=0.59,
            no_ask=0.60,
            liquidity_dollars=1000.0,
            floor_strike=100.0,
            cap_strike=None,
        )
        hedge_market = KalshiMarket(
            ticker="KXBTC-HEDGE",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t2",
            subtitle="s2",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.19,
            yes_ask=0.20,
            no_bid=0.79,
            no_ask=0.20,
            liquidity_dollars=1000.0,
            floor_strike=110.0,
            cap_strike=None,
        )
        client = FakeKalshiClient(
            market_map={"KXBTC-PRIMARY": primary_market, "KXBTC-HEDGE": hedge_market},
            order_responses=[{"order": {"order_id": "primary", "status": "resting"}}],
            fills_by_order_id={"primary": {"fills": []}},
        )

        rc, out, _ = self._run_trade(
            signal=signal,
            markets=[primary_market, hedge_market],
            client=client,
            extra_env={"KALSHI_ARB_PAIRED_HEDGE": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(client.created_orders), 1)
        self.assertTrue(all(not bool(p.get("paired_hedge")) for p in out["placed"]))

    def test_paired_hedge_respects_post_primary_budget(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.kalshi import KalshiMarket

        signal = self._signal(mod, ticker="KXBTC-PRIMARY", strike=100.0, p_yes=0.98, ask=0.90, edge_threshold_bps=80.0)
        primary_market = KalshiMarket(
            ticker="KXBTC-PRIMARY",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t",
            subtitle="s",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.89,
            yes_ask=0.90,
            no_bid=0.09,
            no_ask=0.10,
            liquidity_dollars=1000.0,
            floor_strike=100.0,
            cap_strike=None,
        )
        hedge_market = KalshiMarket(
            ticker="KXBTC-HEDGE",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t2",
            subtitle="s2",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.79,
            yes_ask=0.80,
            no_bid=0.04,
            no_ask=0.05,
            liquidity_dollars=1000.0,
            floor_strike=110.0,
            cap_strike=None,
        )
        client = FakeKalshiClient(
            market_map={"KXBTC-PRIMARY": primary_market, "KXBTC-HEDGE": hedge_market},
            order_responses=[{"order": {"order_id": "primary", "status": "filled"}}],
            fills_by_order_id={"primary": {"fills": [{"count": 1, "price_dollars": 0.90}]}},
        )

        rc, out, _ = self._run_trade(
            signal=signal,
            markets=[primary_market, hedge_market],
            client=client,
            extra_args=["--max-notional-per-run-usd", "0.92", "--max-notional-per-market-usd", "0.92"],
            extra_env={"KALSHI_ARB_PAIRED_HEDGE": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(client.created_orders), 1)
        self.assertEqual(out["skipped"][-1]["reason"], "paired_risk_cap")

    def test_paired_hedge_persists_hedge_notional_when_filled(self) -> None:
        import scripts.kalshi_ref_arb as mod
        from scripts.arb.kalshi import KalshiMarket

        signal = self._signal(mod, ticker="KXBTC-PRIMARY", strike=100.0, p_yes=0.70, ask=0.40, edge_threshold_bps=80.0)
        primary_market = KalshiMarket(
            ticker="KXBTC-PRIMARY",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t",
            subtitle="s",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.39,
            yes_ask=0.40,
            no_bid=0.59,
            no_ask=0.60,
            liquidity_dollars=1000.0,
            floor_strike=100.0,
            cap_strike=None,
        )
        hedge_market = KalshiMarket(
            ticker="KXBTC-HEDGE",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t2",
            subtitle="s2",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.79,
            yes_ask=0.80,
            no_bid=0.19,
            no_ask=0.20,
            liquidity_dollars=1000.0,
            floor_strike=110.0,
            cap_strike=None,
        )
        client = FakeKalshiClient(
            market_map={"KXBTC-PRIMARY": primary_market, "KXBTC-HEDGE": hedge_market},
            order_responses=[
                {"order": {"order_id": "primary", "status": "filled"}},
                {"order": {"order_id": "hedge", "status": "filled"}},
            ],
            fills_by_order_id={
                "primary": {"fills": [{"count": 1, "price_dollars": 0.40}]},
                "hedge": {"fills": [{"count": 1, "price_dollars": 0.20}]},
            },
        )

        rc, out, td = self._run_trade(
            signal=signal,
            markets=[primary_market, hedge_market],
            client=client,
            extra_args=["--max-notional-per-run-usd", "2.0", "--max-notional-per-market-usd", "2.0"],
            extra_env={"KALSHI_ARB_PAIRED_HEDGE": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(len(client.created_orders), 2)
        self.assertTrue(any(bool(p.get("paired_hedge")) for p in out["placed"]))
        with open(f"{td}/tmp/kalshi_ref_arb/state.json", "r", encoding="utf-8") as f:
            state = json.load(f)
        self.assertAlmostEqual(float(state["markets"]["KXBTC-PRIMARY"]["notional_usd"]), 0.40, places=9)
        self.assertAlmostEqual(float(state["markets"]["KXBTC-HEDGE"]["notional_usd"]), 0.20, places=9)


if __name__ == "__main__":
    unittest.main()
