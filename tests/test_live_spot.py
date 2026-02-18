from __future__ import annotations

import unittest


class TestLiveSpot(unittest.TestCase):
    def test_series_mapping(self) -> None:
        from scripts.arb.live_spot import _series_to_coinbase_product

        self.assertEqual(_series_to_coinbase_product("KXBTC"), "BTC-USD")
        self.assertEqual(_series_to_coinbase_product("KXETH"), "ETH-USD")
        self.assertEqual(_series_to_coinbase_product("KXXRP"), "XRP-USD")
        self.assertEqual(_series_to_coinbase_product("KXDOGE"), "DOGE-USD")
        self.assertIsNone(_series_to_coinbase_product("KXSOL"))


if __name__ == "__main__":
    unittest.main()

