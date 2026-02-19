from __future__ import annotations

import unittest


class TestPolymarketSportsPaper(unittest.TestCase):
    def test_is_binary_sports_market(self) -> None:
        from scripts.sports_paper.core import is_binary_sports_market

        m = {
            "category": "sports",
            "active": True,
            "closed": False,
            "outcomes": ["Team A", "Team B"],
            "marketSides": [{"id": "1"}, {"id": "2"}],
        }
        self.assertTrue(is_binary_sports_market(m))
        self.assertFalse(is_binary_sports_market({"category": "politics"}))

    def test_detect_pair_arbs_yes_and_no(self) -> None:
        from scripts.sports_paper.core import BookTop, detect_pair_arbs

        top_a = BookTop(bid_px=0.55, bid_qty=100, ask_px=0.48, ask_qty=50)
        top_b = BookTop(bid_px=0.53, bid_qty=90, ask_px=0.49, ask_qty=45)
        out = detect_pair_arbs(top_a=top_a, top_b=top_b, yes_sum_max=0.98, no_sum_max=0.98)
        yes = out["yes"]
        self.assertTrue(bool(yes.get("ok")))
        self.assertLess(float(yes.get("sum_price") or 1.0), 0.98)
        no = out["no"]
        self.assertTrue(bool(no.get("ok")))

    def test_simulate_pair_fok_fill(self) -> None:
        from scripts.sports_paper.core import BookTop, simulate_pair_fok_fill

        top_a = BookTop(bid_px=0.60, bid_qty=100, ask_px=0.47, ask_qty=12)
        top_b = BookTop(bid_px=0.58, bid_qty=100, ask_px=0.49, ask_qty=10)
        out = simulate_pair_fok_fill(
            side_mode="yes",
            top_a=top_a,
            top_b=top_b,
            sum_max=0.98,
            max_risk_per_side_usd=20.0,
            remaining_run_notional_usd=100.0,
            max_shares_per_side=100,
            min_shares=1,
            slippage_bps=0.0,
            latency_ms=0,
        )
        self.assertTrue(bool(out.get("ok")))
        self.assertGreaterEqual(int(out.get("shares") or 0), 1)

    def test_simulate_pair_rejects_when_slippage_breaks_threshold(self) -> None:
        from scripts.sports_paper.core import BookTop, simulate_pair_fok_fill

        top_a = BookTop(bid_px=0.50, bid_qty=100, ask_px=0.49, ask_qty=10)
        top_b = BookTop(bid_px=0.50, bid_qty=100, ask_px=0.49, ask_qty=10)
        out = simulate_pair_fok_fill(
            side_mode="yes",
            top_a=top_a,
            top_b=top_b,
            sum_max=0.98,
            max_risk_per_side_usd=50.0,
            remaining_run_notional_usd=100.0,
            max_shares_per_side=100,
            min_shares=1,
            slippage_bps=10.0,
            latency_ms=0,
        )
        self.assertFalse(bool(out.get("ok")))
        self.assertEqual(str(out.get("reason")), "slippage_over_threshold")


if __name__ == "__main__":
    unittest.main()

