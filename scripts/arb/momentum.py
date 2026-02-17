from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple


HISTORY_REL = os.path.join("tmp", "kalshi_ref_arb", "ref_spot_history.json")


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else dict(default)
    except Exception:
        return dict(default)


def _save_json_atomic(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def history_path(repo_root: str) -> str:
    return os.path.join(str(repo_root), HISTORY_REL)


def update_ref_spot_history(
    repo_root: str,
    *,
    series: str,
    spot_ref: float,
    ts_unix: Optional[int] = None,
    min_interval_s: int = 60,
    max_points_per_series: int = 800,
) -> None:
    """Append a spot point for the series (bounded)."""
    now = int(ts_unix if ts_unix is not None else time.time())
    s = (series or "").strip().upper()
    if not s:
        return

    p = history_path(repo_root)
    obj = _load_json(p, default={"version": 1, "series": {}})
    series_map = obj.get("series")
    if not isinstance(series_map, dict):
        series_map = {}
        obj["series"] = series_map

    arr = series_map.get(s)
    if not isinstance(arr, list):
        arr = []

    # Deduplicate fast repeated writes (same minute-ish).
    if arr:
        last = arr[-1]
        if isinstance(last, dict):
            try:
                last_ts = int(last.get("ts_unix") or 0)
            except Exception:
                last_ts = 0
            if last_ts and (now - last_ts) < int(min_interval_s):
                return

    arr.append({"ts_unix": int(now), "spot_ref": float(spot_ref)})
    if len(arr) > int(max_points_per_series):
        del arr[: len(arr) - int(max_points_per_series)]
    series_map[s] = arr
    obj["ts_updated"] = int(now)
    _save_json_atomic(p, obj)


def _find_point_at_or_before(points: List[Dict[str, Any]], ts_unix: int) -> Optional[Tuple[int, float]]:
    best = None
    for it in points:
        if not isinstance(it, dict):
            continue
        try:
            t = int(it.get("ts_unix") or 0)
            px = float(it.get("spot_ref") or 0.0)
        except Exception:
            continue
        if t <= int(ts_unix) and px > 0.0:
            if best is None or t > best[0]:
                best = (t, px)
    return best


def momentum_pct(
    repo_root: str,
    *,
    series: str,
    lookback_s: int,
    now_ts_unix: Optional[int] = None,
    spot_ref_now: Optional[float] = None,
) -> Optional[float]:
    """Return (spot_now/spot_then - 1) for a historical lookback window."""
    s = (series or "").strip().upper()
    if not s:
        return None
    now = int(now_ts_unix if now_ts_unix is not None else time.time())
    p = history_path(repo_root)
    obj = _load_json(p, default={"version": 1, "series": {}})
    series_map = obj.get("series")
    if not isinstance(series_map, dict):
        return None
    arr = series_map.get(s)
    if not isinstance(arr, list) or not arr:
        return None

    now_px = None
    if isinstance(spot_ref_now, (int, float)) and float(spot_ref_now) > 0:
        now_px = float(spot_ref_now)
    else:
        pt_now = _find_point_at_or_before(arr, now)
        if pt_now is not None:
            now_px = float(pt_now[1])
    if not now_px or now_px <= 0.0:
        return None

    then_ts = int(now) - int(lookback_s)
    pt_then = _find_point_at_or_before(arr, then_ts)
    if pt_then is None:
        return None
    then_px = float(pt_then[1])
    if then_px <= 0.0:
        return None
    return float(now_px / then_px - 1.0)

