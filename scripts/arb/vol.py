from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from .http import HttpClient, HttpConfig, safe_float


def realized_vol_annual_from_prices(prices: List[float], *, dt_seconds: int) -> Optional[float]:
    """Annualized realized vol from close prices using log returns.

    - prices must be in chronological order.
    - dt_seconds is the sampling interval between points (e.g. 3600 for hourly).
    """
    if not prices or len(prices) < 10:
        return None
    rets: List[float] = []
    for i in range(1, len(prices)):
        p0 = float(prices[i - 1])
        p1 = float(prices[i])
        if p0 <= 0.0 or p1 <= 0.0:
            continue
        rets.append(math.log(p1 / p0))
    if len(rets) < 10:
        return None
    mu = sum(rets) / float(len(rets))
    var = sum((r - mu) ** 2 for r in rets) / float(max(1, len(rets) - 1))
    if var < 0.0:
        return None
    vol_per_step = math.sqrt(var)
    steps_per_year = (365.0 * 24.0 * 3600.0) / float(dt_seconds)
    return float(vol_per_step * math.sqrt(steps_per_year))


@dataclass(frozen=True)
class RealizedVol:
    venue: str
    symbol: str
    window_hours: int
    vol_annual: float


class CoinbasePublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig(timeout_seconds=10.0))

    def hourly_closes(self, product: str, *, window_hours: int = 24 * 7) -> Optional[List[float]]:
        # Coinbase Exchange candles: [time, low, high, open, close, volume]
        url = f"https://api.exchange.coinbase.com/products/{product}/candles"
        end = int(time.time())
        start = end - int(window_hours) * 3600
        obj = self.http.get_json(url, params={"start": start, "end": end, "granularity": 3600})
        if not isinstance(obj, list):
            return None
        rows = []
        for r in obj:
            if not isinstance(r, list) or len(r) < 5:
                continue
            ts = safe_float(r[0])
            close = safe_float(r[4])
            if ts is None or close is None:
                continue
            rows.append((int(ts), float(close)))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        return [c for _, c in rows]


class KrakenPublic:
    def __init__(self, http_cfg: Optional[HttpConfig] = None):
        self.http = HttpClient(http_cfg or HttpConfig(timeout_seconds=10.0))

    def hourly_closes(self, pair: str, *, window_hours: int = 24 * 7) -> Optional[List[float]]:
        url = "https://api.kraken.com/0/public/OHLC"
        since = int(time.time()) - int(window_hours) * 3600
        obj = self.http.get_json(url, params={"pair": pair, "interval": 60, "since": since})
        if not isinstance(obj, dict) or obj.get("error"):
            return None
        result = obj.get("result") or {}
        if not isinstance(result, dict) or not result:
            return None
        # result has one key for pair and another "last"
        key = None
        for k in result.keys():
            if k != "last":
                key = k
                break
        if key is None:
            return None
        rows_obj = result.get(key)
        if not isinstance(rows_obj, list):
            return None
        rows = []
        for r in rows_obj:
            # [time, open, high, low, close, vwap, volume, count]
            if not isinstance(r, list) or len(r) < 5:
                continue
            ts = safe_float(r[0])
            close = safe_float(r[4])
            if ts is None or close is None:
                continue
            rows.append((int(ts), float(close)))
        if not rows:
            return None
        rows.sort(key=lambda x: x[0])
        return [c for _, c in rows]


def realized_vol_btc_usd_annual(*, window_hours: int = 24 * 7) -> List[RealizedVol]:
    out: List[RealizedVol] = []
    cb = CoinbasePublic()
    kr = KrakenPublic()
    cb_prices = cb.hourly_closes("BTC-USD", window_hours=window_hours)
    if cb_prices:
        v = realized_vol_annual_from_prices(cb_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="coinbase", symbol="BTC-USD", window_hours=int(window_hours), vol_annual=float(v)))
    kr_prices = kr.hourly_closes("XBTUSD", window_hours=window_hours)
    if kr_prices:
        v = realized_vol_annual_from_prices(kr_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="kraken", symbol="XBTUSD", window_hours=int(window_hours), vol_annual=float(v)))
    return out


def realized_vol_eth_usd_annual(*, window_hours: int = 24 * 7) -> List[RealizedVol]:
    out: List[RealizedVol] = []
    cb = CoinbasePublic()
    kr = KrakenPublic()
    cb_prices = cb.hourly_closes("ETH-USD", window_hours=window_hours)
    if cb_prices:
        v = realized_vol_annual_from_prices(cb_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="coinbase", symbol="ETH-USD", window_hours=int(window_hours), vol_annual=float(v)))
    kr_prices = kr.hourly_closes("ETHUSD", window_hours=window_hours)
    if kr_prices:
        v = realized_vol_annual_from_prices(kr_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="kraken", symbol="ETHUSD", window_hours=int(window_hours), vol_annual=float(v)))
    return out


def realized_vol_xrp_usd_annual(*, window_hours: int = 24 * 7) -> List[RealizedVol]:
    out: List[RealizedVol] = []
    cb = CoinbasePublic()
    kr = KrakenPublic()
    cb_prices = cb.hourly_closes("XRP-USD", window_hours=window_hours)
    if cb_prices:
        v = realized_vol_annual_from_prices(cb_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="coinbase", symbol="XRP-USD", window_hours=int(window_hours), vol_annual=float(v)))
    kr_prices = kr.hourly_closes("XRPUSD", window_hours=window_hours)
    if kr_prices:
        v = realized_vol_annual_from_prices(kr_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="kraken", symbol="XRPUSD", window_hours=int(window_hours), vol_annual=float(v)))
    return out


def realized_vol_doge_usd_annual(*, window_hours: int = 24 * 7) -> List[RealizedVol]:
    out: List[RealizedVol] = []
    cb = CoinbasePublic()
    kr = KrakenPublic()
    cb_prices = cb.hourly_closes("DOGE-USD", window_hours=window_hours)
    if cb_prices:
        v = realized_vol_annual_from_prices(cb_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="coinbase", symbol="DOGE-USD", window_hours=int(window_hours), vol_annual=float(v)))
    kr_prices = kr.hourly_closes("DOGEUSD", window_hours=window_hours)
    if kr_prices:
        v = realized_vol_annual_from_prices(kr_prices, dt_seconds=3600)
        if v is not None:
            out.append(RealizedVol(venue="kraken", symbol="DOGEUSD", window_hours=int(window_hours), vol_annual=float(v)))
    return out


def conservative_sigma_auto(series: str, *, window_hours: int = 24 * 7) -> Optional[float]:
    s = (series or "").upper()
    vols: List[RealizedVol] = []
    if "BTC" in s:
        vols = realized_vol_btc_usd_annual(window_hours=window_hours)
    elif "ETH" in s:
        vols = realized_vol_eth_usd_annual(window_hours=window_hours)
    elif "XRP" in s:
        vols = realized_vol_xrp_usd_annual(window_hours=window_hours)
    elif "DOGE" in s:
        vols = realized_vol_doge_usd_annual(window_hours=window_hours)
    if not vols:
        return None
    # Conservative: take the maximum across venues.
    v = max(x.vol_annual for x in vols)
    # Clamp to sane bounds to avoid overreacting to bad data.
    return float(min(2.0, max(0.20, v)))
