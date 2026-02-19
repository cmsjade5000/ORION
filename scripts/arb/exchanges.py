from __future__ import annotations

import datetime as _dt
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .http import HttpClient, HttpConfig, safe_float


@dataclass(frozen=True)
class SpotQuote:
    symbol: str
    venue: str
    price: float
    observed_ts_unix: Optional[int] = None
    quote_ts_unix: Optional[int] = None
    quote_age_sec: Optional[float] = None


def _parse_iso_ts_to_unix(x: Any) -> Optional[int]:
    if not isinstance(x, str) or not x.strip():
        return None
    s = str(x).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


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
        now = int(time.time())
        qts = _parse_iso_ts_to_unix(obj.get("time") if isinstance(obj, dict) else None)
        age = float(max(0.0, now - int(qts))) if isinstance(qts, int) else None
        return SpotQuote(symbol=product, venue="coinbase", price=price, observed_ts_unix=now, quote_ts_unix=qts, quote_age_sec=age)


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
        now = int(time.time())
        return SpotQuote(symbol=pair, venue="kraken", price=price, observed_ts_unix=now)


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
        now = int(time.time())
        return SpotQuote(symbol=pair, venue="bitstamp", price=price, observed_ts_unix=now)


class BinancePublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig())

    def get_spot(self, symbol: str) -> Optional[SpotQuote]:
        # Example symbol: BTCUSDT, ETHUSDT, XRPUSDT, DOGEUSDT
        url = "https://api.binance.com/api/v3/ticker/price"
        obj = self.http.get_json(url, params={"symbol": str(symbol)})
        price = safe_float(obj.get("price") if isinstance(obj, dict) else None)
        if price is None:
            return None
        now = int(time.time())
        return SpotQuote(symbol=str(symbol), venue="binance", price=price, observed_ts_unix=now)

    def get_latest_funding_rate(self, symbol: str) -> Optional[float]:
        # USD-M futures funding rate; read-only signal source.
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        obj = self.http.get_json(url, params={"symbol": str(symbol), "limit": 1})
        if not isinstance(obj, list) or not obj:
            return None
        row = obj[-1]
        if not isinstance(row, dict):
            return None
        # Binance fundingRate is decimal (e.g. 0.0001 = 1 bp).
        fr = safe_float(row.get("fundingRate"))
        if fr is None:
            return None
        return float(fr)


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


def parse_ref_feeds(raw: str) -> List[str]:
    allowed = {"coinbase", "kraken", "bitstamp", "binance"}
    out: List[str] = []
    seen: set[str] = set()
    for chunk in str(raw or "").replace(";", ",").split(","):
        v = chunk.strip().lower()
        if not v or v not in allowed or v in seen:
            continue
        seen.add(v)
        out.append(v)
    if not out:
        return ["coinbase", "kraken", "binance"]
    return out


def _series_symbols(series: str) -> tuple[str, str, str, str]:
    s = str(series or "").upper()
    if "BTC" in s:
        return ("BTC-USD", "XBTUSD", "btcusd", "BTCUSDT")
    if "ETH" in s:
        return ("ETH-USD", "ETHUSD", "ethusd", "ETHUSDT")
    if "XRP" in s:
        return ("XRP-USD", "XRPUSD", "xrpusd", "XRPUSDT")
    if "DOGE" in s:
        return ("DOGE-USD", "DOGEUSD", "dogeusd", "DOGEUSDT")
    # Fallback to BTC symbols for unknown series.
    return ("BTC-USD", "XBTUSD", "btcusd", "BTCUSDT")


def ref_spot_snapshot(series: str, *, feeds: Optional[List[str]] = None) -> Dict[str, Any]:
    use = feeds or ["coinbase", "kraken", "binance"]
    cb_product, kr_pair, bs_pair, bn_symbol = _series_symbols(series)
    quotes: List[SpotQuote] = []
    for f in use:
        try:
            if f == "coinbase":
                q = CoinbasePublic().get_spot(cb_product)
            elif f == "kraken":
                q = KrakenPublic().get_spot(kr_pair)
            elif f == "bitstamp":
                q = BitstampPublic().get_spot(bs_pair)
            elif f == "binance":
                q = BinancePublic().get_spot(bn_symbol)
            else:
                q = None
            if q is not None:
                quotes.append(q)
        except Exception:
            continue
    prices = [float(q.price) for q in quotes]
    median = None
    dispersion_bps = None
    max_quote_age_sec = None
    quote_ages = [float(q.quote_age_sec) for q in quotes if isinstance(q.quote_age_sec, (int, float))]
    if quote_ages:
        max_quote_age_sec = max(quote_ages)
    if prices:
        prices_sorted = sorted(prices)
        median = prices_sorted[len(prices_sorted) // 2]
        if median and median > 0 and len(prices_sorted) >= 2:
            lo = prices_sorted[0]
            hi = prices_sorted[-1]
            dispersion_bps = ((hi - lo) / median) * 10_000.0
    now = int(time.time())
    return {
        "series": str(series),
        "feeds": list(use),
        "quotes": [
            {
                "venue": q.venue,
                "symbol": q.symbol,
                "price": float(q.price),
                "observed_ts_unix": int(q.observed_ts_unix) if isinstance(q.observed_ts_unix, int) else None,
                "quote_ts_unix": int(q.quote_ts_unix) if isinstance(q.quote_ts_unix, int) else None,
                "quote_age_sec": float(q.quote_age_sec) if isinstance(q.quote_age_sec, (int, float)) else None,
                "observed_age_sec": float(max(0.0, now - int(q.observed_ts_unix))) if isinstance(q.observed_ts_unix, int) else None,
            }
            for q in quotes
        ],
        "median": float(median) if isinstance(median, (int, float)) else None,
        "dispersion_bps": float(dispersion_bps) if isinstance(dispersion_bps, (int, float)) else None,
        "max_quote_age_sec": float(max_quote_age_sec) if isinstance(max_quote_age_sec, (int, float)) else None,
    }


def latest_binance_funding_rate_bps(series: str) -> Optional[float]:
    _, _, _, bn_symbol = _series_symbols(series)
    fr = BinancePublic().get_latest_funding_rate(bn_symbol)
    if fr is None:
        return None
    return float(fr) * 10_000.0


def ref_spot_btc_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="BTC-USD", kr_pair="XBTUSD")


def ref_spot_eth_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="ETH-USD", kr_pair="ETHUSD")


def ref_spot_xrp_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="XRP-USD", kr_pair="XRPUSD")


def ref_spot_doge_usd() -> Optional[float]:
    return _ref_spot_median(cb_product="DOGE-USD", kr_pair="DOGEUSD")
