#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from scripts.arb.kalshi_analytics import match_fills_for_order  # type: ignore
    from scripts.arb.risk import RiskConfig, cooldown_active, set_cooldown  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore
    from scripts.arb.kalshi_ledger import update_from_run  # type: ignore
except ModuleNotFoundError:
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi_analytics import match_fills_for_order  # type: ignore
    from scripts.arb.risk import RiskConfig, cooldown_active, set_cooldown  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore
    from scripts.arb.kalshi_ledger import update_from_run  # type: ignore


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _read_openclaw_telegram_chat_id() -> Optional[int]:
    p = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception:
        return None

    chan = ((obj.get("channels") or {}).get("telegram") or {})
    allow = chan.get("allowFrom") or chan.get("dm", {}).get("allowFrom") or []
    try:
        if isinstance(allow, list) and allow:
            return int(allow[0])
    except Exception:
        return None
    return None


def _telegram_chat_id() -> Optional[int]:
    raw = os.environ.get("ORION_TELEGRAM_CHAT_ID") or ""
    if raw.strip():
        try:
            return int(raw.strip())
        except Exception:
            return None
    return _read_openclaw_telegram_chat_id()


def _load_dotenv(path: str) -> None:
    # Minimal dotenv loader to support unattended cron runs (OpenClaw env).
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if not k:
                    continue
                # Strip optional quotes.
                if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                    v = v[1:-1]
                # Do not override explicit environment.
                if k not in os.environ or os.environ.get(k, "") == "":
                    os.environ[k] = v
    except Exception:
        return


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return dict(default)


def _save_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def _maybe_reconcile_risk_state(root: str, post: Dict[str, Any]) -> None:
    """If we have no open positions, clear stale per-market notional caps.

    This prevents old dry-run / legacy state from blocking new trades overnight.
    """
    try:
        if not isinstance(post, dict):
            return
        bal = post.get("balance") if isinstance(post.get("balance"), dict) else {}
        pv = float(bal.get("portfolio_value") or 0.0) if isinstance(bal, dict) else 0.0
        pos = post.get("positions") if isinstance(post.get("positions"), dict) else {}
        mp = pos.get("market_positions") if isinstance(pos.get("market_positions"), list) else []
        ep = pos.get("event_positions") if isinstance(pos.get("event_positions"), list) else []
        if pv != 0.0:
            return
        if mp or ep:
            return
        sp = os.path.join(root, "tmp", "kalshi_ref_arb", "state.json")
        try:
            with open(sp, "r", encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            return
        if not isinstance(st, dict):
            return
        if isinstance(st.get("markets"), dict) and st.get("markets"):
            st["markets"] = {}
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2, sort_keys=True)
                f.write("\n")
    except Exception:
        return


def _run_cmd_json(argv: list[str], *, cwd: str, timeout_s: int = 60) -> Tuple[int, str, Dict[str, Any]]:
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            return proc.returncode, stdout, json.loads(stdout)
        except Exception:
            pass
    return proc.returncode, stdout, {"raw_stdout": stdout, "raw_stderr": (proc.stderr or "").strip()}


def _send_telegram(chat_id: int, text: str, *, cwd: str) -> None:
    # Best-effort; do not raise.
    try:
        subprocess.run(
            ["bash", "-lc", f"scripts/telegram_send_message.sh {chat_id} {json.dumps(text)}"],
            cwd=cwd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return


def _list_run_files(runs_dir: str) -> list[str]:
    try:
        names = [n for n in os.listdir(runs_dir) if n.endswith(".json")]
    except Exception:
        return []
    paths = [os.path.join(runs_dir, n) for n in names]
    paths = [p for p in paths if os.path.isfile(p)]
    paths.sort()
    return paths


def _recent_run_health(runs_dir: str, *, lookback: int, min_ts_unix: int = 0) -> dict[str, int]:
    files = _list_run_files(runs_dir)
    if lookback > 0:
        files = files[-lookback:]
    errors = 0
    order_failed = 0
    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                o = json.load(f)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        if int(o.get("ts_unix") or 0) < int(min_ts_unix):
            continue
        bal_rc = int(o.get("balance_rc") or 0)
        trade_rc = int(o.get("trade_rc") or 0)
        post_rc = int(o.get("post_rc") or 0)
        trade = o.get("trade") if isinstance(o.get("trade"), dict) else {}
        refused = bool(trade.get("status") == "refused")
        reason = str(trade.get("reason") or "")
        gate_refused = refused and reason in ("kill_switch", "cooldown")
        if bal_rc != 0:
            errors += 1
        if post_rc != 0:
            errors += 1
        if (trade_rc != 0) and (not gate_refused):
            errors += 1
        skipped = trade.get("skipped") or []
        if isinstance(skipped, list):
            for s in skipped:
                if isinstance(s, dict) and s.get("reason") == "order_failed":
                    order_failed += 1
    return {"errors": errors, "order_failed": order_failed, "runs": len(files)}


def _kill_switch_path(root: str) -> str:
    # Single canonical kill switch path under the workspace root.
    return os.path.join(root, "tmp", "kalshi_ref_arb.KILL")


def _ensure_kill_switch(root: str) -> None:
    p = _kill_switch_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        with open(p, "a", encoding="utf-8"):
            pass
    except Exception:
        return


def _acquire_lock(root: str, *, ttl_s: int) -> bool:
    """Best-effort single-instance lock.

    Prevents overlapping cycles if a prior run is still in-flight.
    """
    lock_dir = os.path.join(root, "tmp", "kalshi_ref_arb")
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, "cycle.lock")
    now = int(time.time())

    try:
        if os.path.exists(lock_path):
            try:
                payload = json.load(open(lock_path, "r", encoding="utf-8"))
                ts = int(payload.get("ts_unix") or 0)
            except Exception:
                ts = 0
            if ts and (now - ts) < ttl_s:
                return False
    except Exception:
        # If we can't read it, still try to take it.
        pass

    try:
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump({"ts_unix": now, "pid": os.getpid()}, f)
            f.write("\n")
        return True
    except Exception:
        return True


