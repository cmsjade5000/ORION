from __future__ import annotations

import json
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
        self._cfg = cfg or HttpConfig()

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
                if attempt >= self._cfg.max_retries:
                    break
                time.sleep(self._cfg.retry_backoff_seconds * (2**attempt))
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

