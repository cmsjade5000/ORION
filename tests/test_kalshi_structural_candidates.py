from __future__ import annotations

import unittest
from types import SimpleNamespace


def _sig(mod, *, ticker: str, strike: float, t_years: float, exp: str, strike_type: str, yes_ask: float, no_ask: float):
    return mod.Signal(
        ticker=ticker,
        strike_type=strike_type,
        strike=float(strike),
        expected_expiration_time=exp,
        spot_ref=100.0,
        t_years=float(t_years),
        sigma_annual=0.85,
        p_yes=0.5,
        yes_bid=max(0.0, float(yes_ask) - 0.01),
        yes_ask=float(yes_ask),
        no_bid=max(0.0, float(no_ask) - 0.01),
        no_ask=float(no_ask),
        edge_bps_buy_yes=100.0,
        edge_bps_buy_no=100.0,
        recommended=None,
        filters={
            "liquidity_dollars": 1000.0,
            "yes_spread": 0.01,
            "no_spread": 0.01,
        },
        rejected_reasons=[],
    )


class TestKalshiStructuralCandidates(unittest.TestCase):
    def test_builds_strike_mono_pair_candidate(self) -> None:
        import scripts.kalshi_ref_arb as mod

        args = SimpleNamespace(
            min_price=0.01,
            max_price=0.99,
            min_seconds_to_expiry=60,
            max_spread=0.05,
            series="KXBTC",
        )
        rt = SimpleNamespace(struct_min_edge_bps=220.0, struct_min_liquidity_usd=25.0)
        s_lo = _sig(mod, ticker="A-100", strike=100.0, t_years=0.01, exp="2026-03-10T22:00:00Z", strike_type="greater", yes_ask=0.40, no_ask=0.60)
        s_hi = _sig(mod, ticker="A-110", strike=110.0, t_years=0.01, exp="2026-03-10T22:00:00Z", strike_type="greater", yes_ask=0.30, no_ask=0.45)
        out = mod._build_structural_candidates(series="KXBTC", all_signals=[s_lo, s_hi], args=args, rt_cfg=rt)
        self.assertTrue(any(str(c.get("module")) == "strike_monotonicity" for c in out))
        pair = [c for c in out if str(c.get("module")) == "strike_monotonicity"][0]
        self.assertEqual(str(pair.get("kind")), "pair")
        self.assertGreater(float(pair.get("expected_profit_bps") or 0.0), 0.0)

    def test_touch_ladder_module_selected_for_maxmon_series(self) -> None:
        import scripts.kalshi_ref_arb as mod

        args = SimpleNamespace(min_price=0.01, max_price=0.99, min_seconds_to_expiry=60, max_spread=0.05, series="KXBTCMAXMON")
        rt = SimpleNamespace(struct_min_edge_bps=220.0, struct_min_liquidity_usd=25.0)
        s_lo = _sig(mod, ticker="B-85000", strike=85000.0, t_years=0.05, exp="2026-04-08T03:59:59Z", strike_type="greater", yes_ask=0.50, no_ask=0.50)
        s_hi = _sig(mod, ticker="B-90000", strike=90000.0, t_years=0.05, exp="2026-04-08T03:59:59Z", strike_type="greater", yes_ask=0.40, no_ask=0.42)
        out = mod._build_structural_candidates(series="KXBTCMAXMON", all_signals=[s_lo, s_hi], args=args, rt_cfg=rt)
        self.assertTrue(any(str(c.get("module")) == "touch_ladder" for c in out))

    def test_builds_time_monotonic_single_candidate(self) -> None:
        import scripts.kalshi_ref_arb as mod

        args = SimpleNamespace(min_price=0.01, max_price=0.99, min_seconds_to_expiry=60, max_spread=0.05, series="KXBTCD")
        rt = SimpleNamespace(struct_min_edge_bps=220.0, struct_min_liquidity_usd=25.0)
        near = _sig(mod, ticker="C-near", strike=70000.0, t_years=0.005, exp="2026-03-05T22:00:00Z", strike_type="greater", yes_ask=0.70, no_ask=0.30)
        far = _sig(mod, ticker="C-far", strike=70000.0, t_years=0.02, exp="2026-03-10T22:00:00Z", strike_type="greater", yes_ask=0.60, no_ask=0.40)
        out = mod._build_structural_candidates(series="KXBTCD", all_signals=[near, far], args=args, rt_cfg=rt)
        self.assertTrue(any(str(c.get("module")) == "time_monotonicity" for c in out))


if __name__ == "__main__":
    unittest.main()

