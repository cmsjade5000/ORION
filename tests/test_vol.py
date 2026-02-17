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

    def test_conservative_sigma_auto_routes_by_series(self) -> None:
        # Pure unit test: avoid network by monkeypatching per-asset realized vol functions.
        import scripts.arb.vol as vol

        orig_btc = vol.realized_vol_btc_usd_annual
        orig_eth = vol.realized_vol_eth_usd_annual
        orig_xrp = getattr(vol, "realized_vol_xrp_usd_annual", None)
        orig_doge = getattr(vol, "realized_vol_doge_usd_annual", None)

        try:
            vol.realized_vol_btc_usd_annual = lambda window_hours=0: [vol.RealizedVol("t", "BTC", int(window_hours), 0.5)]  # type: ignore[assignment]
            vol.realized_vol_eth_usd_annual = lambda window_hours=0: [vol.RealizedVol("t", "ETH", int(window_hours), 0.6)]  # type: ignore[assignment]
            vol.realized_vol_xrp_usd_annual = lambda window_hours=0: [vol.RealizedVol("t", "XRP", int(window_hours), 0.7)]  # type: ignore[attr-defined]
            vol.realized_vol_doge_usd_annual = lambda window_hours=0: [vol.RealizedVol("t", "DOGE", int(window_hours), 0.8)]  # type: ignore[attr-defined]

            self.assertAlmostEqual(vol.conservative_sigma_auto("KXBTC", window_hours=10) or 0.0, 0.5, places=6)
            self.assertAlmostEqual(vol.conservative_sigma_auto("KXETH", window_hours=10) or 0.0, 0.6, places=6)
            self.assertAlmostEqual(vol.conservative_sigma_auto("KXXRP", window_hours=10) or 0.0, 0.7, places=6)
            self.assertAlmostEqual(vol.conservative_sigma_auto("KXDOGE", window_hours=10) or 0.0, 0.8, places=6)
        finally:
            vol.realized_vol_btc_usd_annual = orig_btc  # type: ignore[assignment]
            vol.realized_vol_eth_usd_annual = orig_eth  # type: ignore[assignment]
            if orig_xrp is not None:
                vol.realized_vol_xrp_usd_annual = orig_xrp  # type: ignore[attr-defined]
            if orig_doge is not None:
                vol.realized_vol_doge_usd_annual = orig_doge  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
