from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .http import HttpClient, HttpConfig, safe_float


@dataclass(frozen=True)
class SpotQuote:
    symbol: str
    venue: str
    price: float


class CoinbasePublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig())

    def get_spot(self, product: str) -> Optional[SpotQuote]:
        # Coinbase Exchange (aka "advanced trade") public ticker.
        # Example product: BTC-USD, ETH-USD
        url = f"https://api.exchange.coinbase.com/products/{product}/ticker"
        obj = self.http.get_json(url)
        price = safe_float(obj.get("price") if isinstance(obj, dict) else None)
        if price is None:
            return None
        return SpotQuote(symbol=product, venue="coinbase", price=price)


class KrakenPublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig())

    def get_spot(self, pair: str) -> Optional[SpotQuote]:
        # Example pair: XBTUSD, ETHUSD
        url = "https://api.kraken.com/0/public/Ticker"
        obj = self.http.get_json(url, params={"pair": pair})
        if not isinstance(obj, dict) or obj.get("error"):
            return None
        result = obj.get("result") or {}
        if not isinstance(result, dict) or not result:
            return None
        # Kraken returns a dict keyed by pair name (may be normalized, e.g., XXBTZUSD)
        first_key = next(iter(result.keys()))
        data = result.get(first_key) or {}
        if not isinstance(data, dict):
            return None
        # "c" = last trade closed [price, lot volume]
        c = data.get("c") or []
        price = safe_float(c[0] if isinstance(c, list) and c else None)
        if price is None:
            return None
        return SpotQuote(symbol=pair, venue="kraken", price=price)


class BitstampPublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig())

    def get_spot(self, pair: str) -> Optional[SpotQuote]:
        # Example pair: btcusd, ethusd, xrpusd, dogeusd
        url = f"https://www.bitstamp.net/api/v2/ticker/{pair}/"
        obj = self.http.get_json(url)
        price = safe_float(obj.get("last") if isinstance(obj, dict) else None)
        if price is None:
            return None
        return SpotQuote(symbol=pair, venue="bitstamp", price=price)


def _ref_spot_median(*, cb_product: str, kr_pair: str) -> Optional[float]:
    cb = CoinbasePublic()
    kr = KrakenPublic()
    bs = BitstampPublic()
    q1 = cb.get_spot(cb_product)
    q2 = kr.get_spot(kr_pair)
    # Bitstamp pair format is lowercase with no separators.
    bs_pair = cb_product.replace("-", "").lower()  # BTC-USD -> btcusd
    q3 = bs.get_spot(bs_pair)

    prices = [q.price for q in [q1, q2, q3] if q is not None]
    if not prices:
        return None
    prices.sort()
    # Median (robust to one outlier if we extend to more venues later).
    return prices[len(prices) // 2]


def ref_spot_btc_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="BTC-USD", kr_pair="XBTUSD")


def ref_spot_eth_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="ETH-USD", kr_pair="ETHUSD")


def ref_spot_xrp_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="XRP-USD", kr_pair="XRPUSD")


def ref_spot_doge_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="DOGE-USD", kr_pair="DOGEUSD")
