import unittest

from scripts.arb.prob import prob_lognormal_greater


class TestProbModel(unittest.TestCase):
    def test_prob_monotonic_spot(self):
        # For fixed strike/time/vol, higher spot => higher prob of finishing above strike.
        p1 = prob_lognormal_greater(spot=90, strike=100, t_years=1 / 365, sigma_annual=0.8)
        p2 = prob_lognormal_greater(spot=110, strike=100, t_years=1 / 365, sigma_annual=0.8)
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        self.assertLess(p1, p2)

    def test_prob_limits(self):
        # Near-zero vol => step function at spot vs strike.
        p = prob_lognormal_greater(spot=101, strike=100, t_years=0.5, sigma_annual=0.0)
        self.assertEqual(p, 1.0)
        p = prob_lognormal_greater(spot=99, strike=100, t_years=0.5, sigma_annual=0.0)
        self.assertEqual(p, 0.0)


if __name__ == "__main__":
    unittest.main()

