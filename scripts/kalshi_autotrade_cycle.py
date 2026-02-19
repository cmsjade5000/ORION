#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional, Tuple

try:
    from scripts.arb.kalshi_analytics import match_fills_for_order  # type: ignore
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, set_cooldown  # type: ignore
    from scripts.arb.kalshi_runtime import load_runtime_from_env  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore
    from scripts.arb.kalshi_ledger import update_from_run  # type: ignore
    from scripts.arb.kalshi_autotune import apply_overrides_to_environ, load_overrides, maybe_autotune  # type: ignore
except ModuleNotFoundError:
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi_analytics import match_fills_for_order  # type: ignore
    from scripts.arb.risk import RiskConfig, RiskState, cooldown_active, set_cooldown  # type: ignore
    from scripts.arb.kalshi_runtime import load_runtime_from_env  # type: ignore
    from scripts.arb.vol import conservative_sigma_auto  # type: ignore
    from scripts.arb.kalshi_ledger import update_from_run  # type: ignore
    from scripts.arb.kalshi_autotune import apply_overrides_to_environ, load_overrides, maybe_autotune  # type: ignore


def _day_bounds_unix(*, tz: str, now_unix: int) -> tuple[int, int]:
    """Return [start, end) unix seconds for the local trading day in the given tz."""
    z = ZoneInfo(tz)
    dt = datetime.fromtimestamp(int(now_unix), tz=z)
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def _daily_realized_pnl_usd(repo_root: str, *, now_unix: int, tz: str = "America/New_York") -> Optional[float]:
    """Best-effort: sum attributed settlement cash deltas for today's settlements in the ledger."""
    try:
        from scripts.arb.kalshi_ledger import load_ledger  # type: ignore
    except Exception:
        return None

    try:
        led = load_ledger(repo_root)
    except Exception:
        return None
    orders = led.get("orders") if isinstance(led, dict) else None
    if not isinstance(orders, dict):
        return None

    start, end = _day_bounds_unix(tz=tz, now_unix=int(now_unix))
    pnl = 0.0
    any_seen = False
    for _, o in orders.items():
        if not isinstance(o, dict):
            continue
        st = o.get("settlement") if isinstance(o.get("settlement"), dict) else None
        if not isinstance(st, dict):
            continue
        ts_seen = int(st.get("ts_seen") or 0)
        if ts_seen < start or ts_seen >= end:
            continue
        parsed = st.get("parsed") if isinstance(st.get("parsed"), dict) else {}
        cd = parsed.get("cash_delta_usd")
        if isinstance(cd, (int, float)):
            pnl += float(cd)
            any_seen = True
    return float(pnl) if any_seen else 0.0


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
    def _try(p: str) -> bool:
        try:
            with open(os.path.expanduser(p), "r", encoding="utf-8") as f:
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
                    # For strategy parameters, ~/.openclaw/.env should be the source of truth
                    # even if the gateway process already has older exported values.
                    if k.startswith("KALSHI_ARB_"):
                        os.environ[k] = v
                        continue
                    # Do not override explicit environment for other keys.
                    if k not in os.environ or os.environ.get(k, "") == "":
                        os.environ[k] = v
            return True
        except Exception:
            return False

    if _try(path):
        return
    if os.path.expanduser(path) != os.path.expanduser("~/.openclaw/.env"):
        _try("~/.openclaw/.env")


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
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    try:
        os.replace(tmp, path)
    except Exception:
        # Best-effort fallback.
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, sort_keys=True)
                f.write("\n")
        except Exception:
            pass
        try:
            os.remove(tmp)
        except Exception:
            pass


