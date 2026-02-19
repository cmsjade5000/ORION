from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


def _truthy(raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return bool(default)
    v = str(raw).strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "y", "on")


def _int_env(name: str, default: int, *, min_v: int | None = None) -> tuple[int, str | None]:
    raw = os.environ.get(name, str(default))
    try:
        out = int(str(raw).strip())
    except Exception:
        return int(default), f"{name} must be an integer (got {raw!r})"
    if min_v is not None and out < int(min_v):
        return int(default), f"{name} must be >= {int(min_v)} (got {out})"
    return out, None


def _float_env(name: str, default: float, *, min_v: float | None = None, max_v: float | None = None) -> tuple[float, str | None]:
    raw = os.environ.get(name, str(default))
    try:
        out = float(str(raw).strip())
    except Exception:
        return float(default), f"{name} must be a number (got {raw!r})"
    if min_v is not None and out < float(min_v):
        return float(default), f"{name} must be >= {float(min_v)} (got {out})"
    if max_v is not None and out > float(max_v):
        return float(default), f"{name} must be <= {float(max_v)} (got {out})"
    return out, None


def _feeds(raw: str) -> List[str]:
    allowed = {"coinbase", "kraken", "binance", "bitstamp"}
    out: List[str] = []
    seen: set[str] = set()
    for p in str(raw or "").replace(";", ",").split(","):
        v = p.strip().lower()
        if not v:
            continue
        if v not in allowed:
            continue
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


@dataclass(frozen=True)
class KalshiArbRuntime:
    execution_mode: str
    live_armed: bool
    ref_feeds: List[str]
    enable_funding_filter: bool
    enable_regime_filter: bool
    retry_max_attempts: int
    retry_base_ms: int
    milestone_notify: bool
    metrics_enabled: bool
    metrics_path: str
    max_dispersion_bps: float
    max_vol_anomaly_ratio: float
    funding_abs_bps_max: float
    max_market_concentration_fraction: float

    @property
    def allow_live_writes(self) -> bool:
        return self.execution_mode == "live" and bool(self.live_armed)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["allow_live_writes"] = bool(self.allow_live_writes)
        return d


def load_runtime_from_env(*, repo_root: str) -> tuple[KalshiArbRuntime, List[str]]:
    errs: List[str] = []

    mode = str(os.environ.get("KALSHI_ARB_EXECUTION_MODE", "paper") or "paper").strip().lower()
    if mode not in ("paper", "live"):
        errs.append(f"KALSHI_ARB_EXECUTION_MODE must be 'paper' or 'live' (got {mode!r}); using 'paper'.")
        mode = "paper"

    live_armed = _truthy(os.environ.get("KALSHI_ARB_LIVE_ARMED", "0"), default=False)
    ref_feeds = _feeds(os.environ.get("KALSHI_ARB_REF_FEEDS", "coinbase,kraken,binance"))
    if not ref_feeds:
        errs.append("KALSHI_ARB_REF_FEEDS had no valid venues; using coinbase,kraken,binance.")
        ref_feeds = ["coinbase", "kraken", "binance"]

    retry_max_attempts, e = _int_env("KALSHI_ARB_RETRY_MAX_ATTEMPTS", 4, min_v=1)
    if e:
        errs.append(e)
    retry_base_ms, e = _int_env("KALSHI_ARB_RETRY_BASE_MS", 250, min_v=50)
    if e:
        errs.append(e)
    max_dispersion_bps, e = _float_env("KALSHI_ARB_MAX_DISPERSION_BPS", 35.0, min_v=1.0)
    if e:
        errs.append(e)
    max_vol_anomaly_ratio, e = _float_env("KALSHI_ARB_MAX_VOL_ANOMALY_RATIO", 1.8, min_v=1.0)
    if e:
        errs.append(e)
    funding_abs_bps_max, e = _float_env("KALSHI_ARB_FUNDING_ABS_BPS_MAX", 3.0, min_v=0.0)
    if e:
        errs.append(e)
    max_market_concentration_fraction, e = _float_env(
        "KALSHI_ARB_MAX_MARKET_CONCENTRATION_FRACTION",
        0.35,
        min_v=0.05,
        max_v=1.0,
    )
    if e:
        errs.append(e)

    metrics_path = str(
        os.environ.get(
            "KALSHI_ARB_METRICS_PATH",
            os.path.join(repo_root, "tmp", "kalshi_ref_arb", "metrics.prom"),
        )
    ).strip()
    if not metrics_path:
        metrics_path = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "metrics.prom")

    cfg = KalshiArbRuntime(
        execution_mode=mode,
        live_armed=live_armed,
        ref_feeds=ref_feeds,
        enable_funding_filter=_truthy(os.environ.get("KALSHI_ARB_ENABLE_FUNDING_FILTER", "1"), default=True),
        enable_regime_filter=_truthy(os.environ.get("KALSHI_ARB_ENABLE_REGIME_FILTER", "1"), default=True),
        retry_max_attempts=int(retry_max_attempts),
        retry_base_ms=int(retry_base_ms),
        milestone_notify=_truthy(os.environ.get("KALSHI_ARB_MILESTONE_NOTIFY", "1"), default=True),
        metrics_enabled=_truthy(os.environ.get("KALSHI_ARB_METRICS_ENABLED", "1"), default=True),
        metrics_path=str(metrics_path),
        max_dispersion_bps=float(max_dispersion_bps),
        max_vol_anomaly_ratio=float(max_vol_anomaly_ratio),
        funding_abs_bps_max=float(funding_abs_bps_max),
        max_market_concentration_fraction=float(max_market_concentration_fraction),
    )
    return cfg, errs

