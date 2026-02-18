import types


def test_between_strike_supported(monkeypatch):
    # Import module under test.
    import scripts.kalshi_ref_arb as mod
    from scripts.arb.kalshi import KalshiMarket

    # Patch spot ref to avoid network.
    monkeypatch.setattr(mod, "ref_spot_btc_usd", lambda: 100.0)

    m = KalshiMarket(
        ticker="TEST-BETWEEN",
        series_ticker="KXBTC",
        event_ticker="KXBTC-TEST",
        title="Test",
        subtitle="90 to 110",
        status="open",
        strike_type="between",
        floor_strike=90.0,
        cap_strike=110.0,
        expected_expiration_time="2099-01-01T00:00:00Z",
        yes_bid=0.49,
        yes_ask=0.50,
        no_bid=0.49,
        no_ask=0.50,
        liquidity_dollars=1000.0,
    )

    s = mod._signal_for_market(
        m,
        series="KXBTC",
        sigma_annual=0.5,
        min_edge_bps=-10_000.0,  # don't filter on edge for this test
        uncertainty_bps=0.0,
        min_liquidity_usd=0.0,
        max_spread=1.0,
        min_seconds_to_expiry=0,
        min_price=0.0,
        max_price=1.0,
        min_notional_usd=0.0,
        min_notional_bypass_edge_bps=0.0,
    )
    assert s is not None
    assert s.strike_type == "between"
    assert s.strike == 90.0
    assert s.strike_high == 110.0
    assert 0.0 <= s.p_yes <= 1.0


def test_less_strike_uses_cap_strike(monkeypatch):
    import scripts.kalshi_ref_arb as mod
    from scripts.arb.kalshi import KalshiMarket

    # Also cover the pure helper routing (no network).
    seen = {}

    def fake_prob(spot, strike, t_years, sigma_annual):
        seen["spot"] = spot
        seen["strike"] = strike
        return 0.123

    monkeypatch.setattr(mod, "prob_lognormal_less", fake_prob)
    p = mod._model_p_yes(strike_type="less", strike=42.0, strike_high=None, spot=100.0, t_years=0.1, sigma_annual=0.5)
    assert p == 0.123

    monkeypatch.setattr(mod, "ref_spot_btc_usd", lambda: 100.0)

    m = KalshiMarket(
        ticker="TEST-LESS",
        series_ticker="KXBTC",
        event_ticker="KXBTC-TEST",
        title="Test",
        subtitle="100 or below",
        status="open",
        strike_type="less",
        floor_strike=None,
        cap_strike=100.0,
        expected_expiration_time="2099-01-01T00:00:00Z",
        yes_bid=0.49,
        yes_ask=0.50,
        no_bid=0.49,
        no_ask=0.50,
        liquidity_dollars=1000.0,
    )

    s = mod._signal_for_market(
        m,
        series="KXBTC",
        sigma_annual=0.5,
        min_edge_bps=-10_000.0,
        uncertainty_bps=0.0,
        min_liquidity_usd=0.0,
        max_spread=1.0,
        min_seconds_to_expiry=0,
        min_price=0.0,
        max_price=1.0,
        min_notional_usd=0.0,
        min_notional_bypass_edge_bps=0.0,
    )
    assert s is not None
    assert s.strike_type == "less"
    assert s.strike == 100.0
    assert s.strike_high is None
    assert 0.0 <= s.p_yes <= 1.0
