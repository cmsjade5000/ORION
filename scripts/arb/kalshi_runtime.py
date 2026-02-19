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


def _float_raw(name: str, raw: Any, default: float, *, min_v: float | None = None, max_v: float | None = None) -> tuple[float, str | None]:
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


def _parse_regime_mults(raw: str) -> tuple[Dict[str, float], str | None]:
    base = {"calm": 0.9, "normal": 1.0, "hot": 1.2}
    txt = str(raw or "").strip()
    if not txt:
        return base, None
    out = dict(base)
    allowed = {"calm", "normal", "hot"}
    for part in txt.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        key = str(k or "").strip().lower()
        if key not in allowed:
            continue
        try:
            fv = float(str(v).strip())
        except Exception:
            return base, f"KALSHI_ARB_DYNAMIC_EDGE_REGIME_MULTS invalid value for {key}: {v!r}"
        if fv <= 0.0 or fv > 10.0:
            return base, f"KALSHI_ARB_DYNAMIC_EDGE_REGIME_MULTS out of range for {key}: {fv}"
        out[key] = float(fv)
    return out, None


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
    max_ref_quote_age_sec: float
    max_dispersion_bps: float
    max_vol_anomaly_ratio: float
    funding_abs_bps_max: float
    max_market_concentration_fraction: float
    dynamic_edge_enabled: bool
    dynamic_edge_regime_mults: Dict[str, float]
    reinvest_enabled: bool
    reinvest_max_fraction: float
    drawdown_throttle_pct: float
    paper_exec_emulator: bool
    paper_exec_latency_ms: int
    paper_exec_slippage_bps: float
    portfolio_allocator_enabled: bool
    portfolio_allocator_min_signal_fraction: float
    portfolio_allocator_edge_power: float
    portfolio_allocator_confidence_power: float

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
    max_ref_quote_age_sec, e = _float_env("KALSHI_ARB_MAX_REF_QUOTE_AGE_SEC", 3.0, min_v=0.1, max_v=60.0)
    if e:
        errs.append(e)
    # Backward compatibility:
    # - preferred: KALSHI_ARB_MAX_REF_DISPERSION_BPS
    # - legacy:    KALSHI_ARB_MAX_DISPERSION_BPS
    disp_raw = os.environ.get("KALSHI_ARB_MAX_REF_DISPERSION_BPS")
    if disp_raw is None or str(disp_raw).strip() == "":
        disp_raw = os.environ.get("KALSHI_ARB_MAX_DISPERSION_BPS", "35.0")
    max_dispersion_bps, e = _float_raw("KALSHI_ARB_MAX_REF_DISPERSION_BPS", disp_raw, 35.0, min_v=1.0)
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
    dynamic_edge_regime_mults, e = _parse_regime_mults(os.environ.get("KALSHI_ARB_DYNAMIC_EDGE_REGIME_MULTS", "calm:0.9,normal:1.0,hot:1.2"))
    if e:
        errs.append(e)
    reinvest_max_fraction, e = _float_env("KALSHI_ARB_REINVEST_MAX_FRACTION", 0.08, min_v=0.0, max_v=1.0)
    if e:
        errs.append(e)
    drawdown_throttle_pct, e = _float_env("KALSHI_ARB_DRAWDOWN_THROTTLE_PCT", 5.0, min_v=0.0, max_v=95.0)
    if e:
        errs.append(e)
    paper_exec_latency_ms, e = _int_env("KALSHI_ARB_PAPER_EXEC_LATENCY_MS", 250, min_v=0)
    if e:
        errs.append(e)
    paper_exec_slippage_bps, e = _float_env("KALSHI_ARB_PAPER_EXEC_SLIPPAGE_BPS", 5.0, min_v=0.0, max_v=1000.0)
    if e:
        errs.append(e)
    portfolio_allocator_min_signal_fraction, e = _float_env(
        "KALSHI_ARB_PORTFOLIO_ALLOCATOR_MIN_SIGNAL_FRACTION",
        0.05,
        min_v=0.0,
        max_v=0.5,
    )
    if e:
        errs.append(e)
    portfolio_allocator_edge_power, e = _float_env("KALSHI_ARB_PORTFOLIO_ALLOCATOR_EDGE_POWER", 1.0, min_v=0.2, max_v=4.0)
    if e:
        errs.append(e)
    portfolio_allocator_confidence_power, e = _float_env(
        "KALSHI_ARB_PORTFOLIO_ALLOCATOR_CONFIDENCE_POWER",
        1.0,
        min_v=0.2,
        max_v=4.0,
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
        max_ref_quote_age_sec=float(max_ref_quote_age_sec),
        max_dispersion_bps=float(max_dispersion_bps),
        max_vol_anomaly_ratio=float(max_vol_anomaly_ratio),
        funding_abs_bps_max=float(funding_abs_bps_max),
        max_market_concentration_fraction=float(max_market_concentration_fraction),
        dynamic_edge_enabled=_truthy(os.environ.get("KALSHI_ARB_DYNAMIC_EDGE_ENABLED", "1"), default=True),
        dynamic_edge_regime_mults=dict(dynamic_edge_regime_mults),
        reinvest_enabled=_truthy(os.environ.get("KALSHI_ARB_REINVEST_ENABLED", "1"), default=True),
        reinvest_max_fraction=float(reinvest_max_fraction),
        drawdown_throttle_pct=float(drawdown_throttle_pct),
        paper_exec_emulator=_truthy(os.environ.get("KALSHI_ARB_PAPER_EXEC_EMULATOR", "1"), default=True),
        paper_exec_latency_ms=int(paper_exec_latency_ms),
        paper_exec_slippage_bps=float(paper_exec_slippage_bps),
        portfolio_allocator_enabled=_truthy(os.environ.get("KALSHI_ARB_PORTFOLIO_ALLOCATOR_ENABLED", "1"), default=True),
        portfolio_allocator_min_signal_fraction=float(portfolio_allocator_min_signal_fraction),
        portfolio_allocator_edge_power=float(portfolio_allocator_edge_power),
        portfolio_allocator_confidence_power=float(portfolio_allocator_confidence_power),
    )
    return cfg, errs
