from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


def ledger_path(repo_root: str) -> str:
    return os.path.join(repo_root, "tmp", "polymarket_sports_paper", "ledger.json")


def load_ledger(repo_root: str) -> Dict[str, Any]:
    p = ledger_path(repo_root)
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            obj.setdefault("version", 1)
            obj.setdefault("positions", {})
            obj.setdefault("runs", [])
            obj.setdefault("stats", {})
            return obj
    except Exception:
        pass
    return {"version": 1, "positions": {}, "runs": [], "stats": {}}


def save_ledger(repo_root: str, ledger: Dict[str, Any]) -> None:
    p = ledger_path(repo_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = f"{p}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)


def add_position(ledger: Dict[str, Any], pos: Dict[str, Any]) -> str:
    positions = ledger.setdefault("positions", {})
    if not isinstance(positions, dict):
        positions = {}
        ledger["positions"] = positions
    pid = str(pos.get("id") or f"pp-{int(time.time()*1000)}")
    row = dict(pos)
    row["id"] = pid
    row.setdefault("status", "open")
    row.setdefault("opened_ts_unix", int(time.time()))
    positions[pid] = row
    return pid


def open_positions(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    positions = ledger.get("positions")
    if not isinstance(positions, dict):
        return []
    out: List[Dict[str, Any]] = []
    for _, v in positions.items():
        if isinstance(v, dict) and str(v.get("status") or "") == "open":
            out.append(v)
    out.sort(key=lambda x: int(x.get("opened_ts_unix") or 0))
    return out


def settle_position(ledger: Dict[str, Any], position_id: str, *, settled_ts_unix: int, pnl_usd: float, note: str = "") -> bool:
    positions = ledger.get("positions")
    if not isinstance(positions, dict):
        return False
    pos = positions.get(str(position_id))
    if not isinstance(pos, dict):
        return False
    if str(pos.get("status") or "") != "open":
        return False
    pos["status"] = "settled"
    pos["settled_ts_unix"] = int(settled_ts_unix)
    pos["pnl_usd"] = float(pnl_usd)
    if note:
        pos["settle_note"] = str(note)
    return True


def append_run(ledger: Dict[str, Any], run: Dict[str, Any], *, max_runs: int = 500) -> None:
    runs = ledger.setdefault("runs", [])
    if not isinstance(runs, list):
        runs = []
        ledger["runs"] = runs
    row = dict(run)
    row.setdefault("ts_unix", int(time.time()))
    runs.append(row)
    if len(runs) > int(max_runs):
        del runs[: len(runs) - int(max_runs)]


def recompute_stats(ledger: Dict[str, Any]) -> Dict[str, Any]:
    positions = ledger.get("positions")
    if not isinstance(positions, dict):
        st = {"open_positions": 0, "settled_positions": 0, "realized_pnl_usd": 0.0}
        ledger["stats"] = st
        return st
    open_n = 0
    settled_n = 0
    pnl = 0.0
    for _, p in positions.items():
        if not isinstance(p, dict):
            continue
        if str(p.get("status") or "") == "open":
            open_n += 1
        elif str(p.get("status") or "") == "settled":
            settled_n += 1
            if isinstance(p.get("pnl_usd"), (int, float)):
                pnl += float(p.get("pnl_usd"))
    st = {"open_positions": int(open_n), "settled_positions": int(settled_n), "realized_pnl_usd": float(pnl)}
    ledger["stats"] = st
    return st

