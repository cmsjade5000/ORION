from __future__ import annotations

import unittest
from unittest.mock import patch


class TestExchangeRefFeeds(unittest.TestCase):
    def test_parse_ref_feeds_defaults_on_empty(self) -> None:
        from scripts.arb.exchanges import parse_ref_feeds

        self.assertEqual(parse_ref_feeds(""), ["coinbase", "kraken", "binance"])

    def test_ref_spot_snapshot_uses_selected_feeds(self) -> None:
        import scripts.arb.exchanges as ex

        with patch.object(ex.CoinbasePublic, "get_spot", return_value=ex.SpotQuote(symbol="BTC-USD", venue="coinbase", price=100.0)), patch.object(
            ex.KrakenPublic, "get_spot", return_value=ex.SpotQuote(symbol="XBTUSD", venue="kraken", price=101.0)
        ), patch.object(ex.BinancePublic, "get_spot", return_value=ex.SpotQuote(symbol="BTCUSDT", venue="binance", price=99.0)):
            snap = ex.ref_spot_snapshot("KXBTC", feeds=["coinbase", "kraken", "binance"])
        self.assertEqual(snap["median"], 100.0)
        self.assertIsInstance(snap["dispersion_bps"], float)
        self.assertEqual(len(snap["quotes"]), 3)

    def test_latest_binance_funding_rate_bps(self) -> None:
        import scripts.arb.exchanges as ex

        with patch.object(ex.BinancePublic, "get_latest_funding_rate", return_value=0.0002):
            v = ex.latest_binance_funding_rate_bps("KXBTC")
        self.assertAlmostEqual(float(v), 2.0, places=9)


if __name__ == "__main__":
    unittest.main()

