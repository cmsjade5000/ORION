from __future__ import annotations

import unittest


class TestKalshiNotionalGate(unittest.TestCase):
    def test_low_notional_requires_huge_edge(self) -> None:
        # Low-notional orders (e.g. $0.05) are fee-dominated on Kalshi, so ORION
        # should skip them unless the effective edge is extremely large.
        from scripts.arb.kalshi import KalshiMarket
        from scripts.kalshi_ref_arb import _signal_for_market

        # Setup a market where YES ask is low ($0.05) and spread is tight, but
        # probability is only moderately above price (edge not "huge").
        m = KalshiMarket(
            ticker="T1",
            series_ticker="KXBTC",
            event_ticker="E1",
            title="t",
            subtitle="s",
            status="open",
            strike_type="greater",
            expected_expiration_time="2030-01-01T00:00:00Z",
            yes_bid=0.04,
            yes_ask=0.05,
            no_bid=0.95,
            no_ask=0.96,
            liquidity_dollars=1000.0,
            floor_strike=52000.0,
            cap_strike=None,
        )

        sig = _signal_for_market(
            m,
            series="KXBTC",
            spot=50000.0,
            sigma_annual=0.60,
            min_edge_bps=50.0,
            uncertainty_bps=40.0,
            min_liquidity_usd=30.0,
            max_spread=0.07,
            min_seconds_to_expiry=900,
            min_price=0.01,
            max_price=0.95,
            min_notional_usd=0.20,
            min_notional_bypass_edge_bps=4000.0,
        )

        self.assertIsNotNone(sig)
        assert sig is not None
        # The low-notional YES side should be blocked unless edge is extremely high.
        self.assertIn("yes_notional_below_min", sig.rejected_reasons)
        self.assertIsNone(sig.recommended)


if __name__ == "__main__":
    unittest.main()

