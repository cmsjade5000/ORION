from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .http import HttpClient, HttpConfig, safe_float


@dataclass(frozen=True)
class KalshiMarket:
    ticker: str
    series_ticker: str
    event_ticker: str
    title: str
    subtitle: str
    status: str
    strike_type: str
    floor_strike: Optional[float]
    expected_expiration_time: str
    yes_bid: Optional[float]
    yes_ask: Optional[float]
    no_bid: Optional[float]
    no_ask: Optional[float]
    liquidity_dollars: Optional[float]


@dataclass(frozen=True)
class KalshiOrder:
    ticker: str
    side: str  # "yes" or "no"
    action: str  # "buy" only in our initial scope
    count: int
    price_dollars: str  # "0.xxxx"
    client_order_id: str


class KalshiClient:
    """Kalshi Trade API v2 client.

    - Supports public market-data endpoints without auth.
    - Supports authenticated endpoints using RSA-PSS signature via `openssl`.

    Auth inputs are sourced from env by default:
    - KALSHI_API_KEY_ID
    - KALSHI_PRIVATE_KEY_PATH
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.elections.kalshi.com",
        http_cfg: Optional[HttpConfig] = None,
        api_key_id: str = "",
        private_key_path: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.http = HttpClient(http_cfg or HttpConfig(user_agent="orion-kalshi-arb/0.1", timeout_seconds=20.0))
        self.api_key_id = api_key_id or os.environ.get("KALSHI_API_KEY_ID", "")
        self.private_key_path = private_key_path or os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")

    def list_markets(
        self,
        *,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[KalshiMarket]:
        params: Dict[str, Any] = {"limit": str(int(limit))}
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if tickers:
            params["tickers"] = ",".join(tickers)

        obj = self.http.get_json(f"{self.base_url}/trade-api/v2/markets", params=params)
        items = obj.get("markets") if isinstance(obj, dict) else None
        if not isinstance(items, list):
            return []
        out: List[KalshiMarket] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            m = _parse_market(raw)
            if m is not None:
                out.append(m)
        return out

    def get_market(self, ticker: str) -> Optional[KalshiMarket]:
        obj = self.http.get_json(f"{self.base_url}/trade-api/v2/markets/{ticker}")
        raw = obj.get("market") if isinstance(obj, dict) else None
        if not isinstance(raw, dict):
            return None
        return _parse_market(raw)

    def create_order(self, order: KalshiOrder) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/orders"
        url = f"{self.base_url}{path}"
        cents = dollars_to_cents_int(order.price_dollars)
        if cents is None:
            raise RuntimeError(f"Invalid order price_dollars: {order.price_dollars!r}")
        body: Dict[str, Any] = {
            "ticker": order.ticker,
            "client_order_id": order.client_order_id,
            "action": order.action,
            "side": order.side,
            "count": int(order.count),
            "type": "limit",
            # Kalshi order endpoints accept cent-based prices; include these for compatibility.
            "yes_price": cents if order.side == "yes" else None,
            "no_price": cents if order.side == "no" else None,
            # Also include dollars fixed-point for readability where supported.
            "yes_price_dollars": order.price_dollars if order.side == "yes" else None,
            "no_price_dollars": order.price_dollars if order.side == "no" else None,
            # Conservative default: avoid leaving resting orders around if edge disappears.
            "time_in_force": "fill_or_kill",
        }
        # Remove nulls to match API expectations.
        body = {k: v for k, v in body.items() if v is not None}
        return self._post_json(url, path=path, body=body)

    def get_balance(self) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/balance"
        return self._get_json_authed(path, params=None)

    def get_positions(
        self,
        *,
        limit: int = 100,
        cursor: str = "",
        count_filter: str = "position",
        ticker: str = "",
        event_ticker: str = "",
        subaccount: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/positions"
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        if count_filter:
            params["count_filter"] = count_filter
        if ticker:
            params["ticker"] = ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if subaccount is not None:
            params["subaccount"] = int(subaccount)
        return self._get_json_authed(path, params=params)

    def get_orders(
        self,
        *,
        limit: int = 100,
        cursor: str = "",
        status: str = "",
        ticker: str = "",
        event_ticker: str = "",
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        subaccount: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/orders"
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if ticker:
            params["ticker"] = ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if min_ts is not None:
            params["min_ts"] = int(min_ts)
        if max_ts is not None:
            params["max_ts"] = int(max_ts)
        if subaccount is not None:
            params["subaccount"] = int(subaccount)
        return self._get_json_authed(path, params=params)

    def get_fills(
        self,
        *,
        limit: int = 100,
        cursor: str = "",
        ticker: str = "",
        order_id: str = "",
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        subaccount: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/fills"
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker
        if order_id:
            params["order_id"] = order_id
        if min_ts is not None:
            params["min_ts"] = int(min_ts)
        if max_ts is not None:
            params["max_ts"] = int(max_ts)
        if subaccount is not None:
            params["subaccount"] = int(subaccount)
        return self._get_json_authed(path, params=params)

    def get_settlements(
        self,
        *,
        limit: int = 100,
        cursor: str = "",
        ticker: str = "",
        event_ticker: str = "",
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        subaccount: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._require_auth()
        path = "/trade-api/v2/portfolio/settlements"
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if min_ts is not None:
            params["min_ts"] = int(min_ts)
        if max_ts is not None:
            params["max_ts"] = int(max_ts)
        if subaccount is not None:
            params["subaccount"] = int(subaccount)
        return self._get_json_authed(path, params=params)

    def _get_json_authed(self, path: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        hdrs = self._auth_headers(method="GET", path=path)
        url = f"{self.base_url}{path}"
        return self.http.get_json(url, headers=hdrs, params=params)

    def _post_json(self, url: str, *, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        hdrs = self._auth_headers(method="POST", path=path)
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={**hdrs, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Kalshi POST failed: {path} ({e})")

    def _auth_headers(self, *, method: str, path: str) -> Dict[str, str]:
        # Per Kalshi docs:
        # - timestamp is unix ms
        # - sign message = timestamp + method + path, with query stripped from path before signing
        # - signature is base64(RSA-PSS-SHA256(private_key, message))
        ts_ms = str(int(time.time() * 1000))
        method_u = method.upper()
        path_no_q = urllib.parse.urlsplit(path).path
        msg = f"{ts_ms}{method_u}{path_no_q}".encode("utf-8")
        sig = _rsa_pss_sha256_sign_base64(msg, self.private_key_path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts_ms,
        }

    def _require_auth(self) -> None:
        if not self.api_key_id or not self.private_key_path:
            raise RuntimeError("Missing KALSHI_API_KEY_ID or KALSHI_PRIVATE_KEY_PATH.")
        if not os.path.exists(self.private_key_path):
            raise RuntimeError(f"Private key not found: {self.private_key_path}")


def _rsa_pss_sha256_sign_base64(message: bytes, private_key_path: str) -> str:
    # Use openssl to avoid adding python crypto deps to the Gateway env.
    # We sign SHA-256(message) using RSA-PSS (saltlen = digest length).
    with tempfile.TemporaryDirectory() as td:
        msg_path = os.path.join(td, "msg.bin")
        sig_path = os.path.join(td, "sig.bin")
        with open(msg_path, "wb") as f:
            f.write(message)

        # `pkeyutl -sign` operates on raw inputs; when configured with a digest it expects a
        # digest-length input. Using `dgst -sha256` is the most reliable way to get RSA-PSS.
        cmd = [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            private_key_path,
            "-sigopt",
            "rsa_padding_mode:pss",
            "-sigopt",
            "rsa_pss_saltlen:-1",
            "-sigopt",
            "rsa_mgf1_md:sha256",
            "-out",
            sig_path,
            msg_path,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"openssl signing failed: {err}")

        sig = open(sig_path, "rb").read()
        return base64.b64encode(sig).decode("ascii")


def _parse_market(raw: Dict[str, Any]) -> Optional[KalshiMarket]:
    ticker = str(raw.get("ticker") or "")
    if not ticker:
        return None
    return KalshiMarket(
        ticker=ticker,
        series_ticker=str(raw.get("series_ticker") or ""),
        event_ticker=str(raw.get("event_ticker") or ""),
        title=str(raw.get("title") or ""),
        subtitle=str(raw.get("subtitle") or raw.get("sub_title") or ""),
        status=str(raw.get("status") or ""),
        strike_type=str(raw.get("strike_type") or ""),
        floor_strike=safe_float(raw.get("floor_strike")),
        expected_expiration_time=str(raw.get("expected_expiration_time") or ""),
        yes_bid=safe_float(raw.get("yes_bid_dollars")),
        yes_ask=safe_float(raw.get("yes_ask_dollars")),
        no_bid=safe_float(raw.get("no_bid_dollars")),
        no_ask=safe_float(raw.get("no_ask_dollars")),
        liquidity_dollars=safe_float(raw.get("liquidity_dollars")),
    )


def dollars_to_cents_int(price_dollars: str) -> Optional[int]:
    try:
        x = float(price_dollars)
    except Exception:
        return None
    # Kalshi prices are typically quoted in cents in [1, 99] for limit orders.
    cents = int(round(x * 100.0))
    if cents < 0 or cents > 100:
        return None
    return cents