def _release_lock(root: str) -> None:
    lock_path = os.path.join(root, "tmp", "kalshi_ref_arb", "cycle.lock")
    try:
        os.remove(lock_path)
    except Exception:
        return


def main() -> int:
    root = _repo_root()
    os.chdir(root)

    # Ensure unattended runs can see OpenClaw env vars (Kalshi creds, etc).
    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))

    if not _acquire_lock(root, ttl_s=int(os.environ.get("KALSHI_ARB_LOCK_TTL_S", "240"))):
        return 0

    try:
        ts = int(time.time())
        out_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "runs")
        notify_state_path = os.path.join(root, "tmp", "kalshi_ref_arb", "notify_state.json")
        notify_state = _load_json(notify_state_path, default={"last_notify_ts": 0})
        health_state_path = os.path.join(root, "tmp", "kalshi_ref_arb", "health_state.json")
        health_state = _load_json(health_state_path, default={"window_start_ts": 0, "last_run_had_error": False})

        # Closed-loop safety thresholds (evaluated post-run to avoid old transient errors re-tripping kill switch).
        lookback = int(os.environ.get("KALSHI_ARB_AUTO_PAUSE_LOOKBACK", "6"))
        max_err = int(os.environ.get("KALSHI_ARB_AUTO_PAUSE_MAX_ERRORS", "3"))
        max_of = int(os.environ.get("KALSHI_ARB_AUTO_PAUSE_MAX_ORDER_FAILED", "2"))

        # If a cooldown is active, do not run the trading step (prevents repeated errors from escalating to kill switch).
        if cooldown_active(RiskConfig(), root).get("active"):
            # Still write a run artifact so the digest can report cooldown periods.
            bal_rc, _, bal = _run_cmd_json(["python3", "scripts/kalshi_ref_arb.py", "balance"], cwd=root, timeout_s=30)
            post_rc, _, post = _run_cmd_json(
                ["python3", "scripts/kalshi_ref_arb.py", "portfolio", "--hours", "1", "--limit", "50"],
                cwd=root,
                timeout_s=60,
            )
            if post_rc == 0 and isinstance(post, dict):
                _maybe_reconcile_risk_state(root, post)
            artifact = {
                "ts_unix": ts,
                "cycle_inputs": {"cooldown_active": True},
                "balance_rc": bal_rc,
                "balance": bal,
                "trade_rc": 2,
                "trade": {"mode": "trade", "status": "refused", "reason": "cooldown"},
                "post_rc": post_rc,
                "post": post,
            }
            artifact_path = os.path.join(out_dir, f"{ts}.json")
            _save_json(artifact_path, artifact)
            return 0

        # Run balance first (auth check). If this fails, we want to know.
        bal_rc, _, bal = _run_cmd_json(["python3", "scripts/kalshi_ref_arb.py", "balance"], cwd=root, timeout_s=30)

        # Live trade (user-authorized) but still guarded by kill switch + risk caps in the bot.
        series = os.environ.get("KALSHI_ARB_SERIES", "KXBTC")
        sigma = os.environ.get("KALSHI_ARB_SIGMA", "auto")
        min_edge = os.environ.get("KALSHI_ARB_MIN_EDGE_BPS", "120")
        uncertainty = os.environ.get("KALSHI_ARB_UNCERTAINTY_BPS", "50")
        min_liq = os.environ.get("KALSHI_ARB_MIN_LIQUIDITY_USD", "200")
        max_spread = os.environ.get("KALSHI_ARB_MAX_SPREAD", "0.05")
        min_tte = os.environ.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY", "900")
        min_px = os.environ.get("KALSHI_ARB_MIN_PRICE", "0.05")
        max_px = os.environ.get("KALSHI_ARB_MAX_PRICE", "0.95")
        persist = os.environ.get("KALSHI_ARB_PERSISTENCE_CYCLES", "2")
        persist_win = os.environ.get("KALSHI_ARB_PERSISTENCE_WINDOW_MIN", "30")
        sizing_mode = os.environ.get("KALSHI_ARB_SIZING_MODE", "fixed")

        sigma_arg = sigma
        if str(sigma).strip().lower() == "auto":
            try:
                v = conservative_sigma_auto(series, window_hours=int(os.environ.get("KALSHI_ARB_SIGMA_WINDOW_H", "168")))
            except Exception:
                v = None
            if v is not None:
                sigma_arg = f"{float(v):.4f}"

        cycle_inputs = {
            "series": series,
            "sigma": str(sigma),
            "sigma_arg": str(sigma_arg),
            "sigma_window_h": int(os.environ.get("KALSHI_ARB_SIGMA_WINDOW_H", "168")),
            "min_edge_bps": float(min_edge),
            "uncertainty_bps": float(uncertainty),
            "min_liquidity_usd": float(min_liq),
            "max_spread": float(max_spread),
            "min_seconds_to_expiry": int(min_tte),
            "min_price": float(min_px),
            "max_price": float(max_px),
            "persistence_cycles": int(persist),
            "persistence_window_min": float(persist_win),
        }

        trade_argv = [
            "python3",
            "scripts/kalshi_ref_arb.py",
            "trade",
            "--series",
            series,
            "--limit",
            os.environ.get("KALSHI_ARB_LIMIT", "20"),
            "--sigma-annual",
            sigma_arg,
            "--min-edge-bps",
            min_edge,
            "--uncertainty-bps",
            uncertainty,
            "--min-liquidity-usd",
            min_liq,
            "--max-spread",
            max_spread,
            "--min-seconds-to-expiry",
            min_tte,
            "--min-price",
            min_px,
            "--max-price",
            max_px,
            "--persistence-cycles",
            persist,
            "--persistence-window-min",
            persist_win,
            "--sizing-mode",
            sizing_mode,
            "--allow-write",
            "--max-orders-per-run",
            os.environ.get("KALSHI_ARB_MAX_ORDERS_PER_RUN", "1"),
            "--max-contracts-per-order",
            os.environ.get("KALSHI_ARB_MAX_CONTRACTS_PER_ORDER", "1"),
            "--max-notional-per-run-usd",
            os.environ.get("KALSHI_ARB_MAX_NOTIONAL_PER_RUN_USD", "2"),
            "--max-notional-per-market-usd",
            os.environ.get("KALSHI_ARB_MAX_NOTIONAL_PER_MARKET_USD", "5"),
        ]

        trade_rc, _, trade = _run_cmd_json(trade_argv, cwd=root, timeout_s=90)

        # Post-trade portfolio snapshot: used to confirm fills/positions and power digests.
        post_rc, _, post = _run_cmd_json(
            ["python3", "scripts/kalshi_ref_arb.py", "portfolio", "--hours", "1", "--limit", "50"],
            cwd=root,
            timeout_s=60,
        )
        if post_rc == 0 and isinstance(post, dict):
            _maybe_reconcile_risk_state(root, post)

        # Persist run artifact.
        artifact = {
            "ts_unix": ts,
            "cycle_inputs": cycle_inputs,
            "balance_rc": bal_rc,
            "balance": bal,
            "trade_rc": trade_rc,
            "trade": trade,
            "post_rc": post_rc,
            "post": post,
        }
        artifact_path = os.path.join(out_dir, f"{ts}.json")
        _save_json(artifact_path, artifact)

        # Closed-loop learning: persist entry features + fills + settlements to a rolling ledger.
        try:
            if isinstance(trade, dict) and isinstance(post, dict):
                update_from_run(root, ts_unix=ts, trade=trade, post=post)
        except Exception:
            pass

        # Safety: cooldown after unexpected behavior, even if we don't hard-stop with kill switch.
        # This reduces repeated retries into a degraded API / degraded market.
        kill_refused = (
            isinstance(trade, dict)
            and trade.get("status") == "refused"
            and trade.get("reason") in ("kill_switch", "cooldown")
        )
        any_error = (bal_rc != 0) or ((trade_rc != 0) and (not kill_refused))
        if post_rc != 0:
            any_error = True
        any_order_failed = any(
            isinstance(x, dict) and x.get("reason") == "order_failed"
            for x in ((trade.get("skipped") or []) if isinstance(trade, dict) else [])
        )
        if any_error or any_order_failed:
            cfg = RiskConfig()
            cd = cooldown_active(cfg, root)
            if not bool(cd.get("active")):
                set_cooldown(
                    cfg,
                    root,
                    seconds=int(os.environ.get("KALSHI_ARB_COOLDOWN_S", "1800")),
                    reason=("cycle_error" if any_error else "order_failed"),
                )

        # Notify only on material events (orders placed or errors), rate-limited.
        chat_id = _telegram_chat_id()
        can_notify = chat_id is not None
        now = ts
        last = int(notify_state.get("last_notify_ts") or 0)
        rate_limit_s = int(os.environ.get("KALSHI_ARB_NOTIFY_MIN_INTERVAL_S", "900"))  # 15m
        allowed = (now - last) >= rate_limit_s

        placed = (trade.get("placed") or []) if isinstance(trade, dict) else []
        live_orders = [p for p in placed if isinstance(p, dict) and p.get("mode") == "live"]
        kill_refused = (
            isinstance(trade, dict)
            and trade.get("status") == "refused"
            and trade.get("reason") in ("kill_switch", "cooldown")
        )
        any_error = (bal_rc != 0) or ((trade_rc != 0) and (not kill_refused))
        if post_rc != 0:
            any_error = True
        any_order_failed = any(
            isinstance(x, dict) and x.get("reason") == "order_failed"
            for x in ((trade.get("skipped") or []) if isinstance(trade, dict) else [])
        )

        # Health window reset: once we recover from an error streak, don't let old transient errors re-trigger kill switch.
        prev_had_err = bool(health_state.get("last_run_had_error"))
        if (not any_error) and prev_had_err:
            health_state["window_start_ts"] = int(ts)
        health_state["last_run_had_error"] = bool(any_error)
        _save_json(health_state_path, health_state)

        # If the last N runs look unhealthy, pause trading by creating the kill switch.
        win_start = int(health_state.get("window_start_ts") or 0)
        health = _recent_run_health(out_dir, lookback=lookback, min_ts_unix=win_start)
        if health["runs"] >= lookback and (health["errors"] >= max_err or health["order_failed"] >= max_of):
            _ensure_kill_switch(root)

        # If we just auto-paused, notify once (rate-limited like other messages).
        kill_on = os.path.exists(_kill_switch_path(root))

        if can_notify and allowed and (live_orders or any_error or any_order_failed):
            parts = []
            if any_error:
                parts.append("Kalshi arb: ERROR running cycle")
            if live_orders:
                lo = live_orders[0]
                o = (lo.get("order") or {}) if isinstance(lo, dict) else {}
                filled_hint = ""
                try:
                    # If we have a post snapshot with fills, give a stronger signal.
                    order_id = lo.get("order_id") if isinstance(lo.get("order_id"), str) else None
                    if order_id and isinstance(post, dict):
                        m = match_fills_for_order(post, order_id)
                        if int(m.get("fills_count") or 0) > 0:
                            ap = m.get("avg_price_dollars")
                            if isinstance(ap, (int, float)):
                                filled_hint = f" (filled {int(m.get('fills_count') or 0)} @ ~{float(ap):.4f})"
                            else:
                                filled_hint = f" (filled {int(m.get('fills_count') or 0)})"
                    elif isinstance(post, dict):
                        fills = (post.get("fills") or {}).get("fills")
                        if isinstance(fills, list) and fills:
                            filled_hint = " (fill(s) detected)"
                except Exception:
                    filled_hint = ""
                parts.append(
                    f"Kalshi arb: placed {o.get('action')} {o.get('side')} {o.get('count')}x {o.get('ticker')} @ {o.get('price_dollars')} (~${lo.get('notional_usd')}){filled_hint}"
                )
            if not parts and any_order_failed:
                parts.append("Kalshi arb: order_failed (see tmp/kalshi_ref_arb/runs)")
            if not parts and kill_on and (health["runs"] >= lookback) and (health["errors"] >= max_err or health["order_failed"] >= max_of):
                parts.append("Kalshi arb: auto-paused (kill switch ON) due to repeated errors/order failures")
            msg = "\n".join(parts)
            _send_telegram(int(chat_id), msg, cwd=root)
            notify_state["last_notify_ts"] = now
            _save_json(notify_state_path, notify_state)
        return 0
    finally:
        _release_lock(root)


if __name__ == "__main__":
    raise SystemExit(main())
