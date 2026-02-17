from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .http import HttpClient, HttpConfig, best_bid_ask_from_book


@dataclass(frozen=True)
class GammaMarket:
    id: str
    slug: str
    question: str
    active: bool
    closed: bool
    enable_order_book: bool
    outcomes: List[str]
    clob_token_ids: List[str]
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None


class PolymarketAPI:
    """Read-only Polymarket API helper.

    This intentionally only uses public endpoints:
    - Gamma API for market discovery
    - CLOB API for order books
    - polymarket.com geoblock probe

    Live trading requires authenticated/signed requests and is out of scope here.
    """

    def __init__(
        self,
        *,
        gamma_base_url: str = "https://gamma-api.polymarket.com",
        clob_base_url: str = "https://clob.polymarket.com",
        web_base_url: str = "https://polymarket.com",
        http_cfg: Optional[HttpConfig] = None,
    ):
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")
        self.web_base_url = web_base_url.rstrip("/")
        self.http = HttpClient(http_cfg or HttpConfig())

    def get_geoblock(self) -> Dict[str, Any]:
        return self.http.get_json(f"{self.web_base_url}/api/geoblock")

    def iter_gamma_markets(
        self,
        *,
        active: bool = True,
        closed: bool = False,
        limit: int = 50,
        max_pages: int = 5,
        offset: int = 0,
    ) -> Iterable[GammaMarket]:
        """Iterate markets from Gamma.

        Gamma uses offset-based pagination (`offset`, `limit`).
        """
        if limit <= 0:
            return
        limit = min(limit, 200)

        pages = 0
        cur_offset = max(0, int(offset))
        while pages < max_pages:
            params = {
                "active": "true" if active else "false",
                "closed": "true" if closed else "false",
                "limit": str(limit),
                "offset": str(cur_offset),
            }
            items = self.http.get_json(f"{self.gamma_base_url}/markets", params=params)
            if not isinstance(items, list) or not items:
                return
            for raw in items:
                m = self._parse_gamma_market(raw)
                if m is not None:
                    yield m
            pages += 1
            cur_offset += limit

    def get_clob_book(self, token_id: str) -> Dict[str, Any]:
        return self.http.get_json(f"{self.clob_base_url}/book", params={"token_id": token_id})

    def get_best_bid_ask(self, token_id: str) -> Tuple[Optional[float], Optional[float]]:
        book = self.get_clob_book(token_id)
        return best_bid_ask_from_book(book)

    @staticmethod
    def _parse_gamma_market(raw: Dict[str, Any]) -> Optional[GammaMarket]:
        try:
            outcomes = raw.get("outcomes")
            if isinstance(outcomes, str):
                outcomes = json.loads(outcomes)
            if not isinstance(outcomes, list):
                outcomes = []

            token_ids = raw.get("clobTokenIds") or raw.get("clobTokenIDs") or raw.get("clob_token_ids")
            if isinstance(token_ids, str):
                token_ids = json.loads(token_ids)
            if not isinstance(token_ids, list):
                token_ids = []

            return GammaMarket(
                id=str(raw.get("id") or ""),
                slug=str(raw.get("slug") or ""),
                question=str(raw.get("question") or ""),
                active=bool(raw.get("active")),
                closed=bool(raw.get("closed")),
                enable_order_book=bool(raw.get("enableOrderBook") or raw.get("enable_order_book")),
                outcomes=[str(x) for x in outcomes],
                clob_token_ids=[str(x) for x in token_ids],
                best_bid=_safe_float(raw.get("bestBid")),
                best_ask=_safe_float(raw.get("bestAsk")),
            )
        except Exception:
            return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

