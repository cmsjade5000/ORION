from __future__ import annotations

import unittest

from scripts.arb.kalshi import KalshiMarket


def _mkt() -> KalshiMarket:
    return KalshiMarket(
        ticker="T1",
        series_ticker="KXBTC",
        event_ticker="E1",
        title="t",
        subtitle="s",
        status="open",
        strike_type="greater",
        expected_expiration_time="2030-01-01T00:00:00Z",
        yes_bid=0.45,
        yes_ask=0.46,
        no_bid=0.54,
        no_ask=0.55,
        liquidity_dollars=1000.0,
        floor_strike=100.0,
        cap_strike=None,
    )


class TestKalshiRegimeFundingFilters(unittest.TestCase):
    def test_regime_filter_blocks_signal(self) -> None:
        import scripts.kalshi_ref_arb as mod

        s = mod._signal_for_market(
            _mkt(),
            series="KXBTC",
            spot=105.0,
            sigma_annual=0.6,
            min_edge_bps=5.0,
            uncertainty_bps=0.0,
            min_liquidity_usd=10.0,
            max_spread=0.2,
            min_seconds_to_expiry=10,
            min_price=0.01,
            max_price=0.99,
            min_notional_usd=0.0,
            min_notional_bypass_edge_bps=0.0,
            enable_regime_filter=True,
            max_vol_anomaly_ratio=1.5,
            vol_anomaly_ratio=2.0,
        )
        self.assertIsNotNone(s)
        self.assertIn("vol_regime_too_hot", (s.rejected_reasons or []))

    def test_funding_filter_blocks_signal(self) -> None:
        import scripts.kalshi_ref_arb as mod

        s = mod._signal_for_market(
            _mkt(),
            series="KXBTC",
            spot=105.0,
            sigma_annual=0.6,
            min_edge_bps=5.0,
            uncertainty_bps=0.0,
            min_liquidity_usd=10.0,
            max_spread=0.2,
            min_seconds_to_expiry=10,
            min_price=0.01,
            max_price=0.99,
            min_notional_usd=0.0,
            min_notional_bypass_edge_bps=0.0,
            enable_funding_filter=True,
            funding_rate_bps=8.0,
            funding_abs_bps_max=3.0,
        )
        self.assertIsNotNone(s)
        self.assertIn("funding_too_extreme", (s.rejected_reasons or []))


if __name__ == "__main__":
    unittest.main()

