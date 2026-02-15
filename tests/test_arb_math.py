import unittest

from scripts.arb.arb import calc_internal_buy_both_arb


class TestArbMath(unittest.TestCase):
    def test_internal_arb_positive_edge(self):
        ok, edge_bps, profit = calc_internal_buy_both_arb(
            ask_a=0.45,
            ask_b=0.45,
            fee_bps=0.0,
            min_edge_bps=10.0,
        )
        self.assertTrue(ok)
        self.assertGreater(edge_bps, 0.0)
        self.assertGreater(profit, 0.0)

    def test_internal_arb_no_edge(self):
        ok, edge_bps, profit = calc_internal_buy_both_arb(
            ask_a=0.51,
            ask_b=0.50,
            fee_bps=0.0,
            min_edge_bps=1.0,
        )
        self.assertFalse(ok)
        self.assertLessEqual(edge_bps, 0.0)
        self.assertLessEqual(profit, 0.0)

    def test_internal_arb_fee_can_flip(self):
        ok, edge_bps, profit = calc_internal_buy_both_arb(
            ask_a=0.49,
            ask_b=0.49,
            fee_bps=500.0,  # 5%
            min_edge_bps=1.0,
        )
        self.assertFalse(ok)
        self.assertLessEqual(edge_bps, 0.0)
        self.assertLessEqual(profit, 0.0)


if __name__ == "__main__":
    unittest.main()

