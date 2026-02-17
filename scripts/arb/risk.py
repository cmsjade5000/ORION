from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RiskConfig:
    max_orders_per_run: int = 3
    max_contracts_per_order: int = 25
    max_notional_per_run_usd: float = 50.0
    max_notional_per_market_usd: float = 50.0
    kill_switch_path: str = "tmp/kalshi_ref_arb.KILL"
    cooldown_path: str = "tmp/kalshi_ref_arb/cooldown.json"


class RiskState:
    """Local-only state to enforce caps within and across runs.

    Stored under tmp/ (gitignored).
    """

    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Any] = {"version": 1, "markets": {}, "runs": [], "observations": {}}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {"version": 1, "markets": {}, "runs": [], "observations": {}}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
            f.write("\n")

    def market_notional_usd(self, ticker: str) -> float:
        m = (self._data.get("markets") or {}).get(ticker) or {}
        try:
            return float(m.get("notional_usd") or 0.0)
        except Exception:
            return 0.0

    def add_market_notional_usd(self, ticker: str, delta: float) -> None:
        markets = self._data.setdefault("markets", {})
        m = markets.get(ticker) or {"notional_usd": 0.0}
        m["notional_usd"] = float(m.get("notional_usd") or 0.0) + float(delta)
        markets[ticker] = m

    def append_run(self, payload: Dict[str, Any]) -> None:
        runs = self._data.setdefault("runs", [])
        payload = dict(payload)
        payload.setdefault("ts_unix", int(time.time()))
        runs.append(payload)
        # Keep it bounded.
        if len(runs) > 200:
            del runs[: len(runs) - 200]

    def record_observation(self, key: str, *, edge_bps: float, ts_unix: Optional[int] = None) -> None:
        obs = self._data.setdefault("observations", {})
        if not isinstance(obs, dict):
            obs = {}
            self._data["observations"] = obs
        k = str(key)
        arr = obs.get(k)
        if not isinstance(arr, list):
            arr = []
        payload = {"ts_unix": int(ts_unix if ts_unix is not None else time.time()), "edge_bps": float(edge_bps)}
        arr.append(payload)
        # Bound per-key.
        if len(arr) > 80:
            del arr[: len(arr) - 80]
        obs[k] = arr

    def count_observations(self, key: str, *, min_ts_unix: int, min_edge_bps: float) -> int:
        obs = self._data.get("observations", {})
        if not isinstance(obs, dict):
            return 0
        arr = obs.get(str(key))
        if not isinstance(arr, list):
            return 0
        n = 0
        for it in arr:
            if not isinstance(it, dict):
                continue
            try:
                ts = int(it.get("ts_unix") or 0)
                edge = float(it.get("edge_bps") or 0.0)
            except Exception:
                continue
            if ts >= int(min_ts_unix) and edge >= float(min_edge_bps):
                n += 1
        return n


def kill_switch_tripped(cfg: RiskConfig, repo_root: str) -> bool:
    p = cfg.kill_switch_path
    # Support relative to repo root by default.
    if not os.path.isabs(p):
        p = os.path.join(repo_root, p)
    return os.path.exists(p)


def cooldown_active(cfg: RiskConfig, repo_root: str) -> Dict[str, Any]:
    """Returns {active: bool, until_ts: int, remaining_s: int, reason: str}."""
    p = cfg.cooldown_path
    if not os.path.isabs(p):
        p = os.path.join(repo_root, p)
    try:
        obj = json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return {"active": False, "until_ts": 0, "remaining_s": 0, "reason": ""}
    if not isinstance(obj, dict):
        return {"active": False, "until_ts": 0, "remaining_s": 0, "reason": ""}
    until_ts = int(obj.get("until_ts") or 0)
    now = int(time.time())
    remaining = max(0, until_ts - now)
    return {
        "active": remaining > 0,
        "until_ts": until_ts,
        "remaining_s": remaining,
        "reason": str(obj.get("reason") or ""),
    }


def set_cooldown(cfg: RiskConfig, repo_root: str, *, seconds: int, reason: str) -> bool:
    p = cfg.cooldown_path
    if not os.path.isabs(p):
        p = os.path.join(repo_root, p)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    until = int(time.time()) + max(0, int(seconds))
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"until_ts": until, "reason": str(reason), "ts_set": int(time.time())}, f, indent=2, sort_keys=True)
            f.write("\n")
        return True
    except Exception:
        return False