def _write_cycle_status(root: str, *, status: str, detail: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    path = os.path.join(root, "tmp", "kalshi_ref_arb", "last_cycle_status.json")
    payload: Dict[str, Any] = {
        "ts_unix": int(time.time()),
        "status": str(status),
        "detail": str(detail),
    }
    if isinstance(extra, dict):
        payload.update(extra)
    _save_json(path, payload)


def _build_trade_argv(
    *,
    selected_series: str,
    sigma_arg: str,
    min_edge: str,
    uncertainty: str,
    min_liq: str,
    max_spread: str,
    min_tte: str,
    min_px: str,
    max_px: str,
    min_notional: str,
    min_notional_bypass: str,
    persist: str,
    persist_win: str,
    sizing_mode: str,
    kelly_fraction: str,
    kelly_cap_fraction: str,
    bayes_prior_k: str,
    bayes_obs_k_max: str,
    vol_anomaly: str,
    vol_anomaly_window_h: str,
    max_market_concentration_fraction: str,
    allow_live_writes: bool,
) -> list[str]:
    argv = [
        "python3",
        "scripts/kalshi_ref_arb.py",
        "trade",
        "--series",
        selected_series,
        "--limit",
        os.environ.get("KALSHI_ARB_LIMIT", "20"),
        "--sigma-annual",
        str(sigma_arg),
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
        "--min-notional-usd",
        min_notional,
        "--min-notional-bypass-edge-bps",
        min_notional_bypass,
        "--persistence-cycles",
        persist,
        "--persistence-window-min",
        persist_win,
        "--sizing-mode",
        sizing_mode,
        "--kelly-fraction",
        kelly_fraction,
        "--kelly-cap-fraction",
        kelly_cap_fraction,
        "--bayes-prior-k",
        bayes_prior_k,
        "--bayes-obs-k-max",
        bayes_obs_k_max,
        "--max-orders-per-run",
        os.environ.get("KALSHI_ARB_MAX_ORDERS_PER_RUN", "1"),
        "--max-contracts-per-order",
        os.environ.get("KALSHI_ARB_MAX_CONTRACTS_PER_ORDER", "1"),
        "--max-notional-per-run-usd",
        os.environ.get("KALSHI_ARB_MAX_NOTIONAL_PER_RUN_USD", "2"),
        "--max-notional-per-market-usd",
        os.environ.get("KALSHI_ARB_MAX_NOTIONAL_PER_MARKET_USD", "5"),
        "--max-open-contracts-per-ticker",
        os.environ.get("KALSHI_ARB_MAX_OPEN_CONTRACTS_PER_TICKER", "2"),
        "--max-market-concentration-fraction",
        str(max_market_concentration_fraction),
    ]
    if allow_live_writes:
        argv.append("--allow-write")
    if str(vol_anomaly).strip().lower() in ("1", "true", "yes", "y", "on"):
        argv.extend(["--vol-anomaly", "--vol-anomaly-window-h", str(vol_anomaly_window_h)])
    return argv


def _write_prom_metrics(root: str, *, metrics_path: str, enabled: bool, artifact: Dict[str, Any]) -> None:
    if not enabled:
        return
    path = str(metrics_path).strip()
    if not path:
        return
    if not os.path.isabs(path):
        path = os.path.join(root, path)
    try:
        ts = int(artifact.get("ts_unix") or int(time.time()))
        bal_rc = int(artifact.get("balance_rc") or 0)
        trade_rc = int(artifact.get("trade_rc") or 0)
        post_rc = int(artifact.get("post_rc") or 0)
        trade = artifact.get("trade") if isinstance(artifact.get("trade"), dict) else {}
        placed = trade.get("placed") if isinstance(trade.get("placed"), list) else []
        live_orders = sum(1 for p in placed if isinstance(p, dict) and p.get("mode") == "live")
        skipped = trade.get("skipped") if isinstance(trade.get("skipped"), list) else []
        order_failed = sum(1 for s in skipped if isinstance(s, dict) and s.get("reason") == "order_failed")
        scan_failed = 1 if (str(trade.get("status") or "") == "refused" and str(trade.get("reason") or "") == "scan_failed") else 0
        allow_write = 1 if bool(((artifact.get("cycle_inputs") or {}).get("allow_live_writes"))) else 0

        lines = [
            "# HELP kalshi_cycle_last_ts_unix Last cycle timestamp.",
            "# TYPE kalshi_cycle_last_ts_unix gauge",
            f"kalshi_cycle_last_ts_unix {ts}",
            "# HELP kalshi_cycle_balance_rc Last balance command rc.",
            "# TYPE kalshi_cycle_balance_rc gauge",
            f"kalshi_cycle_balance_rc {bal_rc}",
            "# HELP kalshi_cycle_trade_rc Last trade command rc.",
            "# TYPE kalshi_cycle_trade_rc gauge",
            f"kalshi_cycle_trade_rc {trade_rc}",
            "# HELP kalshi_cycle_post_rc Last post snapshot rc.",
            "# TYPE kalshi_cycle_post_rc gauge",
            f"kalshi_cycle_post_rc {post_rc}",
            "# HELP kalshi_cycle_live_orders Last cycle live orders count.",
            "# TYPE kalshi_cycle_live_orders gauge",
            f"kalshi_cycle_live_orders {int(live_orders)}",
            "# HELP kalshi_cycle_order_failed Last cycle order_failed skips.",
            "# TYPE kalshi_cycle_order_failed gauge",
            f"kalshi_cycle_order_failed {int(order_failed)}",
            "# HELP kalshi_cycle_scan_failed Last cycle scan_failed indicator.",
            "# TYPE kalshi_cycle_scan_failed gauge",
            f"kalshi_cycle_scan_failed {int(scan_failed)}",
            "# HELP kalshi_cycle_allow_live_writes Last cycle write-arm state.",
            "# TYPE kalshi_cycle_allow_live_writes gauge",
            f"kalshi_cycle_allow_live_writes {int(allow_write)}",
        ]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except Exception:
        return


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
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "").strip() if isinstance(e.stdout, str) else ""
        stderr = (e.stderr or "").strip() if isinstance(e.stderr, str) else ""
        return 124, stdout, {"raw_stdout": stdout, "raw_stderr": stderr, "error": "timeout", "timeout_s": int(timeout_s)}
    except Exception as e:
        return 1, "", {"raw_stdout": "", "raw_stderr": str(e), "error": "exception"}

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
        # Avoid `bash -lc "...$..."` here: dollar signs in the text would be expanded
        # by the shell (e.g. "$0.76" -> "bash.76"). Pass args directly instead.
        subprocess.run(
            ["bash", "scripts/telegram_send_message.sh", str(int(chat_id)), str(text)],
            cwd=cwd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception:
        return


def _truthy_env(name: str, default: str = "0") -> bool:
    v = str(os.environ.get(name, default) or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _fmt_usd(x: Any) -> str:
    try:
        return f"${float(x):.2f}"
    except Exception:
        return "$?"


def _fmt_price_dollars(x: Any) -> str:
    try:
        return f"{float(x):.4f}"
    except Exception:
        return "?"


def _orion_order_sentence(lo: dict[str, Any], post: Any) -> str:
    o = (lo.get("order") or {}) if isinstance(lo.get("order"), dict) else {}
    action = str(o.get("action") or "buy")
    side = str(o.get("side") or "").lower()  # yes/no
    count = o.get("count") or o.get("initial_count") or lo.get("count") or "?"
    ticker = str(o.get("ticker") or lo.get("ticker") or "?")
    price = o.get("price_dollars")
    notional = lo.get("notional_usd")

    # Human phrasing.
    side_word = "YES" if side == "yes" else ("NO" if side == "no" else side.upper() or "?")
    verb = "placed" if action != "buy" else "placed"
    line = f"ORION: I {verb} a {action} order: {side_word} {count}x {ticker} @ { _fmt_price_dollars(price) } (~{_fmt_usd(notional)})"

    # Fill hint if we can match fills quickly.
    filled_hint = ""
    try:
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

    return line + filled_hint


def _list_run_files(runs_dir: str) -> list[str]:
    try:
        names = [n for n in os.listdir(runs_dir) if n.endswith(".json")]
    except Exception:
        return []
    paths = [os.path.join(runs_dir, n) for n in names]
    paths = [p for p in paths if os.path.isfile(p)]
    paths.sort()
    return paths


def _is_transient_http_err_payload(payload: Any) -> bool:
    """Heuristic for short-lived infra/API errors we should not escalate.

    We still record these in run artifacts and digests, but we avoid triggering
    cooldown/kill-switch behavior off them.
    """
    if not isinstance(payload, dict):
        return False
    s = payload.get("raw_stderr")
    if not isinstance(s, str) or not s:
        return False
    return any(
        x in s
        for x in (
            "HTTP Error 502",
            "HTTP Error 503",
            "HTTP Error 504",
            "timed out",
            "Temporary failure",
            "Connection reset",
            "Connection refused",
            "Name or service not known",
        )
    )


def _cycle_outcome_flags(*, bal_rc: int, bal: Any, post_rc: int, post: Any, trade_rc: int, trade: Any) -> Dict[str, bool]:
    kill_refused = (
        isinstance(trade, dict)
        and trade.get("status") == "refused"
        and trade.get("reason") in ("kill_switch", "cooldown")
    )
    bal_hard_err = (int(bal_rc) != 0) and (not _is_transient_http_err_payload(bal))
    post_hard_err = (int(post_rc) != 0) and (not _is_transient_http_err_payload(post))
    trade_hard_err = (int(trade_rc) != 0) and (not kill_refused)
    any_error = bool(bal_hard_err or post_hard_err or trade_hard_err)
    any_soft_err = bool((int(bal_rc) != 0) or (int(post_rc) != 0)) and (not any_error)
    any_order_failed = any(
        isinstance(x, dict) and x.get("reason") == "order_failed"
        for x in ((trade.get("skipped") or []) if isinstance(trade, dict) else [])
    )
    return {
        "kill_refused": bool(kill_refused),
        "any_error": bool(any_error),
        "any_soft_err": bool(any_soft_err),
        "any_order_failed": bool(any_order_failed),
    }


def _milestone_notification_text(
    *,
    any_error: bool,
    any_soft_err: bool,
    any_order_failed: bool,
    milestone_notify: bool,
    notify_trades: bool,
    live_orders: list[dict[str, Any]],
    post: Any,
    auto_paused: bool,
) -> str:
    parts: list[str] = []
    if any_error:
        parts = [
            "Status: Testing",
            "What changed:",
            "- Cycle hit a hard error and entered cooldown protections.",
            "Why it matters:",
            "This prevents repeated bad writes during unstable API/network windows.",
            "Risks / notes:",
            "- Check tmp/kalshi_ref_arb/runs for exact command failure context.",
            "Next step: I will retry on the next scheduled cycle.",
        ]
    elif any_soft_err:
        parts = [
            "Status: Testing",
            "What changed:",
            "- Transient Kalshi/API issue detected; no risky action taken.",
            "Why it matters:",
            "Bot stayed safe and preserved capital while connectivity recovered.",
            "Risks / notes:",
            "- If repeated, I will escalate to cooldown/kill-switch protections.",
            "Next step: Retry automatically on next cycle.",
        ]
    elif any_order_failed:
        parts = [
            "Status: Testing",
            "What changed:",
            "- Order attempt failed validation/rejection path.",
            "Why it matters:",
            "Execution safeguards blocked a low-quality or invalid trade path.",
            "Risks / notes:",
            "- Review latest run artifact for reason=order_failed.",
            "Next step: Continue scanning; trade only when constraints pass.",
        ]
    elif (not milestone_notify) and live_orders and notify_trades:
        parts.append(_orion_order_sentence(live_orders[0], post))

    if (not parts) and auto_paused:
        parts = [
            "Status: Testing",
            "What changed:",
            "- Kill switch auto-enabled after repeated error threshold.",
            "Why it matters:",
            "Trading is paused to contain risk and prevent cascading failures.",
            "Risks / notes:",
            "- Manual review needed before re-arming writes.",
            "Next step: Investigate latest run artifacts and re-enable safely.",
        ]
    return "\n".join(parts)


def _recent_run_health(runs_dir: str, *, lookback: int, min_ts_unix: int = 0) -> dict[str, int]:
    files = _list_run_files(runs_dir)
    if lookback > 0:
        files = files[-lookback:]
    errors = 0
    order_failed = 0
    considered = 0

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
        considered += 1
        bal_rc = int(o.get("balance_rc") or 0)
        trade_rc = int(o.get("trade_rc") or 0)
        post_rc = int(o.get("post_rc") or 0)
        bal_payload = o.get("balance")
        post_payload = o.get("post")
        trade = o.get("trade") if isinstance(o.get("trade"), dict) else {}
        refused = bool(trade.get("status") == "refused")
        reason = str(trade.get("reason") or "")
        # Refusals are not necessarily "errors". Treat operator-style stop gates as healthy.
        gate_refused = refused and reason in ("kill_switch", "cooldown", "scan_failed", "daily_loss_limit")
        if bal_rc != 0 and not _is_transient_http_err_payload(bal_payload):
            errors += 1
        if post_rc != 0 and not _is_transient_http_err_payload(post_payload):
            errors += 1
        if (trade_rc != 0) and (not gate_refused):
            errors += 1
        skipped = trade.get("skipped") or []
        if isinstance(skipped, list):
            for s in skipped:
                if isinstance(s, dict) and s.get("reason") == "order_failed":
                    order_failed += 1
    return {"errors": errors, "order_failed": order_failed, "runs": int(considered)}


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
        # If we can't take a lock, skip the cycle (safer than overlapping).
        return False


def _record_observations_from_scan(root: str, scan_obj: Dict[str, Any], *, ts_unix: int) -> None:
    """Record edge observations from scan output into RiskState in one place."""
    try:
        state = RiskState(os.path.join(root, "tmp", "kalshi_ref_arb", "state.json"))
        sigs = scan_obj.get("signals") if isinstance(scan_obj, dict) else None
        if not isinstance(sigs, list):
            return
        for it in sigs:
            if not isinstance(it, dict):
                continue
            t = it.get("ticker")
            if not isinstance(t, str) or not t:
                continue
            rec = it.get("recommended")
            if not isinstance(rec, dict):
                continue
            side = rec.get("side")
            if side not in ("yes", "no"):
                continue
            eff = rec.get("effective_edge_bps") if rec.get("effective_edge_bps") is not None else rec.get("edge_bps")
            try:
                eb = float(eff)
            except Exception:
                continue
            state.record_observation(f"{t}:{side}", edge_bps=eb, ts_unix=int(ts_unix))
        state.save()
    except Exception:
        return


def _release_lock(root: str) -> None:
    lock_path = os.path.join(root, "tmp", "kalshi_ref_arb", "cycle.lock")
    try:
        os.remove(lock_path)
    except Exception:
        return


def _parse_series_list(raw: str) -> list[str]:
    # Accept comma/space-separated series tickers.
    parts: list[str] = []
    for chunk in str(raw or "").replace(";", ",").split(","):
        for p in chunk.strip().split():
            if p.strip():
                parts.append(p.strip().upper())
    # De-dupe preserving order.
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _best_series_from_scan(root: str, series_list: list[str], *, sigma: str, sigma_window_h: int, min_edge: str, uncertainty: str, min_liq: str, max_spread: str, min_tte: str, min_px: str, max_px: str) -> tuple[str, dict[str, Any]]:
    """Pick a single series to trade this cycle based on scan results (no state writes)."""
    best_series = series_list[0] if series_list else "KXBTC"
    best_eff = None
    summary: dict[str, Any] = {"series": []}

    for s in series_list:
        sigma_arg = sigma
        if str(sigma).strip().lower() == "auto":
            try:
                v = conservative_sigma_auto(s, window_hours=int(sigma_window_h))
            except Exception:
                v = None
            if v is not None:
                sigma_arg = f"{float(v):.4f}"
        argv = [
            "python3",
            "scripts/kalshi_ref_arb.py",
            "scan",
            "--series",
            s,
            "--limit",
            os.environ.get("KALSHI_ARB_LIMIT", "20"),
            "--sigma-annual",
            str(sigma_arg),
            "--min-edge-bps",
            str(min_edge),
            "--uncertainty-bps",
            str(uncertainty),
            "--min-liquidity-usd",
            str(min_liq),
            "--max-spread",
            str(max_spread),
            "--min-seconds-to-expiry",
            str(min_tte),
            "--min-price",
            str(min_px),
            "--max-price",
            str(max_px),
            "--min-notional-usd",
            str(os.environ.get("KALSHI_ARB_MIN_NOTIONAL_USD", "0.20")),
            "--min-notional-bypass-edge-bps",
            str(os.environ.get("KALSHI_ARB_MIN_NOTIONAL_BYPASS_EDGE_BPS", "4000")),
        ]
        rc, _, obj = _run_cmd_json(argv, cwd=root, timeout_s=60)
        best = None
        try:
            sigs = obj.get("signals") if isinstance(obj, dict) else []
            if isinstance(sigs, list):
                for it in sigs:
                    if not isinstance(it, dict):
                        continue
                    rec = it.get("recommended")
                    if not isinstance(rec, dict):
                        continue
                    eff = rec.get("effective_edge_bps") if rec.get("effective_edge_bps") is not None else rec.get("edge_bps")
                    try:
                        eff_f = float(eff)
                    except Exception:
                        continue
                    if best is None or eff_f > float(best.get("effective_edge_bps") or -1e9):
                        best = {
                            "ticker": it.get("ticker"),
                            "side": rec.get("side"),
                            "limit_price": rec.get("limit_price"),
                            "effective_edge_bps": eff_f,
                        }
        except Exception:
            best = None

        summary["series"].append({"series": s, "rc": int(rc), "best": best, "sigma_arg": str(sigma_arg)})
        if best is not None:
            if best_eff is None or float(best["effective_edge_bps"]) > float(best_eff):
                best_eff = float(best["effective_edge_bps"])
                best_series = s

    summary["selected_series"] = best_series
    summary["selected_effective_edge_bps"] = best_eff
    return best_series, summary


def _scan_series(
    root: str,
    series: str,
    *,
    sigma: str,
    sigma_window_h: int,
    min_edge: str,
    uncertainty: str,
    min_liq: str,
    max_spread: str,
    min_tte: str,
    min_px: str,
    max_px: str,
    min_notional: str,
    min_notional_bypass: str,
) -> Dict[str, Any]:
    sigma_arg = sigma
    if str(sigma).strip().lower() == "auto":
        try:
            v = conservative_sigma_auto(series, window_hours=int(sigma_window_h))
        except Exception:
            v = None
        if v is not None:
            sigma_arg = f"{float(v):.4f}"

    argv = [
        "python3",
        "scripts/kalshi_ref_arb.py",
        "scan",
        "--series",
        series,
        "--limit",
        os.environ.get("KALSHI_ARB_LIMIT", "20"),
        "--sigma-annual",
        str(sigma_arg),
        "--min-edge-bps",
        str(min_edge),
        "--uncertainty-bps",
        str(uncertainty),
        "--min-liquidity-usd",
        str(min_liq),
        "--max-spread",
        str(max_spread),
        "--min-seconds-to-expiry",
        str(min_tte),
        "--min-price",
        str(min_px),
        "--max-price",
        str(max_px),
        "--min-notional-usd",
        str(min_notional),
        "--min-notional-bypass-edge-bps",
        str(min_notional_bypass),
    ]
    scan_timeout_s = int(os.environ.get("KALSHI_ARB_SCAN_TIMEOUT_S", "30"))
    rc, _, obj = _run_cmd_json(argv, cwd=root, timeout_s=scan_timeout_s)
    out = obj if isinstance(obj, dict) else {"raw": obj}
    out["_rc"] = int(rc)
    out["_sigma_arg"] = str(sigma_arg)
    try:
        rs = out.get("raw_stderr")
        if isinstance(rs, str) and rs.strip():
            out["_stderr_head"] = rs.strip().replace("\n", " ")[:160]
    except Exception:
        pass
    out.setdefault("inputs", {})
    if isinstance(out.get("inputs"), dict):
        out["inputs"].setdefault("series", series)
        out["inputs"].setdefault("sigma_annual", sigma_arg)
        # Spot is required for meaningful scan; capture it explicitly for diagnostics.
        out["_spot_ref"] = out["inputs"].get("spot_ref")
        out["_spot_ok"] = bool(isinstance(out.get("_spot_ref"), (int, float)) and float(out.get("_spot_ref")) > 0.0)
    # If scan ran but had no spot, treat it as a soft failure so the cycle can skip series cleanly.
    try:
        if int(out.get("_rc") or 0) == 0 and (not bool(out.get("_spot_ok"))):
            out["_rc"] = 1
            out["_rc_reason"] = "missing_spot_ref"
    except Exception:
        pass
    return out


def _best_candidate_from_scan(scan_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    best = None
    sigs = scan_obj.get("signals") if isinstance(scan_obj, dict) else None
    if not isinstance(sigs, list):
        return None
    recommended_count = 0
    for it in sigs:
        if not isinstance(it, dict):
            continue
        rec = it.get("recommended")
        if not isinstance(rec, dict):
            continue
        recommended_count += 1
        eff = rec.get("effective_edge_bps") if rec.get("effective_edge_bps") is not None else rec.get("edge_bps")
        try:
            eff_f = float(eff)
        except Exception:
            continue
        filters = it.get("filters") if isinstance(it.get("filters"), dict) else {}
        t_years = it.get("t_years")
        try:
            tte_s = float(t_years) * 365.0 * 24.0 * 3600.0 if isinstance(t_years, (int, float)) else None
        except Exception:
            tte_s = None
        cand = {
            "ticker": it.get("ticker"),
            "side": rec.get("side"),
            "limit_price": rec.get("limit_price"),
            "effective_edge_bps": eff_f,
            "edge_threshold_bps": rec.get("edge_threshold_bps"),
            "liquidity_dollars": filters.get("liquidity_dollars"),
            "spread": filters.get("yes_spread" if rec.get("side") == "yes" else "no_spread"),
            "tte_s": tte_s,
            "regime_bucket": it.get("regime_bucket"),
            "ref_quote_age_sec": filters.get("ref_quote_age_sec"),
        }
        if best is None or float(cand["effective_edge_bps"]) > float(best.get("effective_edge_bps") or -1e9):
            best = cand
    if isinstance(best, dict):
        best["recommended_count"] = int(recommended_count)
    return best


def main() -> int:
    root = _repo_root()
    os.chdir(root)

    # Ensure unattended runs can see OpenClaw env vars (Kalshi creds, etc).
    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))
    rt_cfg, rt_errs = load_runtime_from_env(repo_root=root)

    if not _acquire_lock(root, ttl_s=int(os.environ.get("KALSHI_ARB_LOCK_TTL_S", "240"))):
        _write_cycle_status(
            root,
            status="skipped_lock",
            detail="cycle lock held by another run",
            extra={
                "runtime": rt_cfg.as_dict(),
                "runtime_errors": rt_errs,
            },
        )
        return 0

    try:
        ts = int(time.time())
        _write_cycle_status(
            root,
            status="running",
            detail="cycle started",
            extra={"runtime": rt_cfg.as_dict(), "runtime_errors": rt_errs},
        )
        # Auto-tune status is captured into run artifacts for visibility.
        autotune_status: Optional[Dict[str, Any]] = None

        # Apply any persisted param overrides (written by the auto-tuner) and then
        # optionally run auto-tune. Keep this inside the cycle lock to avoid
        # overlapping cycles racing on override files.
        try:
            apply_overrides_to_environ(load_overrides(root))
        except Exception:
            pass
        try:
            autotune_status = maybe_autotune(root)
        except Exception:
            autotune_status = None

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
                "cycle_inputs": {
                    "cooldown_active": True,
                    "autotune": autotune_status,
                    "runtime": rt_cfg.as_dict(),
                    "runtime_errors": rt_errs,
                    "allow_live_writes": bool(rt_cfg.allow_live_writes),
                },
                "balance_rc": bal_rc,
                "balance": bal,
                "trade_rc": 2,
                "trade": {"mode": "trade", "status": "refused", "reason": "cooldown"},
                "post_rc": post_rc,
                "post": post,
            }
            artifact_path = os.path.join(out_dir, f"{ts}.json")
            _save_json(artifact_path, artifact)
            _write_prom_metrics(root, metrics_path=rt_cfg.metrics_path, enabled=bool(rt_cfg.metrics_enabled), artifact=artifact)
            _write_cycle_status(root, status="cooldown_active", detail="trade refused due to cooldown", extra={"artifact": artifact_path})
            return 0

        # Run balance first (auth check). If this fails, we want to know.
        bal_rc, _, bal = _run_cmd_json(["python3", "scripts/kalshi_ref_arb.py", "balance"], cwd=root, timeout_s=30)

        # Daily loss gate (best-effort, local ledger): if exceeded, cooldown until tomorrow.
        try:
            limit = float(os.environ.get("KALSHI_ARB_DAILY_LOSS_LIMIT_USD", "10") or 0.0)
        except Exception:
            limit = 0.0
        if limit > 0.0:
            pnl_today = _daily_realized_pnl_usd(root, now_unix=ts, tz="America/New_York")
            if isinstance(pnl_today, (int, float)) and float(pnl_today) <= -float(limit):
                # Cooldown until next local midnight.
                try:
                    _, end = _day_bounds_unix(tz="America/New_York", now_unix=ts)
                    seconds = max(60, int(end - ts))
                except Exception:
                    seconds = int(os.environ.get("KALSHI_ARB_COOLDOWN_S", "1800"))
                set_cooldown(RiskConfig(), root, seconds=seconds, reason="daily_loss_limit")
                post_rc, _, post = _run_cmd_json(
                    ["python3", "scripts/kalshi_ref_arb.py", "portfolio", "--hours", "1", "--limit", "50"],
                    cwd=root,
                    timeout_s=60,
                )
                if post_rc == 0 and isinstance(post, dict):
                    _maybe_reconcile_risk_state(root, post)
                artifact = {
                    "ts_unix": ts,
                    "cycle_inputs": {
                        "daily_loss_limit_usd": float(limit),
                        "pnl_today_usd_approx": float(pnl_today),
                        "autotune": autotune_status,
                        "runtime": rt_cfg.as_dict(),
                        "runtime_errors": rt_errs,
                        "allow_live_writes": bool(rt_cfg.allow_live_writes),
                    },
                    "balance_rc": bal_rc,
                    "balance": bal,
                    "trade_rc": 2,
                    "trade": {"mode": "trade", "status": "refused", "reason": "daily_loss_limit", "pnl_today_usd_approx": float(pnl_today)},
                    "post_rc": post_rc,
                    "post": post,
                }
                artifact_path = os.path.join(out_dir, f"{ts}.json")
                _save_json(artifact_path, artifact)
                _write_prom_metrics(root, metrics_path=rt_cfg.metrics_path, enabled=bool(rt_cfg.metrics_enabled), artifact=artifact)
                _write_cycle_status(root, status="daily_loss_limit", detail="trade refused by daily loss gate", extra={"artifact": artifact_path})
                return 0
        else:
            pnl_today = None

        # Live trade (user-authorized) but still guarded by kill switch + risk caps in the bot.
        series_raw = os.environ.get("KALSHI_ARB_SERIES", "KXBTC")
        series_list = _parse_series_list(series_raw) or ["KXBTC"]
        sigma = os.environ.get("KALSHI_ARB_SIGMA", "auto")
        min_edge = os.environ.get("KALSHI_ARB_MIN_EDGE_BPS", "120")
        uncertainty = os.environ.get("KALSHI_ARB_UNCERTAINTY_BPS", "50")
        min_liq = os.environ.get("KALSHI_ARB_MIN_LIQUIDITY_USD", "200")
        max_spread = os.environ.get("KALSHI_ARB_MAX_SPREAD", "0.05")
        min_tte = os.environ.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY", "900")
        min_px = os.environ.get("KALSHI_ARB_MIN_PRICE", "0.05")
        max_px = os.environ.get("KALSHI_ARB_MAX_PRICE", "0.95")
        min_notional = os.environ.get("KALSHI_ARB_MIN_NOTIONAL_USD", "0.20")
        min_notional_bypass = os.environ.get("KALSHI_ARB_MIN_NOTIONAL_BYPASS_EDGE_BPS", "4000")
        persist = os.environ.get("KALSHI_ARB_PERSISTENCE_CYCLES", "2")
        persist_win = os.environ.get("KALSHI_ARB_PERSISTENCE_WINDOW_MIN", "30")
        sizing_mode = os.environ.get("KALSHI_ARB_SIZING_MODE", "fixed")
        kelly_fraction = os.environ.get("KALSHI_ARB_KELLY_FRACTION", "0.10")
        kelly_cap_fraction = os.environ.get("KALSHI_ARB_KELLY_CAP_FRACTION", "0.10")
        bayes_prior_k = os.environ.get("KALSHI_ARB_BAYES_PRIOR_K", "20")
        bayes_obs_k_max = os.environ.get("KALSHI_ARB_BAYES_OBS_K_MAX", "30")
        vol_anomaly = os.environ.get("KALSHI_ARB_VOL_ANOMALY", "0")
        vol_anomaly_window_h = os.environ.get("KALSHI_ARB_VOL_ANOMALY_WINDOW_H", "24")
        sigma_window_h = int(os.environ.get("KALSHI_ARB_SIGMA_WINDOW_H", "168"))
        max_market_concentration_fraction = str(rt_cfg.max_market_concentration_fraction)
        try:
            select_min_liq = float(os.environ.get("KALSHI_ARB_SCAN_SELECT_MIN_LIQUIDITY_USD", min_liq) or min_liq)
        except Exception:
            select_min_liq = float(min_liq)
        try:
            select_max_spread = float(os.environ.get("KALSHI_ARB_SCAN_SELECT_MAX_SPREAD", max_spread) or max_spread)
        except Exception:
            select_max_spread = float(max_spread)
        try:
            select_min_tte = float(os.environ.get("KALSHI_ARB_SCAN_SELECT_MIN_TTE_S", min_tte) or min_tte)
        except Exception:
            select_min_tte = float(min_tte)
        try:
            select_min_candidates = int(os.environ.get("KALSHI_ARB_SCAN_SELECT_MIN_CANDIDATES", "1") or 1)
        except Exception:
            select_min_candidates = 1
        try:
            select_depth_weight = float(os.environ.get("KALSHI_ARB_SCAN_SELECT_DEPTH_WEIGHT", "5.0") or 5.0)
        except Exception:
            select_depth_weight = 5.0

        # Scan each series once, pick the best, then trade only the selected series.
        scans_by_series: Dict[str, Any] = {}
        scan_summary: Dict[str, Any] = {"series": []}
        selected_series = series_list[0]
        selected_eff = None
        selected_score = None
        selected_eligible = False
        for s in series_list:
            sobj = _scan_series(
                root,
                s,
                sigma=sigma,
                sigma_window_h=sigma_window_h,
                min_edge=min_edge,
                uncertainty=uncertainty,
                min_liq=min_liq,
                max_spread=max_spread,
                min_tte=min_tte,
                min_px=min_px,
                max_px=max_px,
                min_notional=min_notional,
                min_notional_bypass=min_notional_bypass,
            )
            rc = int(sobj.get("_rc") or 0) if isinstance(sobj, dict) else 1
            best = _best_candidate_from_scan(sobj) if rc == 0 else None
            scans_by_series[s] = sobj
            rec_count = int(best.get("recommended_count") or 0) if isinstance(best, dict) else 0
            liq = float(best.get("liquidity_dollars") or 0.0) if isinstance(best, dict) and best.get("liquidity_dollars") is not None else None
            spr = float(best.get("spread")) if isinstance(best, dict) and best.get("spread") is not None else None
            tte = float(best.get("tte_s")) if isinstance(best, dict) and best.get("tte_s") is not None else None
            eligible = bool(best is not None)
            if eligible and rec_count < int(select_min_candidates):
                eligible = False
            if eligible and isinstance(liq, (int, float)) and float(liq) < float(select_min_liq):
                eligible = False
            if eligible and isinstance(spr, (int, float)) and float(spr) > float(select_max_spread):
                eligible = False
            if eligible and isinstance(tte, (int, float)) and float(tte) < float(select_min_tte):
                eligible = False
            score = None
            if isinstance(best, dict):
                try:
                    score = float(best.get("effective_edge_bps") or 0.0) + float(select_depth_weight) * (float(rec_count) ** 0.5)
                except Exception:
                    score = None
            scan_summary["series"].append(
                {
                    "series": s,
                    "rc": int(sobj.get("_rc") or 0),
                    "rc_reason": str(sobj.get("_rc_reason") or ""),
                    "stderr_head": str(sobj.get("_stderr_head") or ""),
                    "best": best,
                    "eligible_for_selection": bool(eligible),
                    "selection_score": float(score) if isinstance(score, (int, float)) else None,
                    "selection_filters": {
                        "min_liquidity_usd": float(select_min_liq),
                        "max_spread": float(select_max_spread),
                        "min_tte_s": float(select_min_tte),
                        "min_candidates": int(select_min_candidates),
                    },
                    "sigma_arg": str(sobj.get("_sigma_arg") or ""),
                    "spot_ok": bool(sobj.get("_spot_ok")),
                }
            )
            if best is not None and not selected_eligible:
                eff_f = float(best.get("effective_edge_bps") or 0.0)
                if selected_eff is None or eff_f > float(selected_eff):
                    selected_eff = eff_f
                    selected_series = s
            if bool(eligible) and isinstance(score, (int, float)):
                if (not selected_eligible) or (selected_score is None) or (float(score) > float(selected_score)):
                    selected_eligible = True
                    selected_score = float(score)
                    selected_eff = float(best.get("effective_edge_bps") or 0.0)
                    selected_series = s
        scan_summary["selected_series"] = selected_series
        scan_summary["selected_effective_edge_bps"] = selected_eff
        scan_summary["selected_score"] = selected_score
        scan_summary["selected_eligible"] = bool(selected_eligible)

        # If *all* scans failed (timeouts/errors), skip trading this cycle rather than
        # blindly defaulting to the first series.
        #
        # Important: `selected_eff is None` can also mean "scan succeeded but no market
        # passed the filters" (i.e., no opportunity). In that case we still run the
        # trade step for the selected series so we get diagnostics in the run artifact
        # (why no trades), and we remain ready if the market changes between scan/trade.
        any_scan_ok = False
        try:
            for it in (scan_summary.get("series") or []):
                if not isinstance(it, dict):
                    continue
                if int(it.get("rc") or 0) == 0:
                    any_scan_ok = True
                    break
        except Exception:
            any_scan_ok = False

        if not any_scan_ok:
            # Notify ORION on repeated scan failures (avoid silent death).
            try:
                lines = []
                for it in (scan_summary.get("series") or [])[:10]:
                    if not isinstance(it, dict):
                        continue
                    s = it.get("series")
                    rc = int(it.get("rc") or 0)
                    rsn = str(it.get("rc_reason") or "")
                    if rc != 0:
                        tail = f" ({rsn})" if rsn else ""
                        lines.append(f"{s}: rc={rc}{tail}")
                if lines:
                    health_state["last_run_had_error"] = True
                    _save_json(health_state_path, health_state)
            except Exception:
                pass
            post_rc, _, post = _run_cmd_json(
                ["python3", "scripts/kalshi_ref_arb.py", "portfolio", "--hours", "1", "--limit", "50"],
                cwd=root,
                timeout_s=60,
            )
            if post_rc == 0 and isinstance(post, dict):
                _maybe_reconcile_risk_state(root, post)
            artifact = {
                "ts_unix": ts,
                "cycle_inputs": {
                    "series_list": series_list,
                    "scan_summary": scan_summary,
                    "daily_loss_limit_usd": float(limit) if limit > 0 else 0.0,
                    "pnl_today_usd_approx": float(pnl_today) if isinstance(pnl_today, (int, float)) else None,
                    "autotune": autotune_status,
                    "runtime": rt_cfg.as_dict(),
                    "runtime_errors": rt_errs,
                    "allow_live_writes": bool(rt_cfg.allow_live_writes),
                },
                "balance_rc": bal_rc,
                "balance": bal,
                "trade_rc": 2,
                "trade": {"mode": "trade", "status": "refused", "reason": "scan_failed"},
                "trades_by_series": {
                    s: {"rc": int((scans_by_series.get(s) or {}).get("_rc") or 0), "scan": {"inputs": {"series": s, "allow_write": False}}}
                    for s in series_list
                },
                "post_rc": post_rc,
                "post": post,
            }
            artifact_path = os.path.join(out_dir, f"{ts}.json")
            _save_json(artifact_path, artifact)
            _write_prom_metrics(root, metrics_path=rt_cfg.metrics_path, enabled=bool(rt_cfg.metrics_enabled), artifact=artifact)
            _write_cycle_status(root, status="scan_failed", detail="all series scans failed", extra={"artifact": artifact_path})
            return 0

        sigma_arg = sigma
        if str(sigma).strip().lower() == "auto":
            try:
                v = conservative_sigma_auto(selected_series, window_hours=int(sigma_window_h))
            except Exception:
                v = None
            if v is not None:
                sigma_arg = f"{float(v):.4f}"

        cycle_inputs = {
            "series": selected_series,
            "series_list": series_list,
            "scan_summary": scan_summary,
            "autotune": autotune_status,
            "runtime": rt_cfg.as_dict(),
            "runtime_errors": rt_errs,
            "execution_mode": str(rt_cfg.execution_mode),
            "allow_live_writes": bool(rt_cfg.allow_live_writes),
            "sigma": str(sigma),
            "sigma_arg": str(sigma_arg),
            "sigma_window_h": int(sigma_window_h),
            "min_edge_bps": float(min_edge),
            "uncertainty_bps": float(uncertainty),
            "min_liquidity_usd": float(min_liq),
            "max_spread": float(max_spread),
            "min_seconds_to_expiry": int(min_tte),
            "min_price": float(min_px),
            "max_price": float(max_px),
            "min_notional_usd": float(min_notional),
            "min_notional_bypass_edge_bps": float(min_notional_bypass),
            "max_market_concentration_fraction": float(rt_cfg.max_market_concentration_fraction),
            "scan_select_min_liquidity_usd": float(select_min_liq),
            "scan_select_max_spread": float(select_max_spread),
            "scan_select_min_tte_s": float(select_min_tte),
            "scan_select_min_candidates": int(select_min_candidates),
            "scan_select_depth_weight": float(select_depth_weight),
            "persistence_cycles": int(persist),
            "persistence_window_min": float(persist_win),
            "daily_loss_limit_usd": float(limit) if limit > 0 else 0.0,
            "pnl_today_usd_approx": float(pnl_today) if isinstance(pnl_today, (int, float)) else None,
        }

        # Record persistence observations from scans once per cycle (cheaper than running trade N times).
        try:
            for sobj in scans_by_series.values():
                if isinstance(sobj, dict):
                    _record_observations_from_scan(root, sobj, ts_unix=ts)
        except Exception:
            pass

        # Trade only the selected series (live), still guarded by kill switch + risk caps.
        trade_argv = _build_trade_argv(
            selected_series=selected_series,
            sigma_arg=str(sigma_arg),
            min_edge=str(min_edge),
            uncertainty=str(uncertainty),
            min_liq=str(min_liq),
            max_spread=str(max_spread),
            min_tte=str(min_tte),
            min_px=str(min_px),
            max_px=str(max_px),
            min_notional=str(min_notional),
            min_notional_bypass=str(min_notional_bypass),
            persist=str(persist),
            persist_win=str(persist_win),
            sizing_mode=str(sizing_mode),
            kelly_fraction=str(kelly_fraction),
            kelly_cap_fraction=str(kelly_cap_fraction),
            bayes_prior_k=str(bayes_prior_k),
            bayes_obs_k_max=str(bayes_obs_k_max),
            vol_anomaly=str(vol_anomaly),
            vol_anomaly_window_h=str(vol_anomaly_window_h),
            max_market_concentration_fraction=str(max_market_concentration_fraction),
            allow_live_writes=bool(rt_cfg.allow_live_writes),
        )
        trade_rc, _, trade = _run_cmd_json(trade_argv, cwd=root, timeout_s=90)
        trade = trade if isinstance(trade, dict) else {"mode": "trade", "status": "error", "reason": "bad_json"}
        # Expose scan context per series in the run artifact for status/digests.
        trades_by_series: Dict[str, Any] = {}
        for s in series_list:
            sobj = scans_by_series.get(s)
            if not isinstance(sobj, dict):
                sobj = {"_rc": 1}
            allow_write = (s == selected_series)
            trades_by_series[s] = {
                "rc": int(sobj.get("_rc") or 0),
                "scan": {
                    "best": _best_candidate_from_scan(sobj) if isinstance(sobj, dict) else None,
                    "sigma_arg": sobj.get("_sigma_arg"),
                    "inputs": {"series": s, "allow_write": bool(allow_write)},
                },
            }

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
            "trades_by_series": trades_by_series,
            "post_rc": post_rc,
            "post": post,
        }
        artifact_path = os.path.join(out_dir, f"{ts}.json")
        _save_json(artifact_path, artifact)
        _write_prom_metrics(root, metrics_path=rt_cfg.metrics_path, enabled=bool(rt_cfg.metrics_enabled), artifact=artifact)

        # Closed-loop learning: persist entry features + fills + settlements to a rolling ledger.
        try:
            if isinstance(trade, dict) and isinstance(post, dict):
                update_from_run(root, ts_unix=ts, trade=trade, post=post, cycle_inputs=cycle_inputs)
        except Exception:
            pass

        # Safety: cooldown after unexpected behavior, even if we don't hard-stop with kill switch.
        # This reduces repeated retries into a degraded API / degraded market.
        outcome = _cycle_outcome_flags(
            bal_rc=bal_rc,
            bal=bal,
            post_rc=post_rc,
            post=post,
            trade_rc=trade_rc,
            trade=trade,
        )
        any_error = bool(outcome["any_error"])
        any_order_failed = bool(outcome["any_order_failed"])
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

        # Notify only on material milestone events (errors / pauses by default), rate-limited.
        chat_id = _telegram_chat_id()
        can_notify = chat_id is not None
        now = ts
        last = int(notify_state.get("last_notify_ts") or 0)
        rate_limit_s = int(os.environ.get("KALSHI_ARB_NOTIFY_MIN_INTERVAL_S", "900"))  # 15m
        allowed = (now - last) >= rate_limit_s
        notify_trades = _truthy_env("KALSHI_ARB_NOTIFY_TRADES", default="0")

        placed = (trade.get("placed") or []) if isinstance(trade, dict) else []
        live_orders = [p for p in placed if isinstance(p, dict) and p.get("mode") == "live"]
        any_error = bool(outcome["any_error"])
        any_soft_err = bool(outcome["any_soft_err"])
        any_order_failed = bool(outcome["any_order_failed"])

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

        milestone_notify = bool(rt_cfg.milestone_notify)
        # Default: milestone-only alerts.
        should_notify = bool(any_error or any_soft_err or any_order_failed)
        if not milestone_notify and notify_trades:
            should_notify = should_notify or bool(live_orders)

        auto_paused = bool(kill_on and (health["runs"] >= lookback) and (health["errors"] >= max_err or health["order_failed"] >= max_of))

        if can_notify and allowed and should_notify:
            msg = _milestone_notification_text(
                any_error=any_error,
                any_soft_err=any_soft_err,
                any_order_failed=any_order_failed,
                milestone_notify=milestone_notify,
                notify_trades=notify_trades,
                live_orders=live_orders,
                post=post,
                auto_paused=auto_paused,
            )
            _send_telegram(int(chat_id), msg, cwd=root)
            notify_state["last_notify_ts"] = now
            _save_json(notify_state_path, notify_state)
        no_trade_reason = ""
        try:
            if isinstance(trade, dict):
                dg = trade.get("diagnostics") if isinstance(trade.get("diagnostics"), dict) else {}
                top = dg.get("top_blockers") if isinstance(dg, dict) else []
                if isinstance(top, list) and top and isinstance(top[0], dict):
                    no_trade_reason = str(top[0].get("reason") or "")
        except Exception:
            no_trade_reason = ""
        _write_cycle_status(
            root,
            status="completed",
            detail="cycle complete",
            extra={
                "artifact": artifact_path,
                "allow_live_writes": bool(rt_cfg.allow_live_writes),
                "live_orders": len(live_orders),
                "no_trade_reason": no_trade_reason,
            },
        )
        return 0
    finally:
        _release_lock(root)


if __name__ == "__main__":
    raise SystemExit(main())
