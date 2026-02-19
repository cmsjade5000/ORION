from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float = 15.0
    user_agent: str = "orion-arb-bot/0.1"
    max_retries: int = 2
    retry_backoff_seconds: float = 0.4


class HttpClient:
    def __init__(self, cfg: Optional[HttpConfig] = None):
        cfg0 = cfg or HttpConfig()
        # Runtime overrides for retry behavior (safe defaults when unset).
        try:
            ma = int(str(os.environ.get("KALSHI_ARB_RETRY_MAX_ATTEMPTS", "")).strip() or 0)
        except Exception:
            ma = 0
        if ma <= 0:
            ma = int(cfg0.max_retries) + 1
        try:
            base_ms = int(str(os.environ.get("KALSHI_ARB_RETRY_BASE_MS", "")).strip() or 0)
        except Exception:
            base_ms = 0
        if base_ms <= 0:
            base_ms = int(float(cfg0.retry_backoff_seconds) * 1000.0)
        retries = max(0, int(ma) - 1)
        self._cfg = HttpConfig(
            timeout_seconds=float(cfg0.timeout_seconds),
            user_agent=str(cfg0.user_agent),
            max_retries=int(retries),
            retry_backoff_seconds=max(0.05, float(base_ms) / 1000.0),
        )

    @staticmethod
    def _retry_delay_seconds(e: BaseException, *, attempt: int, base: float) -> float:
        # Honor Retry-After for HTTP 429/503 when present.
        if isinstance(e, urllib.error.HTTPError):
            try:
                ra = e.headers.get("Retry-After")
                if ra is not None:
                    return max(0.05, float(str(ra).strip()))
            except Exception:
                pass
        return max(0.05, float(base) * (2**int(attempt)))

    @staticmethod
    def _is_retryable(e: BaseException) -> bool:
        if isinstance(e, urllib.error.HTTPError):
            try:
                return int(e.code) in (429, 500, 502, 503, 504)
            except Exception:
                return False
        return isinstance(e, (urllib.error.URLError, TimeoutError))

    def get_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        final_url = self._build_url(url, params=params)
        hdrs = {"User-Agent": self._cfg.user_agent}
        if headers:
            hdrs.update(headers)

        last_err: Optional[BaseException] = None
        for attempt in range(self._cfg.max_retries + 1):
            try:
                req = urllib.request.Request(final_url, headers=hdrs, method="GET")
                with urllib.request.urlopen(req, timeout=self._cfg.timeout_seconds) as resp:
                    raw = resp.read()
                return json.loads(raw.decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last_err = e
                if not self._is_retryable(e):
                    break
                if attempt >= self._cfg.max_retries:
                    break
                time.sleep(self._retry_delay_seconds(e, attempt=attempt, base=self._cfg.retry_backoff_seconds))
        raise RuntimeError(f"HTTP GET failed: {final_url} ({last_err})")

    @staticmethod
    def _build_url(url: str, *, params: Optional[Dict[str, Any]] = None) -> str:
        if not params:
            return url
        # Preserve any existing query.
        parsed = urllib.parse.urlsplit(url)
        existing = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        extra = [(k, str(v)) for k, v in params.items() if v is not None]
        query = urllib.parse.urlencode(existing + extra)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def best_bid_ask_from_book(book: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    bids = book.get("bids") or []
    asks = book.get("asks") or []

    best_bid = None
    for b in bids:
        p = safe_float(b.get("price") if isinstance(b, dict) else None)
        if p is None:
            continue
        best_bid = p if best_bid is None else max(best_bid, p)

    best_ask = None
    for a in asks:
        p = safe_float(a.get("price") if isinstance(a, dict) else None)
        if p is None:
            continue
        best_ask = p if best_ask is None else min(best_ask, p)

    return best_bid, best_ask
