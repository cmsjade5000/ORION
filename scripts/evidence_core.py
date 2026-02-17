#!/usr/bin/env python3
"""
Evidence core primitives used by retrieval/drafting agents (WIRE/SCRIBE/ORION).

Goals:
- deterministic validation (no network)
- strict timestamp parsing (avoid stale "latest" items)
- simple credibility tiers that downstream agents can extend
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any


ALLOWED_SOURCE_TIERS = {"primary", "secondary", "low"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


class EvidenceError(ValueError):
    pass


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_rfc3339(ts: str) -> dt.datetime:
    """
    Parse a subset of RFC3339/ISO8601 timestamps into an aware datetime.

    Accepted forms:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SSZ
    - YYYY-MM-DDTHH:MM:SS+00:00 (and other offsets)
    - fractional seconds are allowed
    """
    s = (ts or "").strip()
    if not s:
        raise EvidenceError("published_at is empty")

    # Date-only -> midnight UTC
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            d = dt.date.fromisoformat(s)
        except Exception as e:
            raise EvidenceError(f"invalid date-only published_at: {s!r}") from e
        return dt.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=dt.timezone.utc)

    # Support Z suffix by mapping to +00:00 for fromisoformat.
    s2 = s[:-1] + "+00:00" if s.endswith("Z") else s
    try:
        out = dt.datetime.fromisoformat(s2)
    except Exception as e:
        raise EvidenceError(f"invalid published_at timestamp: {s!r}") from e

    if out.tzinfo is None:
        raise EvidenceError(f"published_at must include timezone: {s!r}")
    return out


def within_time_window(*, published_at: dt.datetime, now: dt.datetime, window: dt.timedelta) -> bool:
    if published_at.tzinfo is None or now.tzinfo is None:
        raise EvidenceError("published_at/now must be timezone-aware")
    if window.total_seconds() < 0:
        raise EvidenceError("window must be non-negative")
    delta = now - published_at
    # Future timestamps are invalid for "freshness" checks.
    if delta.total_seconds() < 0:
        return False
    return delta <= window


def _parse_claims(obj: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Optional traceability adapter:
    - If `claims` is present, validate and return list of (claim_text, url).
    - Otherwise return a single (claim,url) pair from required fields.
    """
    if "claims" in obj:
        raw = obj.get("claims")
        if not isinstance(raw, list) or not raw:
            raise EvidenceError("claims must be a non-empty list when provided")
        out: list[tuple[str, str]] = []
        for i, it in enumerate(raw):
            if not isinstance(it, dict):
                raise EvidenceError(f"claims[{i}] must be an object")
            c = it.get("claim", "")
            u = it.get("url", "")
            if not isinstance(c, str) or not c.strip():
                raise EvidenceError(f"claims[{i}].claim missing/empty")
            if not isinstance(u, str) or not u.strip():
                raise EvidenceError(f"claims[{i}].url missing/empty")
            out.append((c.strip(), u.strip()))
        return out

    # Fallback to the single-claim schema.
    claim = obj.get("claim", "")
    url = obj.get("url", "")
    if not isinstance(claim, str) or not claim.strip():
        raise EvidenceError("missing/empty field: claim")
    if not isinstance(url, str) or not url.strip():
        raise EvidenceError("missing/empty field: url")
    return [(claim.strip(), url.strip())]


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
    title: str
    source: str
    url: str
    published_at: dt.datetime
    claim: str
    claims: tuple[tuple[str, str], ...] = ()
    source_tier: str = "secondary"
    confidence: str = "medium"

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "EvidenceItem":
        def _req_str(k: str) -> str:
            v = obj.get(k, "")
            if not isinstance(v, str) or not v.strip():
                raise EvidenceError(f"missing/empty field: {k}")
            return v.strip()

        title = _req_str("title")
        source = _req_str("source")
        # Traceability adapter: supports either a single claim+url, or a multi-claim list.
        parsed_claims = _parse_claims(obj)
        # Preserve compatibility with the existing schema by keeping url/claim required.
        # If multi-claims are provided, prefer the first one for the legacy fields.
        claim, url = parsed_claims[0][0], parsed_claims[0][1]

        published_raw = _req_str("published_at")
        published_at = parse_rfc3339(published_raw)

        tier = obj.get("source_tier", "secondary")
        if not isinstance(tier, str):
            raise EvidenceError("source_tier must be a string")
        tier = tier.strip().lower()
        if tier not in ALLOWED_SOURCE_TIERS:
            raise EvidenceError(f"invalid source_tier: {tier!r} (allowed: {sorted(ALLOWED_SOURCE_TIERS)!r})")

        conf = obj.get("confidence", "medium")
        if not isinstance(conf, str):
            raise EvidenceError("confidence must be a string")
        conf = conf.strip().lower()
        if conf not in ALLOWED_CONFIDENCE:
            raise EvidenceError(f"invalid confidence: {conf!r} (allowed: {sorted(ALLOWED_CONFIDENCE)!r})")

        return EvidenceItem(
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            claim=claim,
            claims=tuple(parsed_claims),
            source_tier=tier,
            confidence=conf,
        )


@dataclasses.dataclass(frozen=True)
class EvidenceCheckResult:
    ok: bool
    errors: list[str]


def validate_items(
    items: list[dict[str, Any]],
    *,
    time_window_hours: float = 24.0,
    now: dt.datetime | None = None,
    min_source_tier: str = "secondary",
) -> EvidenceCheckResult:
    if now is None:
        now = _utc_now()
    if now.tzinfo is None:
        raise EvidenceError("now must be timezone-aware")
    if time_window_hours < 0:
        raise EvidenceError("time_window_hours must be non-negative")
    if min_source_tier not in ALLOWED_SOURCE_TIERS:
        raise EvidenceError(f"invalid min_source_tier: {min_source_tier!r}")

    # Ordering is strictest->loosest.
    tier_rank = {"primary": 3, "secondary": 2, "low": 1}
    min_rank = tier_rank[min_source_tier]
    window = dt.timedelta(hours=float(time_window_hours))

    errs: list[str] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            errs.append(f"items[{i}]: must be an object")
            continue
        try:
            it = EvidenceItem.from_dict(raw)
        except Exception as e:
            errs.append(f"items[{i}]: {e}")
            continue

        if tier_rank[it.source_tier] < min_rank:
            errs.append(f"items[{i}]: source_tier {it.source_tier!r} below minimum {min_source_tier!r}")

        if not within_time_window(published_at=it.published_at, now=now, window=window):
            errs.append(
                f"items[{i}]: published_at {it.published_at.isoformat()} not within {time_window_hours}h window of now {now.isoformat()}"
            )

        # Minimal traceability rule: if you make a claim, you must have a URL.
        # (Claims are required earlier, but keep this explicit for future schema relaxations.)
        if not it.claims:
            errs.append(f"items[{i}]: no claims present for traceability")
        else:
            for j, (_c, u) in enumerate(it.claims):
                if not u.strip():
                    errs.append(f"items[{i}].claims[{j}]: missing url for claim traceability")

    return EvidenceCheckResult(ok=(len(errs) == 0), errors=errs)
