from __future__ import annotations

import math
import unittest


class TestVol(unittest.TestCase):
    def test_realized_vol_zero_for_constant_series(self) -> None:
        from scripts.arb.vol import realized_vol_annual_from_prices

        prices = [100.0] * 50
        v = realized_vol_annual_from_prices(prices, dt_seconds=3600)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertAlmostEqual(v, 0.0, places=12)

    def test_realized_vol_increases_with_noise(self) -> None:
        from scripts.arb.vol import realized_vol_annual_from_prices

        # Alternate +1% / -1% moves.
        prices = [100.0]
        for i in range(1, 200):
            prices.append(prices[-1] * (1.01 if i % 2 == 0 else 0.99))
        v = realized_vol_annual_from_prices(prices, dt_seconds=3600)
        self.assertIsNotNone(v)
        assert v is not None
        self.assertGreater(v, 0.0)
        self.assertTrue(math.isfinite(v))


if __name__ == "__main__":
    unittest.main()

