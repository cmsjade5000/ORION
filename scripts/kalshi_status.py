#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

try:
    from scripts.arb.kalshi_ledger import load_ledger  # type: ignore
except ModuleNotFoundError:
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi_ledger import load_ledger  # type: ignore


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _kill_switch_on(root: str) -> bool:
    return os.path.exists(os.path.join(root, "tmp", "kalshi_ref_arb.KILL"))


def _cooldown_info(root: str) -> Dict[str, Any]:
    p = os.path.join(root, "tmp", "kalshi_ref_arb", "cooldown.json")
    obj = _load_json(p) or {}
    now = int(time.time())
    until = int(obj.get("until_ts") or 0)
    remaining = max(0, until - now)
    return {
        "active": remaining > 0,
        "remaining_s": remaining,
        "reason": str(obj.get("reason") or ""),
        "until_ts": until,
    }


def _latest_run(root: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    runs_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "runs")
    paths = sorted(glob.glob(os.path.join(runs_dir, "*.json")))
    if not paths:
        return None
    # named <unix>.json; sort already works but be safe
    paths.sort(key=lambda p: int(os.path.basename(p).split(".")[0] or "0"))
    for p in reversed(paths):
        obj = _load_json(p)
        if obj:
            return p, obj
    return None


def _extract_cash_pv(run: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    for path in (("post", "balance"), ("balance", "balance")):
        cur: Any = run
        ok = True
        for k in path:
            if not isinstance(cur, dict):
                ok = False
                break
            cur = cur.get(k)
        if not ok or not isinstance(cur, dict):
            continue
        try:
            cash = float(cur.get("balance") or 0.0) / 100.0
            pv = float(cur.get("portfolio_value") or 0.0) / 100.0
            return cash, pv
        except Exception:
            continue
    return None, None


def _format_usd(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Print Kalshi bot status message (for Telegram).")
    args = ap.parse_args()

    root = _repo_root()
    kill_on = _kill_switch_on(root)
    cd = _cooldown_info(root)
    last = _latest_run(root)
    now = int(time.time())

    lines = []
    lines.append("Kalshi status")
    lines.append(f"Kill switch: {'ON' if kill_on else 'OFF'}")
    if cd.get("active"):
        mins = int((int(cd.get('remaining_s') or 0) + 59) / 60)
        tail = f" ({cd.get('reason')})" if cd.get("reason") else ""
        lines.append(f"Cooldown: ON ({mins}m){tail}")
    else:
        lines.append("Cooldown: OFF")

    if not last:
        msg = "\n".join(lines)
        print(json.dumps({"mode": "kalshi_status", "timestamp_unix": now, "message": msg}, indent=2, sort_keys=True))
        return 0

    _, run = last
    ts = int(run.get("ts_unix") or 0)
    if ts:
        lines.append(f"Last cycle: {time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(ts))}")

    cash, pv = _extract_cash_pv(run)
    lines.append(f"Cash: {_format_usd(cash)}")
    lines.append(f"Portfolio value: {_format_usd(pv)}")

    trade = run.get("trade") if isinstance(run.get("trade"), dict) else {}
    status = str(trade.get("status") or "")
    reason = str(trade.get("reason") or "")
    if status:
        lines.append(f"Trade: {status}{f' ({reason})' if reason else ''}")

    placed = trade.get("placed") if isinstance(trade.get("placed"), list) else []
    live = [p for p in placed if isinstance(p, dict) and p.get("mode") == "live"]
    if live:
        o = (live[0].get("order") or {}) if isinstance(live[0].get("order"), dict) else {}
        lines.append(
            f"Last order: {o.get('action')} {o.get('side')} {o.get('count')}x {o.get('ticker')} @ {o.get('price_dollars')}"
        )
    else:
        diag = trade.get("diagnostics") if isinstance(trade.get("diagnostics"), dict) else {}
        best = (
            diag.get("best_effective_edge_pass_filters")
            or diag.get("best_effective_edge_any_quote")
            or diag.get("best_effective_edge")
        )
        best = best if isinstance(best, dict) else {}
        if best.get("ticker"):
            try:
                lines.append(
                    f"No trades: best eff edge {float(best.get('effective_edge_bps')):.0f} bps on {best.get('ticker')} {best.get('side')} @ {float(best.get('ask')):.4f}"
                )
            except Exception:
                pass
        tb = diag.get("top_blockers") if isinstance(diag.get("top_blockers"), list) else []
        parts = []
        for it in tb[:5]:
            if not isinstance(it, dict):
                continue
            r = it.get("reason")
            c = it.get("count")
            if isinstance(r, str) and isinstance(c, int):
                parts.append(f"{r}={c}")
        if parts:
            lines.append(f"Blockers: {', '.join(parts)}")
        totals = diag.get("totals") if isinstance(diag.get("totals"), dict) else {}
        if totals:
            try:
                qp = int(totals.get("quotes_present") or 0)
                pn = int(totals.get("pass_non_edge_filters") or 0)
                lines.append(f"Diag: quotes {qp}, pass-non-edge {pn}")
            except Exception:
                pass

    # Ledger health: show unmatched settlements (so we know if settlement parsing needs work).
    try:
        led = load_ledger(root)
        um = led.get("unmatched_settlements") if isinstance(led, dict) else None
        if isinstance(um, list) and um:
            lines.append(f"Unmatched settlements: {len(um)}")
    except Exception:
        pass

    msg = "\n".join(lines)
    payload = {
        "mode": "kalshi_status",
        "timestamp_unix": now,
        "message": msg,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
