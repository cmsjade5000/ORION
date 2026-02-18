from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .http import HttpClient, HttpConfig


@dataclass(frozen=True)
class PolymarketUSConfig:
    # Public market data is served from the Gateway base URL.
    gateway_base_url: str = "https://gateway.polymarket.us"
    # Authenticated trading + portfolio endpoints are served from the API base URL.
    api_base_url: str = "https://api.polymarket.us"
    # WebSocket endpoints (not used by this module yet, but tracked for config completeness).
    ws_private_url: str = "wss://api.polymarket.us/v1/ws/private"
    ws_markets_url: str = "wss://api.polymarket.us/v1/ws/markets"


class PolymarketUSClient:
    """Polymarket US Retail API client (REST).

    Design goals:
    - Safe by default: market-data endpoints work without credentials.
    - Auth endpoints require Ed25519 request signing via `openssl` (no extra pip deps).

    Credential env vars:
    - POLY_US_API_KEY_ID: UUID
    - POLY_US_SECRET_KEY_B64: base64 string; first 32 bytes are Ed25519 seed (per docs)

    Optional:
    - POLY_US_PRIVATE_KEY_PATH: PKCS#8 PEM for Ed25519 (if you prefer file-based secrets).
      If not set, the client will derive a temp PKCS#8 PEM from POLY_US_SECRET_KEY_B64.
    """

    def __init__(
        self,
        *,
        cfg: Optional[PolymarketUSConfig] = None,
        http_cfg: Optional[HttpConfig] = None,
        api_key_id: str = "",
        secret_key_b64: str = "",
        private_key_path: str = "",
    ):
        self.cfg = cfg or PolymarketUSConfig()
        self.http = HttpClient(http_cfg or HttpConfig(user_agent="orion-polymarket-us/0.1", timeout_seconds=20.0))
        self.api_key_id = api_key_id or os.environ.get("POLY_US_API_KEY_ID", "")
        self.secret_key_b64 = secret_key_b64 or os.environ.get("POLY_US_SECRET_KEY_B64", "")
        self.private_key_path = private_key_path or os.environ.get("POLY_US_PRIVATE_KEY_PATH", "")

        self.gateway_base_url = str(self.cfg.gateway_base_url).rstrip("/")
        self.api_base_url = str(self.cfg.api_base_url).rstrip("/")

    # ----------------------------
    # Public market data (Gateway)
    # ----------------------------

    def get_markets(self, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.gateway_base_url}/v1/markets"
        obj = self.http.get_json(url, params=params)
        return obj if isinstance(obj, dict) else {"raw": obj}

    def get_market_by_slug(self, slug: str) -> Dict[str, Any]:
        # Endpoint per docs: GET /v1/market/{slug}
        path = f"/v1/market/{urllib.parse.quote(str(slug))}"
        url = f"{self.gateway_base_url}{path}"
        obj = self.http.get_json(url)
        return obj if isinstance(obj, dict) else {"raw": obj}

    def get_market_book(self, slug: str) -> Dict[str, Any]:
        # Endpoint per docs: GET /v1/markets/{slug}/book
        return self.get_market_book_side(slug, market_side_id="")

    def get_market_book_side(self, slug: str, *, market_side_id: str) -> Dict[str, Any]:
        # Some markets require specifying a marketSideId to get bids/offers for each outcome.
        path = f"/v1/markets/{urllib.parse.quote(str(slug))}/book"
        url = f"{self.gateway_base_url}{path}"
        params = {"marketSideId": market_side_id} if market_side_id else None
        obj = self.http.get_json(url, params=params)
        return obj if isinstance(obj, dict) else {"raw": obj}

    def get_market_bbo(self, slug: str) -> Dict[str, Any]:
        # Endpoint per docs: GET /v1/markets/{slug}/bbo
        path = f"/v1/markets/{urllib.parse.quote(str(slug))}/bbo"
        url = f"{self.gateway_base_url}{path}"
        obj = self.http.get_json(url)
        return obj if isinstance(obj, dict) else {"raw": obj}

    # ----------------------------
    # Authenticated (API)
    # ----------------------------

    def get_account_balances(self) -> Dict[str, Any]:
        self._require_auth()
        return self._get_json_authed("/v1/account/balances")

    def get_portfolio_positions(self, *, cursor: str = "", limit: int = 100) -> Dict[str, Any]:
        self._require_auth()
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        return self._get_json_authed("/v1/portfolio/positions", params=params)

    def get_portfolio_activities(self, *, cursor: str = "", limit: int = 100, market_slug: str = "", types: str = "") -> Dict[str, Any]:
        self._require_auth()
        params: Dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = cursor
        if market_slug:
            params["marketSlug"] = str(market_slug)
        if types:
            params["types"] = str(types)
        return self._get_json_authed("/v1/portfolio/activities", params=params)

    def create_order(self, body: Dict[str, Any]) -> Dict[str, Any]:
        self._require_auth()
        return self._post_json_authed("/v1/orders", body=body)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        self._require_auth()
        return self._post_json_authed(f"/v1/order/{urllib.parse.quote(str(order_id))}/cancel", body={})

    def cancel_open_orders(self) -> Dict[str, Any]:
        self._require_auth()
        return self._post_json_authed("/v1/orders/open/cancel", body={})

    # ----------------------------
    # Internals
    # ----------------------------

    def _get_json_authed(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        hdrs = self._auth_headers(method="GET", path=path)
        url = f"{self.api_base_url}{path}"
        obj = self.http.get_json(url, params=params, headers=hdrs)
        return obj if isinstance(obj, dict) else {"raw": obj}

    def _post_json_authed(self, path: str, *, body: Dict[str, Any]) -> Dict[str, Any]:
        hdrs = self._auth_headers(method="POST", path=path)
        url = f"{self.api_base_url}{path}"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={**hdrs, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                raw = resp.read()
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else {"raw": obj}
        except urllib.error.HTTPError as e:
            try:
                b = e.read()
                detail = b.decode("utf-8", errors="replace").strip()
            except Exception:
                detail = ""
            if len(detail) > 1200:
                detail = detail[:1200] + "...(truncated)"
            extra = f" body={detail!r}" if detail else ""
            raise RuntimeError(f"PolymarketUS POST failed: {path} (HTTP {getattr(e, 'code', '?')}){extra}")
        except Exception as e:
            raise RuntimeError(f"PolymarketUS POST failed: {path} ({e})")

    def _auth_headers(self, *, method: str, path: str) -> Dict[str, str]:
        # Per Polymarket US docs:
        # - timestamp is unix ms
        # - sign message = timestamp + method + path
        # - signature is base64(Ed25519.sign(private_key, message))
        ts_ms = str(int(time.time() * 1000))
        method_u = str(method or "GET").upper()
        path_no_q = urllib.parse.urlsplit(path).path
        msg = f"{ts_ms}{method_u}{path_no_q}".encode("utf-8")
        sig = _ed25519_sign_base64(msg, secret_b64=self.secret_key_b64, private_key_path=self.private_key_path)
        return {
            "X-PM-Access-Key": self.api_key_id,
            "X-PM-Timestamp": ts_ms,
            "X-PM-Signature": sig,
        }

    def _require_auth(self) -> None:
        if not self.api_key_id:
            raise RuntimeError("Missing POLY_US_API_KEY_ID.")
        if self.private_key_path:
            if not os.path.exists(self.private_key_path):
                raise RuntimeError(f"Private key not found: {self.private_key_path}")
            return
        if not self.secret_key_b64:
            raise RuntimeError("Missing POLY_US_SECRET_KEY_B64 (or set POLY_US_PRIVATE_KEY_PATH).")


_ED25519_PKCS8_PREFIX = bytes.fromhex("302e020100300506032b657004220420")


def ed25519_pkcs8_pem_from_secret_b64(secret_b64: str) -> str:
    raw = base64.b64decode(str(secret_b64).strip())
    if len(raw) < 32:
        raise ValueError("secret_b64 is too short; expected at least 32 bytes.")
    seed = raw[:32]
    der = _ED25519_PKCS8_PREFIX + seed
    b64 = base64.b64encode(der).decode("ascii")
    # 64-char lines for PEM readability.
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"


def best_bid_ask_from_us_book(book: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    """Extract best bid/ask from a Polymarket US `/book` response.

    Shape observed:
      {"marketData": {"bids":[{"px":{"value":"0.95"}, "qty":"..."}], "offers":[...]}}
    """

    def _px(x: Any) -> Optional[float]:
        try:
            if not isinstance(x, dict):
                return None
            px = x.get("px")
            if isinstance(px, dict):
                v = px.get("value")
            else:
                v = x.get("price") or x.get("value")
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    md = book.get("marketData") if isinstance(book, dict) else None
    if not isinstance(md, dict):
        return (None, None)

    bids = md.get("bids") or []
    offers = md.get("offers") or []

    best_bid = None
    if isinstance(bids, list):
        for b in bids:
            p = _px(b)
            if p is None:
                continue
            best_bid = p if best_bid is None else max(best_bid, p)

    best_ask = None
    if isinstance(offers, list):
        for a in offers:
            p = _px(a)
            if p is None:
                continue
            best_ask = p if best_ask is None else min(best_ask, p)

    return (best_bid, best_ask)


def _ed25519_sign_base64(msg: bytes, *, secret_b64: str, private_key_path: str) -> str:
    if not msg:
        raise ValueError("empty message")

    # Prefer file-based key if provided.
    if private_key_path:
        key_path = private_key_path
        tmp_key = None
    else:
        pem = ed25519_pkcs8_pem_from_secret_b64(secret_b64)
        tf = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        tf.write(pem)
        tf.flush()
        tf.close()
        key_path = tf.name
        tmp_key = key_path

    mf = tempfile.NamedTemporaryFile("wb", delete=False)
    mf.write(msg)
    mf.flush()
    mf.close()
    msg_path = mf.name

    try:
        proc = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", key_path, "-in", msg_path],
            capture_output=True,
            check=False,
            timeout=10,
        )
        if int(proc.returncode) != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"openssl ed25519 sign failed: {err[:300]}")
        sig = proc.stdout or b""
        # Ed25519 signatures are 64 bytes.
        if len(sig) != 64:
            raise RuntimeError(f"unexpected signature length: {len(sig)}")
        return base64.b64encode(sig).decode("ascii")
    finally:
        for p in (msg_path, tmp_key):
            if not p:
                continue
            try:
                os.remove(p)
            except Exception:
                pass
