#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

try:
    from scripts.arb.kalshi import KalshiClient  # type: ignore
    from scripts.arb.kalshi_analytics import (  # type: ignore
        dedupe_settlements,
        extract_market_position_counts,
        match_fills_for_order,
        settlement_cash_delta_usd,
        summarize_post_snapshot,
    )
    from scripts.arb.kalshi_ledger import closed_loop_report, load_ledger  # type: ignore
except ModuleNotFoundError:
    # Allow running from repo root without package install.
    import sys

    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.arb.kalshi import KalshiClient  # type: ignore
    from scripts.arb.kalshi_analytics import (  # type: ignore
        dedupe_settlements,
        extract_market_position_counts,
        match_fills_for_order,
        settlement_cash_delta_usd,
        summarize_post_snapshot,
    )
    from scripts.arb.kalshi_ledger import closed_loop_report, load_ledger  # type: ignore


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


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
                    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                        v = v[1:-1]
                    # Keep strategy params consistent with ~/.openclaw/.env even if the
                    # gateway process already has older exported values.
                    if k.startswith("KALSHI_ARB_"):
                        os.environ[k] = v
                        continue
                    if k not in os.environ or os.environ.get(k, "") == "":
                        os.environ[k] = v
            return True
        except Exception:
            return False

    if _try(path):
        return
    # If OPENCLAW_ENV_PATH is mis-set, fall back to the default location.
    if os.path.expanduser(path) != os.path.expanduser("~/.openclaw/.env"):
        _try("~/.openclaw/.env")


def _param_recommendations(cl: Dict[str, Any], current_inputs: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Produce conservative, non-auto-applied parameter recommendations from closed-loop stats."""

    def _num(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            return float(x)
        except Exception:
            return None

    def _int(x: Any) -> Optional[int]:
        try:
            if x is None:
                return None
            return int(x)
        except Exception:
            return None

    settled = _int(cl.get("settled_orders")) or 0
    if settled < 5:
        return []

    cur_unc = _num((current_inputs or {}).get("uncertainty_bps"))
    cur_edge = _num((current_inputs or {}).get("min_edge_bps"))
    cur_pers = _int((current_inputs or {}).get("persistence_cycles"))

    wr = _num(cl.get("win_rate"))
    ap = _num(cl.get("avg_implied_win_prob_settled"))
    brier = _num(cl.get("brier_score_settled"))
    pnl = _num(cl.get("realized_pnl_usd_approx"))

    recs: List[Dict[str, Any]] = []

    # If we underperform implied probability or calibration is bad, increase conservatism.
    if wr is not None and ap is not None and wr + 0.05 < ap:
        target = 75.0 if cur_unc is None else min(200.0, float(cur_unc) + 25.0)
        recs.append(
            {
                "env": "KALSHI_ARB_UNCERTAINTY_BPS",
                "value": str(int(round(target))),
                "why": "Win-rate is materially below implied probability; add buffer to reduce false positives.",
            }
        )

    if brier is not None and brier > 0.25:
        target = 100.0 if cur_unc is None else min(250.0, float(cur_unc) + 25.0)
        recs.append(
            {
                "env": "KALSHI_ARB_UNCERTAINTY_BPS",
                "value": str(int(round(target))),
                "why": "Poor calibration (high Brier); add uncertainty buffer and keep sigma=auto.",
            }
        )

    if pnl is not None and pnl < 0.0:
        # Trade less frequently by requiring persistence.
        target = 2 if cur_pers is None else min(4, int(cur_pers) + 1)
        recs.append(
            {
                "env": "KALSHI_ARB_PERSISTENCE_CYCLES",
                "value": str(int(target)),
                "why": "Negative realized P/L; require edge persistence across more cycles before entering.",
            }
        )

    if cur_edge is not None and pnl is not None and pnl < 0.0:
        target = min(400.0, float(cur_edge) + 20.0)
        recs.append(
            {
                "env": "KALSHI_ARB_MIN_EDGE_BPS",
                "value": str(int(round(target))),
                "why": "Negative realized P/L; tighten min-edge to trade less and only take clearer mispricings.",
            }
        )

    # Deduplicate by env; keep first (most relevant).
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in recs:
        e = r.get("env")
        if not isinstance(e, str) or not e:
            continue
        if e in seen:
            continue
        seen.add(e)
        out.append(r)
    return out


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


def _send_telegram(chat_id: int, text: str, *, cwd: str) -> bool:
    # Use the repo helper to avoid token handling here, but avoid `bash -lc "...$..."`
    # because dollar signs in text would be expanded by the shell.
    try:
        import subprocess

        proc = subprocess.run(
            ["bash", "scripts/telegram_send_message.sh", str(int(chat_id)), str(text)],
            cwd=cwd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return int(proc.returncode) == 0
    except Exception:
        return False


def _send_email_via_agentmail(to_email: str, subject: str, body: str, *, cwd: str) -> bool:
    """Send plain-text email using the repo AgentMail helper script."""
    try:
        import subprocess
        import tempfile
        import re

        def _write_last_send(obj: Dict[str, Any]) -> None:
            try:
                p = os.path.join(cwd, "tmp", "kalshi_ref_arb", "last_email_send.json")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(obj, f, indent=2, sort_keys=True)
                    f.write("\n")
            except Exception:
                return

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(body)
            f.write("\n")
            body_path = f.name
        try:
            last_err = ""
            for attempt in range(1, 4):
                proc = subprocess.run(
                    ["bash", "scripts/agentmail_send.sh", "--to", str(to_email), "--subject", str(subject), "--text-file", body_path],
                    cwd=cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                out = (proc.stdout or "").strip()
                err = (proc.stderr or "").strip()
                if int(proc.returncode) == 0:
                    mid = None
                    m = re.search(r"message_id=(\S+)", out)
                    if m:
                        mid = m.group(1).strip().strip("<>").strip()
                    _write_last_send(
                        {
                            "ts_unix": int(time.time()),
                            "ok": True,
                            "to": str(to_email),
                            "subject": str(subject),
                            "message_id": mid,
                            "attempt": attempt,
                        }
                    )
                    return True
                last_err = err or out or f"returncode={proc.returncode}"
                time.sleep(min(10.0, 1.5 * float(attempt)))

            _write_last_send(
                {
                    "ts_unix": int(time.time()),
                    "ok": False,
                    "to": str(to_email),
                    "subject": str(subject),
                    "error": str(last_err)[:1000],
                }
            )
            if last_err:
                print(f"EMAIL_SEND_FAILED: {last_err[:400]}", file=os.sys.stderr)
            return False
        finally:
            try:
                os.remove(body_path)
            except Exception:
                pass
    except Exception:
        return False


def _send_email_html_via_agentmail(to_email: str, subject: str, *, text_body: str, html_body: str, cwd: str) -> bool:
    """Send multipart (text + html) email using the repo AgentMail helper script."""
    try:
        import subprocess
        import tempfile
        import re

        def _write_last_send(obj: Dict[str, Any]) -> None:
            try:
                p = os.path.join(cwd, "tmp", "kalshi_ref_arb", "last_email_send.json")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(obj, f, indent=2, sort_keys=True)
                    f.write("\n")
            except Exception:
                return

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tf:
            tf.write(text_body)
            tf.write("\n")
            text_path = tf.name
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as hf:
            hf.write(html_body)
            hf.write("\n")
            html_path = hf.name

        try:
            last_err = ""
            for attempt in range(1, 4):
                proc = subprocess.run(
                    [
                        "bash",
                        "scripts/agentmail_send.sh",
                        "--to",
                        str(to_email),
                        "--subject",
                        str(subject),
                        "--text-file",
                        text_path,
                        "--html-file",
                        html_path,
                    ],
                    cwd=cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                out = (proc.stdout or "").strip()
                err = (proc.stderr or "").strip()
                if int(proc.returncode) == 0:
                    mid = None
                    m = re.search(r"message_id=(\S+)", out)
                    if m:
                        mid = m.group(1).strip().strip("<>").strip()
                    _write_last_send(
                        {
                            "ts_unix": int(time.time()),
                            "ok": True,
                            "to": str(to_email),
                            "subject": str(subject),
                            "message_id": mid,
                            "attempt": attempt,
                        }
                    )
                    return True
                last_err = err or out or f"returncode={proc.returncode}"
                time.sleep(min(10.0, 1.5 * float(attempt)))

            _write_last_send(
                {
                    "ts_unix": int(time.time()),
                    "ok": False,
                    "to": str(to_email),
                    "subject": str(subject),
                    "error": str(last_err)[:1000],
                }
            )
            if last_err:
                print(f"EMAIL_SEND_FAILED: {last_err[:400]}", file=os.sys.stderr)
            return False
        finally:
            for p in (text_path, html_path):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        return False


def _email_to_default() -> Optional[str]:
    # Prefer a dedicated env var for Kalshi digests; fallback to global AgentMail default if set.
    for k in ("KALSHI_ARB_DIGEST_EMAIL_TO", "AGENTMAIL_TO"):
        v = os.environ.get(k) or ""
        if v.strip():
            return v.strip()
    return None


def _escape_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _fmt_usd_opt(x: Any) -> str:
    try:
        if x is None:
            return "-"
        return _format_usd(float(x))
    except Exception:
        return "-"


def _fmt_int_opt(x: Any) -> str:
    try:
        if x is None:
            return "-"
        return str(int(x))
    except Exception:
        return "-"


def _status_styles(status: str) -> Tuple[str, str]:
    s = (status or "").upper().strip()
    if s == "PAUSED":
        return ("#fff7ed", "#9a3412")  # bg, fg
    if s == "WARN":
        return ("#fef9c3", "#854d0e")
    return ("#dcfce7", "#166534")


def _render_metrics_table(rows: List[Tuple[str, str]]) -> str:
    out = []
    for k, v in rows:
        out.append(
            "<tr>"
            f'<td style="padding:8px 10px;color:#94a3b8;font-size:13px;border-top:1px solid #1f2a44;">{_escape_html(k)}</td>'
            f'<td style="padding:8px 10px;color:#e2e8f0;font-size:13px;border-top:1px solid #1f2a44;text-align:right;font-weight:600;">{_escape_html(v)}</td>'
            "</tr>"
        )
    return "\n".join(out)


def _render_bar_table(items: List[Tuple[str, int]]) -> str:
    if not items:
        return '<div style="color:#94a3b8;font-size:13px;">No blockers observed in this window.</div>'
    maxc = max((c for _, c in items if isinstance(c, int) and c > 0), default=1)
    rows = []
    for reason, count in items[:8]:
        c = int(count or 0)
        pct = int(round((float(c) / float(maxc)) * 100.0)) if maxc > 0 else 0
        rows.append(
            "<tr>"
            f'<td style="padding:6px 0 6px 0;color:#e2e8f0;font-size:13px;white-space:nowrap;">{_escape_html(reason)}</td>'
            f'<td style="padding:6px 0 6px 10px;color:#94a3b8;font-size:13px;text-align:right;white-space:nowrap;">{c}</td>'
            '<td style="padding:6px 0 6px 10px;width:100%;">'
            '<div style="height:10px;background:#0b1220;border:1px solid #1f2a44;border-radius:999px;overflow:hidden;">'
            f'<div style="height:10px;width:{pct}%;background:linear-gradient(90deg,#38bdf8,#a78bfa);border-radius:999px;"></div>'
            "</div>"
            "</td>"
            "</tr>"
        )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">'
        + "\n".join(rows)
        + "</table>"
    )


def _render_positions_table(items: List[Dict[str, Any]]) -> str:
    if not items:
        return '<div style="color:#94a3b8;font-size:13px;">No open positions detected.</div>'
    rows = []
    for it in items[:8]:
        t = str(it.get("ticker") or "")
        y = it.get("yes")
        n = it.get("no")
        notional = it.get("notional_usd")
        rows.append(
            "<tr>"
            f'<td style="padding:8px 10px;color:#e2e8f0;font-size:13px;border-top:1px solid #1f2a44;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,\\"Liberation Mono\\",\\"Courier New\\",monospace;white-space:nowrap;">{_escape_html(t)}</td>'
            f'<td style="padding:8px 10px;color:#94a3b8;font-size:13px;border-top:1px solid #1f2a44;text-align:right;">{_escape_html(_fmt_int_opt(y))}</td>'
            f'<td style="padding:8px 10px;color:#94a3b8;font-size:13px;border-top:1px solid #1f2a44;text-align:right;">{_escape_html(_fmt_int_opt(n))}</td>'
            f'<td style="padding:8px 10px;color:#e2e8f0;font-size:13px;border-top:1px solid #1f2a44;text-align:right;font-weight:600;">{_escape_html(_fmt_usd_opt(notional))}</td>'
            "</tr>"
        )
    head = (
        "<tr>"
        '<td style="padding:8px 10px;color:#94a3b8;font-size:12px;">Ticker</td>'
        '<td style="padding:8px 10px;color:#94a3b8;font-size:12px;text-align:right;">YES</td>'
        '<td style="padding:8px 10px;color:#94a3b8;font-size:12px;text-align:right;">NO</td>'
        '<td style="padding:8px 10px;color:#94a3b8;font-size:12px;text-align:right;">Notional (est)</td>'
        "</tr>"
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">'
        + head
        + "\n".join(rows)
        + "</table>"
    )


def _top_k_counts(items: List[str], *, k: int = 8) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for it in items:
        s = str(it or "").strip()
        if not s:
            continue
        counts[s] = int(counts.get(s, 0)) + 1
    out = sorted(counts.items(), key=lambda kv: (-int(kv[1]), kv[0]))
    return out[: int(k)]


def _summarize_skips_and_live_spot(run_objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate skip reasons + live-spot issues across the digest window."""
    skip_keys: List[str] = []
    live_errs: List[str] = []
    live_ok = 0
    live_seen = 0

    for o in run_objs:
        trade = o.get("trade") if isinstance(o.get("trade"), dict) else {}
        skipped = trade.get("skipped") or []
        if isinstance(skipped, list):
            for s in skipped:
                if not isinstance(s, dict):
                    continue
                detail = s.get("detail")
                reason = s.get("reason")
                key = None
                if isinstance(detail, str) and detail.strip():
                    key = detail.strip()
                elif isinstance(reason, str) and reason.strip():
                    key = reason.strip()
                if key:
                    skip_keys.append(key)
                le = s.get("ref_spot_live_err")
                if isinstance(le, str) and le.strip():
                    live_errs.append(le.strip()[:80])

        placed = trade.get("placed") or []
        if isinstance(placed, list):
            for p in placed:
                if not isinstance(p, dict):
                    continue
                if p.get("ref_spot_live") is not None or p.get("ref_spot_live_err"):
                    live_seen += 1
                if isinstance(p.get("ref_spot_live"), (int, float)):
                    live_ok += 1
                le = p.get("ref_spot_live_err")
                if isinstance(le, str) and le.strip():
                    live_errs.append(le.strip()[:80])

    return {
        "top_skips": [{"reason": r, "count": c} for r, c in _top_k_counts(skip_keys, k=8)],
        "live_spot": {
            "attempts_with_fields": int(live_seen),
            "ok_prices": int(live_ok),
            "top_errors": [{"error": r, "count": c} for r, c in _top_k_counts(live_errs, k=5)],
        },
    }


def _load_sweep_stats(root: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(root, "tmp", "kalshi_ref_arb", "sweep_stats.json")
    try:
        obj = json.load(open(p, "r", encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _sweep_rollup_24h(obj: Optional[Dict[str, Any]], *, now_unix: int) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    entries = obj.get("entries")
    if not isinstance(entries, list) or not entries:
        return None
    window_s = int(obj.get("window_s") or 24 * 3600)
    start = int(now_unix) - max(60, window_s)
    totals = {
        "cycles": 0,
        "signals": 0,
        "recommended": 0,
        "placed_live": 0,
        "no_fill": 0,
        "recheck_failed": 0,
        "live_spot_fail": 0,
        "cache_hits": 0,
    }
    for it in entries:
        if not isinstance(it, dict):
            continue
        try:
            ts = int(it.get("ts_unix") or 0)
        except Exception:
            ts = 0
        if ts < start:
            continue
        totals["cycles"] += 1
        for k in ("signals_computed", "candidates_recommended", "placed_live", "no_fill", "recheck_failed", "live_spot_fail"):
            try:
                totals_map = {
                    "signals_computed": "signals",
                    "candidates_recommended": "recommended",
                    "placed_live": "placed_live",
                    "no_fill": "no_fill",
                    "recheck_failed": "recheck_failed",
                    "live_spot_fail": "live_spot_fail",
                }
                totals[totals_map[k]] += int(it.get(k) or 0)
            except Exception:
                pass
        if bool(it.get("markets_cache_hit")):
            totals["cache_hits"] += 1
    return totals


def _digest_html(*, subject: str, window_hours: float, payload: Dict[str, Any], now_unix: int) -> str:
    # Email-client friendly HTML: table layout + inline styles, no external assets.
    dt_local = datetime.datetime.fromtimestamp(int(now_unix)).astimezone()
    dt_et = datetime.datetime.fromtimestamp(int(now_unix), tz=ZoneInfo("America/New_York"))
    ts_local = dt_local.strftime("%Y-%m-%d %H:%M %Z")
    ts_et = dt_et.strftime("%Y-%m-%d %I:%M %p ET")

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    today = payload.get("today") if isinstance(payload.get("today"), dict) else {}
    no_trade = payload.get("no_trade") if isinstance(payload.get("no_trade"), dict) else {}

    status = str(summary.get("status") or "OK").upper()
    pill_bg, pill_fg = _status_styles(status)

    exec_rows: List[Tuple[str, str]] = [
        ("Status", status),
        ("Cash", _fmt_usd_opt(summary.get("cash_usd"))),
        ("Portfolio value", _fmt_usd_opt(summary.get("portfolio_value_usd"))),
        ("Deployed downside (est)", _fmt_usd_opt(summary.get("deployed_notional_usd"))),
        ("Live orders (window)", f"{_fmt_int_opt(stats.get('live_orders'))} ({_fmt_usd_opt(stats.get('live_notional_usd'))})"),
        ("Cycles (window)", _fmt_int_opt(stats.get("cycles"))),
    ]
    if summary.get("fees_total_usd_window") is not None:
        pct = summary.get("fees_pct_window")
        tail = f" ({float(pct):.1f}%)" if isinstance(pct, (int, float)) else ""
        exec_rows.append(("Fees (window)", f"{_fmt_usd_opt(summary.get('fees_total_usd_window'))}{tail}"))
    if summary.get("realized_pnl_usd_approx") is not None:
        exec_rows.append(("Realized P/L (settled, approx)", _fmt_usd_opt(summary.get("realized_pnl_usd_approx"))))
    if summary.get("settlements_cash_delta_usd_window") is not None:
        exec_rows.append(("Settlements cash delta (window)", _fmt_usd_opt(summary.get("settlements_cash_delta_usd_window"))))
    if summary.get("mtm_liq_value_usd") is not None:
        exec_rows.append(("MTM liquidation (bids, est)", _fmt_usd_opt(summary.get("mtm_liq_value_usd"))))
    if summary.get("sigma_avg") is not None:
        mode = summary.get("sigma_mode") or ""
        sm = f"{float(summary.get('sigma_avg')):.4f}" if isinstance(summary.get("sigma_avg"), (int, float)) else "-"
        if isinstance(mode, str) and mode:
            sm = f"{sm} ({mode})"
        exec_rows.append(("Sigma (avg)", sm))

    today_rows: List[Tuple[str, str]] = [
        ("Cycles (today)", _fmt_int_opt(today.get("cycles"))),
        ("Live orders (today)", f"{_fmt_int_opt(today.get('live_orders'))} ({_fmt_usd_opt(today.get('live_notional_usd'))})"),
        ("Realized P/L (today, settled)", _fmt_usd_opt(today.get("realized_pnl_usd_settled"))),
    ]

    blockers_items: List[Tuple[str, int]] = []
    tb = no_trade.get("top_blockers")
    if isinstance(tb, list):
        for it in tb:
            if not isinstance(it, dict):
                continue
            r = it.get("reason")
            c = it.get("count")
            if isinstance(r, str) and isinstance(c, int):
                blockers_items.append((r, c))

    skips_items: List[Tuple[str, int]] = []
    ts = no_trade.get("top_skips")
    if isinstance(ts, list):
        for it in ts:
            if not isinstance(it, dict):
                continue
            r = it.get("reason")
            c = it.get("count")
            if isinstance(r, str) and isinstance(c, int):
                skips_items.append((r, c))

    live_spot_s = no_trade.get("live_spot") if isinstance(no_trade.get("live_spot"), dict) else {}

    raw_message = payload.get("message") if isinstance(payload.get("message"), str) else ""
    include_raw = status in ("WARN", "PAUSED")

    commands = [
        "python3 /Users/corystoner/Desktop/ORION/scripts/kalshi_ref_arb.py balance",
        f"python3 /Users/corystoner/Desktop/ORION/scripts/kalshi_digest.py --window-hours {int(window_hours)} --send-email --email-html",
    ]

    why_lines: List[str] = []
    if isinstance(no_trade.get("headline"), str) and no_trade["headline"].strip():
        why_lines.append(no_trade["headline"].strip())
    if isinstance(no_trade.get("series_selected"), str) and no_trade["series_selected"].strip():
        why_lines.append(f"Series selected: {no_trade['series_selected'].strip()}")
    st = no_trade.get("scans")
    if isinstance(st, dict):
        tmo = int(st.get("timeouts") or 0)
        err = int(st.get("errors") or 0)
        if tmo or err:
            why_lines.append(f"Scans: timeouts {tmo}, errors {err}")

    try:
        if isinstance(live_spot_s, dict) and live_spot_s:
            okp = int(live_spot_s.get("ok_prices") or 0)
            att = int(live_spot_s.get("attempts_with_fields") or 0)
            if att > 0:
                why_lines.append(f"Live spot: ok {okp}/{att}")
    except Exception:
        pass

    why_html = ""
    if why_lines or blockers_items or skips_items:
        why_html = (
            '<tr><td style="padding:0 0 14px 0;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">'
            '<tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Why No Trades</td></tr>'
            '<tr><td style="padding:0 14px 14px 14px;">'
        )
        if why_lines:
            why_html += '<div style="color:#e2e8f0;font-size:13px;line-height:1.45;">' + "<br/>".join(
                _escape_html(x) for x in why_lines[:6]
            ) + "</div>"
        if blockers_items:
            why_html += '<div style="height:10px;"></div>' + _render_bar_table(blockers_items)
        if skips_items:
            why_html += '<div style="height:10px;"></div><div style="color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;margin:2px 0 8px 0;">Skips (window)</div>' + _render_bar_table(skips_items)
        try:
            te = live_spot_s.get("top_errors") if isinstance(live_spot_s, dict) else None
            if isinstance(te, list) and te:
                parts = []
                for it in te[:3]:
                    if not isinstance(it, dict):
                        continue
                    e = it.get("error")
                    c = it.get("count")
                    if isinstance(e, str) and isinstance(c, int):
                        parts.append(f"{e}={c}")
                if parts:
                    why_html += '<div style="height:10px;"></div><div style="color:#94a3b8;font-size:13px;">Live spot errors: ' + _escape_html(", ".join(parts)) + "</div>"
        except Exception:
            pass
        why_html += "</td></tr></table></td></tr>"

    pre = _escape_html(raw_message)
    cmd_html = "<br/>".join(f"<code>{_escape_html(c)}</code>" for c in commands)

    health_html = ""
    if include_raw:
        last_cycle = summary.get("last_cycle_ts_et") if isinstance(summary.get("last_cycle_ts_et"), str) else ""
        last_issue = summary.get("last_issue") if isinstance(summary.get("last_issue"), str) else ""
        parts = []
        if last_cycle.strip():
            parts.append(f"<b>Last cycle:</b> {_escape_html(last_cycle.strip())}")
        if last_issue.strip():
            parts.append(f"<b>Last issue:</b> {_escape_html(last_issue.strip())}")
        if parts:
            health_html = (
                '<tr><td style="padding:0 0 14px 0;">'
                '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">'
                '<tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Health</td></tr>'
                '<tr><td style="padding:0 14px 14px 14px;color:#e2e8f0;font-size:13px;line-height:1.45;">'
                + "<br/>".join(parts)
                + "</td></tr></table></td></tr>"
            )

    positions_html = ""
    pts = summary.get("positions_top")
    if isinstance(pts, list) and pts:
        positions_html = (
            '<tr><td style="padding:0 0 14px 0;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">'
            '<tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Exposure (Top Positions)</td></tr>'
            '<tr><td style="padding:0 14px 14px 14px;">'
            + _render_positions_table([x for x in pts if isinstance(x, dict)])
            + "</td></tr></table></td></tr>"
        )

    raw_html = ""
    if include_raw:
        raw_html = f"""
            <tr>
              <td style="padding:0 0 14px 0;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">
                  <tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Raw Details</td></tr>
                  <tr>
                    <td style="padding:0 14px 14px 14px;">
                      <pre style="margin:0;white-space:pre-wrap;word-wrap:break-word;background:#05070d;border:1px solid #1f2a44;border-radius:12px;padding:12px;color:#dbeafe;font-size:12px;line-height:1.45;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,\\"Liberation Mono\\",\\"Courier New\\",monospace;">{pre}</pre>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
        """

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape_html(subject)}</title>
  </head>
  <body style="margin:0;padding:0;background:#05070d;background-image:radial-gradient(900px 700px at 18% 10%, rgba(56,189,248,0.14), transparent 60%),radial-gradient(700px 600px at 82% 18%, rgba(167,139,250,0.12), transparent 58%),radial-gradient(900px 900px at 50% 110%, rgba(34,197,94,0.06), transparent 55%);">
    <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;background:#05070d;background-image:radial-gradient(900px 700px at 18% 10%, rgba(56,189,248,0.14), transparent 60%),radial-gradient(700px 600px at 82% 18%, rgba(167,139,250,0.12), transparent 58%),radial-gradient(900px 900px at 50% 110%, rgba(34,197,94,0.06), transparent 55%);">
      <tr>
        <td align="center" style="padding:24px 12px 36px 12px;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="width:640px;max-width:640px;border-collapse:separate;border-spacing:0;">
            <tr>
              <td style="padding:16px 18px;background:linear-gradient(180deg, #101a2e 0%, #0b1220 100%);border:1px solid #1f2a44;border-radius:18px;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">
                  <tr>
                    <td style="vertical-align:top;">
                      <div style="font-family:Helvetica,Arial,sans-serif;color:#e2e8f0;font-size:18px;font-weight:800;letter-spacing:0.2px;">
                        ORION Kalshi Digest
                        <span style="display:inline-block;margin-left:8px;padding:3px 10px;border-radius:999px;background:{pill_bg};color:{pill_fg};font-size:12px;font-weight:700;vertical-align:middle;">
                          { _escape_html(status) }
                        </span>
                        <span style="display:inline-block;margin-left:6px;padding:3px 10px;border-radius:999px;background:#0f1930;border:1px solid #1f2a44;color:#bae6fd;font-size:12px;font-weight:700;vertical-align:middle;">
                          {window_hours:.1f}h window
                        </span>
                      </div>
                      <div style="margin-top:4px;font-family:Helvetica,Arial,sans-serif;color:#94a3b8;font-size:13px;">
                        { _escape_html(ts_et) } · { _escape_html(ts_local) }
                      </div>
                    </td>
                    <td style="text-align:right;vertical-align:top;">
                      <div style="font-family:Helvetica,Arial,sans-serif;color:#94a3b8;font-size:12px;">{ _escape_html(subject) }</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr><td style="height:14px;"></td></tr>

            <tr>
              <td style="padding:0 0 14px 0;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">
                  <tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Executive Summary</td></tr>
                  <tr>
                    <td style="padding:0 14px 14px 14px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">
                        { _render_metrics_table(exec_rows) }
                      </table>
                      <div style="margin-top:10px;color:#94a3b8;font-size:12px;font-family:Helvetica,Arial,sans-serif;">
                        Telegram alerts are sent only on errors/pauses. Regular updates are via email.
                      </div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            {health_html}
            {why_html}
            {positions_html}

            <tr>
              <td style="padding:0 0 14px 0;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">
                  <tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Today So Far (ET)</td></tr>
                  <tr>
                    <td style="padding:0 14px 14px 14px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">
                        { _render_metrics_table(today_rows) }
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:0 0 14px 0;">
                <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:0;background:#0f1930;border:1px solid #1f2a44;border-radius:16px;">
                  <tr><td style="padding:14px 14px 10px 14px;color:#94a3b8;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;">Quick Commands</td></tr>
                  <tr>
                    <td style="padding:0 14px 14px 14px;color:#e2e8f0;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,\"Liberation Mono\",\"Courier New\",monospace;line-height:1.5;">
                      {cmd_html}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            {raw_html}

            <tr>
              <td style="padding:0 4px;color:#94a3b8;font-size:12px;font-family:Helvetica,Arial,sans-serif;">
                Generated by ORION. Reply with what you want emphasized (P/L, risk, fills, or “why no trade”).
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _day_bounds_unix(*, tz: str, now_unix: int) -> Tuple[int, int]:
    z = ZoneInfo(tz)
    dt = datetime.datetime.fromtimestamp(int(now_unix), tz=z)
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def _daily_realized_pnl_usd(repo_root: str, *, now_unix: int, tz: str = "America/New_York") -> Optional[float]:
    """Best-effort: sum attributed settlement cash deltas for today's settlements in the ledger."""
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


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return dict(default)


def _list_run_files(runs_dir: str) -> List[str]:
    try:
        names = [n for n in os.listdir(runs_dir) if n.endswith(".json")]
    except Exception:
        return []
    out: List[str] = []
    for n in names:
        p = os.path.join(runs_dir, n)
        if os.path.isfile(p):
            out.append(p)
    out.sort()
    return out


def _list_run_files_since(runs_dir: str, start_ts: int) -> List[str]:
    try:
        names = [n for n in os.listdir(runs_dir) if n.endswith(".json")]
    except Exception:
        return []
    out: List[str] = []
    for n in names:
        try:
            ts = int(n[:-5])
        except Exception:
            continue
        if ts < int(start_ts):
            continue
        p = os.path.join(runs_dir, n)
        if os.path.isfile(p):
            out.append(p)
    out.sort()
    return out


@dataclass(frozen=True)
class DigestStats:
    from_ts: int
    to_ts: int
    cycles: int
    live_orders: int
    live_notional_usd: float
    errors: int
    order_failed: int
    kill_switch_seen: int


def _extract_stats(run_objs: List[Dict[str, Any]]) -> DigestStats:
    if not run_objs:
        now = int(time.time())
        return DigestStats(
            from_ts=now,
            to_ts=now,
            cycles=0,
            live_orders=0,
            live_notional_usd=0.0,
            errors=0,
            order_failed=0,
            kill_switch_seen=0,
        )

    from_ts = int(min(int(o.get("ts_unix") or 0) for o in run_objs))
    to_ts = int(max(int(o.get("ts_unix") or 0) for o in run_objs))
    cycles = len(run_objs)

    live_orders = 0
    live_notional = 0.0
    errors = 0
    order_failed = 0
    kill_seen = 0

    for o in run_objs:
        bal_rc = int(o.get("balance_rc") or 0)
        trade_rc = int(o.get("trade_rc") or 0)
        trade = o.get("trade") if isinstance(o.get("trade"), dict) else {}

        if bal_rc != 0:
            errors += 1
        refused = bool(trade.get("status") == "refused")
        reason = str(trade.get("reason") or "")
        kill_refused = refused and reason == "kill_switch"
        gate_refused = refused and reason in ("kill_switch", "cooldown", "scan_failed", "daily_loss_limit")
        if kill_refused:
            kill_seen += 1
        if (trade_rc != 0) and (not gate_refused):
            errors += 1

        placed = trade.get("placed") or []
        if isinstance(placed, list):
            for p in placed:
                if not isinstance(p, dict):
                    continue
                if p.get("mode") == "live":
                    live_orders += 1
                    try:
                        live_notional += float(p.get("notional_usd") or 0.0)
                    except Exception:
                        pass

        skipped = trade.get("skipped") or []
        if isinstance(skipped, list):
            for s in skipped:
                if isinstance(s, dict) and s.get("reason") == "order_failed":
                    order_failed += 1

    return DigestStats(
        from_ts=from_ts,
        to_ts=to_ts,
        cycles=cycles,
        live_orders=live_orders,
        live_notional_usd=live_notional,
        errors=errors,
        order_failed=order_failed,
        kill_switch_seen=kill_seen,
    )


def _format_usd(x: float) -> str:
    return f"${x:.2f}"


def _load_risk_state_summary(state_path: str) -> Dict[str, Any]:
    try:
        obj = json.load(open(state_path, "r", encoding="utf-8"))
    except Exception:
        return {"markets": 0, "deployed_notional_usd": None}
    markets = obj.get("markets") or {}
    if not isinstance(markets, dict):
        return {"markets": 0, "deployed_notional_usd": None}
    total = 0.0
    n = 0
    for _, v in markets.items():
        if not isinstance(v, dict):
            continue
        try:
            total += float(v.get("notional_usd") or 0.0)
            n += 1
        except Exception:
            continue
    return {"markets": n, "deployed_notional_usd": float(total)}


def _sigma_summary(run_objs: List[Dict[str, Any]]) -> Dict[str, Any]:
    sigmas: List[float] = []
    modes: List[str] = []
    for o in run_objs:
        ci = o.get("cycle_inputs")
        if not isinstance(ci, dict):
            continue
        sarg = ci.get("sigma_arg")
        smode = ci.get("sigma")
        try:
            if sarg is not None:
                sigmas.append(float(sarg))
        except Exception:
            pass
        if isinstance(smode, str) and smode:
            modes.append(smode)
    avg = (sum(sigmas) / float(len(sigmas))) if sigmas else None
    mode = None
    if modes:
        # If any run was "auto", call it auto; otherwise last explicit.
        mode = "auto" if any(m == "auto" for m in modes) else modes[-1]
    return {"avg_sigma_arg": avg, "mode": mode, "samples": len(sigmas)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a digest for Kalshi ref-arb bot runs.")
    ap.add_argument("--window-hours", type=float, default=8.0)
    ap.add_argument("--send", action="store_true", help="Actually send Telegram (legacy flag); otherwise prints digest JSON.")
    ap.add_argument("--send-telegram", action="store_true", help="Actually send Telegram digest.")
    ap.add_argument("--send-email", action="store_true", help="Actually send email digest via AgentMail.")
    ap.add_argument("--email-to", default="", help="Destination email for --send-email (or env KALSHI_ARB_DIGEST_EMAIL_TO/AGENTMAIL_TO).")
    ap.add_argument("--email-html", action="store_true", help="Send HTML formatted email (with text fallback).")
    args = ap.parse_args()

    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))

    root = _repo_root()
    runs_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "runs")
    state_path = os.path.join(root, "tmp", "kalshi_ref_arb", "state.json")
    kill_path = os.path.join(root, "tmp", "kalshi_ref_arb.KILL")
    cooldown_path = os.path.join(root, "tmp", "kalshi_ref_arb", "cooldown.json")

    now = int(time.time())
    window_s = int(max(60, float(args.window_hours) * 3600.0))
    start = now - window_s

    run_files = _list_run_files(runs_dir)
    run_objs: List[Dict[str, Any]] = []
    for p in run_files:
        try:
            obj = json.load(open(p, "r", encoding="utf-8"))
            if isinstance(obj, dict) and int(obj.get("ts_unix") or 0) >= start:
                run_objs.append(obj)
        except Exception:
            continue

    stats = _extract_stats(run_objs)
    sigma_s = _sigma_summary(run_objs)
    sweep_stats = _load_sweep_stats(root)
    sweep_roll = _sweep_rollup_24h(sweep_stats, now_unix=now)
    # ET "today so far" run stats (helps answer: did it run today, and did it trade today?).
    today_start, _ = _day_bounds_unix(tz="America/New_York", now_unix=now)
    today_files = _list_run_files_since(runs_dir, today_start)
    today_objs: List[Dict[str, Any]] = []
    for p in today_files:
        try:
            obj = json.load(open(p, "r", encoding="utf-8"))
            if isinstance(obj, dict):
                today_objs.append(obj)
        except Exception:
            continue
    today_stats = _extract_stats(today_objs)
    today_realized_pnl = _daily_realized_pnl_usd(root, now_unix=now, tz="America/New_York")

    # For visibility, we report cash / portfolio_value from the most recent post-trade snapshot if present.
    latest_bal = None
    latest_post = None
    for o in reversed(run_objs):
        post = o.get("post")
        if isinstance(post, dict) and isinstance(post.get("balance"), dict):
            latest_post = post
            latest_bal = post.get("balance")
            break
    if latest_bal is None:
        for o in reversed(run_objs):
            bal = o.get("balance")
            if isinstance(bal, dict) and "balance" in bal:
                latest_bal = bal
                break
    avail_usd = None
    port_usd = None
    try:
        if isinstance(latest_bal, dict):
            avail_usd = float(latest_bal.get("balance") or 0.0) / 100.0
            port_usd = float(latest_bal.get("portfolio_value") or 0.0) / 100.0
    except Exception:
        avail_usd = None
        port_usd = None
    kill_on = os.path.exists(kill_path)
    cooldown_on = False
    try:
        if os.path.exists(cooldown_path):
            cd = json.load(open(cooldown_path, "r", encoding="utf-8"))
            until_ts = int((cd or {}).get("until_ts") or 0) if isinstance(cd, dict) else 0
            cooldown_on = until_ts > now
    except Exception:
        cooldown_on = False

    status = "OK"
    if kill_on or cooldown_on:
        status = "PAUSED"
    elif int(stats.errors or 0) > 0 or int(stats.order_failed or 0) > 0:
        status = "WARN"

    # Include whether an auto-pause might have triggered (best-effort).
    notify_state = _load_json(os.path.join(root, "tmp", "kalshi_ref_arb", "notify_state.json"), default={})

    msg_lines = []
    msg_lines.append(f"Kalshi arb digest ({int(args.window_hours)}h)")
    msg_lines.append(f"Cycles: {stats.cycles}")
    msg_lines.append(f"Live orders: {stats.live_orders} (notional { _format_usd(stats.live_notional_usd) })")
    if isinstance(sweep_roll, dict) and int(sweep_roll.get("cycles") or 0) > 0:
        msg_lines.append(
            "Sweeps (24h): "
            + f"cycles {int(sweep_roll.get('cycles') or 0)}, "
            + f"signals {int(sweep_roll.get('signals') or 0)}, "
            + f"recommended {int(sweep_roll.get('recommended') or 0)}, "
            + f"placed {int(sweep_roll.get('placed_live') or 0)}, "
            + f"no_fill {int(sweep_roll.get('no_fill') or 0)}, "
            + f"live_spot_fail {int(sweep_roll.get('live_spot_fail') or 0)}, "
            + f"cache_hit {int(sweep_roll.get('cache_hits') or 0)}/{int(sweep_roll.get('cycles') or 0)}"
        )
    if isinstance(sigma_s.get("avg_sigma_arg"), (int, float)):
        mode = sigma_s.get("mode") or ""
        suffix = f" ({mode})" if isinstance(mode, str) and mode else ""
        msg_lines.append(f"Sigma used (avg): {float(sigma_s['avg_sigma_arg']):.4f}{suffix}")
    if stats.errors:
        msg_lines.append(f"Errors: {stats.errors} (order_failed {stats.order_failed})")
    if stats.kill_switch_seen or kill_on:
        msg_lines.append(f"Kill switch: {'ON' if kill_on else 'OFF'} (seen {stats.kill_switch_seen} cycles refused)")
    if avail_usd is not None:
        msg_lines.append(f"Cash (approx): {_format_usd(avail_usd)}")
    if port_usd is not None:
        msg_lines.append(f"Portfolio value (approx): {_format_usd(port_usd)}")
    if isinstance(latest_post, dict):
        try:
            s = summarize_post_snapshot(latest_post)
            msg_lines.append(f"Open market positions: {s.open_market_positions}")
            msg_lines.append(f"Open event positions: {s.open_event_positions}")
            if s.fills_count:
                tail = f" ({', '.join(s.tickers_with_fills)})" if s.tickers_with_fills else ""
                msg_lines.append(f"Recent fills (window): {s.fills_count}{tail}")
            if s.settlements_count:
                tail = f" ({', '.join(s.tickers_with_settlements)})" if s.tickers_with_settlements else ""
                msg_lines.append(f"Recent settlements (window): {s.settlements_count}{tail}")
        except Exception:
            pass

    skip_live = _summarize_skips_and_live_spot(run_objs)

    # If we didn't place trades, explain why (from latest cycle diagnostics).
    no_trade_diag: Dict[str, Any] = {}
    try:
        if stats.live_orders == 0:
            latest_trade = None
            latest_run = None
            for o in reversed(run_objs):
                t = o.get("trade")
                if isinstance(t, dict) and t.get("mode") == "trade":
                    latest_trade = t
                    latest_run = o
                    break
            if isinstance(latest_trade, dict):
                # Surface scan timeout/errors (multi-series pre-scan phase).
                try:
                    ci = latest_run.get("cycle_inputs") if isinstance(latest_run, dict) else {}
                    ss = ci.get("scan_summary") if isinstance(ci, dict) else None
                    series = (ss or {}).get("series") if isinstance(ss, dict) else None
                    if isinstance(series, list) and series:
                        timeouts = 0
                        errs = 0
                        for it in series:
                            if not isinstance(it, dict):
                                continue
                            rc = int(it.get("rc") or 0)
                            if rc == 124:
                                timeouts += 1
                            elif rc != 0:
                                errs += 1
                        if timeouts or errs:
                            msg_lines.append(f"Scans: timeouts {timeouts}, errors {errs}")
                            no_trade_diag["scans"] = {"timeouts": int(timeouts), "errors": int(errs)}
                except Exception:
                    pass
                # If the cycle is evaluating multiple series, surface which one was selected.
                try:
                    tbs = None
                    if isinstance(latest_run, dict) and isinstance(latest_run.get("trades_by_series"), dict):
                        tbs = latest_run.get("trades_by_series")
                    elif isinstance(latest_trade.get("trades_by_series"), dict):
                        tbs = latest_trade.get("trades_by_series")
                    if isinstance(tbs, dict) and tbs:
                        sel = None
                        # The selected series is the one with allow_write=true in its inputs.
                        for s, it in tbs.items():
                            tr = None
                            if isinstance(it, dict):
                                tr = it.get("trade") or it.get("scan") or (it.get("scan") if isinstance(it.get("scan"), dict) else None)
                            inp = None
                            if isinstance(tr, dict):
                                inp = tr.get("inputs")
                            if inp is None and isinstance(it, dict) and isinstance((it.get("scan") or {}).get("inputs"), dict):
                                inp = (it.get("scan") or {}).get("inputs")
                            if isinstance(inp, dict) and bool(inp.get("allow_write")):
                                sel = s
                                break
                        if isinstance(sel, str) and sel:
                            msg_lines.append(f"Series selected: {sel}")
                            no_trade_diag["series_selected"] = sel
                except Exception:
                    pass
                diag = latest_trade.get("diagnostics")
                if isinstance(diag, dict):
                    best_pass = diag.get("best_effective_edge_pass_filters") if isinstance(diag.get("best_effective_edge_pass_filters"), dict) else None
                    best_bounds = diag.get("best_effective_edge_in_bounds") if isinstance(diag.get("best_effective_edge_in_bounds"), dict) else None
                    best_any = (
                        diag.get("best_effective_edge_any_quote")
                        if isinstance(diag.get("best_effective_edge_any_quote"), dict)
                        else (diag.get("best_effective_edge") if isinstance(diag.get("best_effective_edge"), dict) else None)
                    )
                    best = best_pass or best_bounds or best_any
                    if isinstance(best, dict) and best.get("ticker"):
                        prefix = "No trades:"
                        if best_pass is None and best_bounds is None and best_any is not None:
                            prefix = "No trades (no quotes in bounds):"
                        try:
                            headline = f"{prefix} best eff edge {float(best.get('effective_edge_bps')):.0f} bps on {best.get('ticker')} {best.get('side')} @ {float(best.get('ask')):.4f}"
                            msg_lines.append(headline)
                            no_trade_diag["headline"] = headline
                        except Exception:
                            pass
                    tb = diag.get("top_blockers")
                    if isinstance(tb, list) and tb:
                        parts = []
                        for it in tb[:5]:
                            if not isinstance(it, dict):
                                continue
                            r = it.get("reason")
                            c = it.get("count")
                            if isinstance(r, str) and isinstance(c, int):
                                parts.append(f"{r}={c}")
                        if parts:
                            msg_lines.append(f"Blockers: {', '.join(parts)}")
                            no_trade_diag["top_blockers"] = tb[:10]
                    totals = diag.get("totals")
                    if isinstance(totals, dict):
                        try:
                            qp = int(totals.get("quotes_present") or 0)
                            pn = int(totals.get("pass_non_edge_filters") or 0)
                            msg_lines.append(f"Diag: quotes {qp}, pass-non-edge {pn}")
                            no_trade_diag["totals"] = {"quotes_present": qp, "pass_non_edge_filters": pn}
                        except Exception:
                            pass

                # Window-level skip + live-spot diagnostics (complements per-cycle blockers).
                try:
                    ts = skip_live.get("top_skips")
                    if isinstance(ts, list) and ts:
                        parts = []
                        for it in ts[:5]:
                            if not isinstance(it, dict):
                                continue
                            r = it.get("reason")
                            c = it.get("count")
                            if isinstance(r, str) and isinstance(c, int):
                                parts.append(f"{r}={c}")
                        if parts:
                            msg_lines.append(f"Skips (window): {', '.join(parts)}")
                            no_trade_diag["top_skips"] = ts[:10]
                    ls = skip_live.get("live_spot")
                    if isinstance(ls, dict):
                        okp = int(ls.get("ok_prices") or 0)
                        att = int(ls.get("attempts_with_fields") or 0)
                        if att > 0:
                            msg_lines.append(f"Live spot (window): ok {okp}/{att}")
                            no_trade_diag["live_spot"] = ls
                except Exception:
                    pass
    except Exception:
        pass

    # Closed-loop learning (persistent): entry quality vs (eventual) realized outcomes.
    cl_report: Optional[Dict[str, Any]] = None
    realized_pnl_usd_approx: Optional[float] = None
    try:
        cl = closed_loop_report(root, window_hours=float(args.window_hours))
        cl_report = cl if isinstance(cl, dict) else None
        if isinstance(cl.get("avg_effective_edge_bps"), (int, float)):
            msg_lines.append(f"Avg effective edge (window): {float(cl['avg_effective_edge_bps']):.0f} bps")
        if isinstance(cl.get("avg_implied_win_prob"), (int, float)):
            msg_lines.append(f"Avg implied win prob (window): {float(cl['avg_implied_win_prob']):.2f}")
        if isinstance(cl.get("settled_orders"), int) and int(cl["settled_orders"]) > 0:
            wr = cl.get("win_rate")
            if isinstance(wr, (int, float)):
                msg_lines.append(f"Settled win-rate (window): {float(wr):.2f}")
            ap = cl.get("avg_implied_win_prob_settled")
            if isinstance(ap, (int, float)):
                msg_lines.append(f"Avg implied win prob (settled): {float(ap):.2f}")
            bd = cl.get("breakdowns")
            if isinstance(bd, dict):
                by_tte = bd.get("by_tte")
                by_strike = bd.get("by_strike")
                if isinstance(by_tte, dict) and by_tte:
                    best = max(by_tte.items(), key=lambda kv: float((kv[1] or {}).get("pnl") or 0.0))
                    try:
                        msg_lines.append(f"Best TTE bucket: {best[0]} pnl {_format_usd(float(best[1]['pnl']))} (n {int(best[1]['n'])})")
                    except Exception:
                        pass
                if isinstance(by_strike, dict) and by_strike:
                    best = max(by_strike.items(), key=lambda kv: float((kv[1] or {}).get("pnl") or 0.0))
                    try:
                        msg_lines.append(f"Best strike bucket: {best[0]} pnl {_format_usd(float(best[1]['pnl']))} (n {int(best[1]['n'])})")
                    except Exception:
                        pass
            sugg = cl.get("suggestions")
            if isinstance(sugg, list) and sugg:
                # Only include one short suggestion in Telegram digest to avoid spam.
                s0 = sugg[0]
                if isinstance(s0, str) and s0.strip():
                    msg_lines.append(f"Note: {s0.strip()}")
        if isinstance(cl.get("realized_pnl_usd_approx"), (int, float)):
            msg_lines.append(f"Realized P/L (settled, approx): {_format_usd(float(cl['realized_pnl_usd_approx']))}")
            realized_pnl_usd_approx = float(cl["realized_pnl_usd_approx"])
        # Light breakdown hints.
        mt = cl.get("market_type_counts")
        if isinstance(mt, dict) and mt:
            parts = []
            for k, v in list(mt.items())[:3]:
                try:
                    parts.append(f"{k}:{int(v)}")
                except Exception:
                    continue
            if parts:
                msg_lines.append(f"Market mix (window): {', '.join(parts)}")
        if isinstance(cl.get("avg_time_to_expiry_min"), (int, float)):
            msg_lines.append(f"Avg time-to-expiry at entry: {float(cl['avg_time_to_expiry_min']):.0f} min")
        if isinstance(cl.get("avg_abs_strike_distance_pct"), (int, float)):
            msg_lines.append(f"Avg strike distance at entry: {float(cl['avg_abs_strike_distance_pct']):.2f}%")
    except Exception:
        pass

    # Ledger health: show whether we are seeing settlements we can't attribute/parse.
    try:
        led = load_ledger(root)
        um = led.get("unmatched_settlements") if isinstance(led, dict) else None
        if isinstance(um, list) and um:
            now = int(time.time())
            start = now - int(max(60.0, float(args.window_hours) * 3600.0))
            recent = 0
            for it in um:
                if isinstance(it, dict) and int(it.get("ts_unix") or 0) >= start:
                    recent += 1
            if recent:
                msg_lines.append(f"Unmatched settlements (window): {recent} (total {len(um)})")
    except Exception:
        pass

    # Conservative "parameter recs" (do not auto-apply; just persist and optionally surface one hint).
    param_recs: List[Dict[str, Any]] = []
    try:
        # Pull current params from the most recent trade artifact (if present).
        current_inputs = None
        for o in reversed(run_objs):
            t = o.get("trade")
            if isinstance(t, dict) and isinstance(t.get("inputs"), dict):
                current_inputs = t.get("inputs")
                break
        if isinstance(cl_report, dict):
            param_recs = _param_recommendations(cl_report, current_inputs=current_inputs)
            if param_recs:
                # Keep Telegram short: only 1 line.
                r0 = param_recs[0]
                if isinstance(r0, dict) and isinstance(r0.get("env"), str) and isinstance(r0.get("value"), str):
                    msg_lines.append(f"Param rec: set {r0['env']}={r0['value']}")
    except Exception:
        param_recs = []

    # Auto-tune status (bounded auto-apply after enough settled trades, with rollback).
    try:
        tp = os.path.join(root, "tmp", "kalshi_ref_arb", "tune_state.json")
        ts_obj = _load_json(tp, default={})
        if isinstance(ts_obj, dict) and bool(ts_obj.get("enabled")):
            st = str(ts_obj.get("status") or "unknown")
            msg_lines.append(f"Auto-tune: ON ({st})")
    except Exception:
        pass

    # Deployed downside risk (approx): sum of our tracked notional per market (cost basis), from local state.
    rs = _load_risk_state_summary(state_path)
    if rs.get("deployed_notional_usd") is not None:
        msg_lines.append(
            f"Deployed notional (approx downside): {_format_usd(float(rs['deployed_notional_usd']))} across {int(rs.get('markets') or 0)} markets"
        )

    # Realized cash delta from settlements observed in run artifacts (best-effort, deduped).
    all_settlements: List[Dict[str, Any]] = []
    settlements_cash_delta_usd_window: Optional[float] = None
    for o in run_objs:
        post = o.get("post")
        if not isinstance(post, dict):
            continue
        st = post.get("settlements")
        if not isinstance(st, dict):
            continue
        lst = st.get("settlements")
        if isinstance(lst, list):
            for it in lst:
                if isinstance(it, dict):
                    all_settlements.append(it)
    if all_settlements:
        all_settlements = dedupe_settlements(all_settlements)
        ss = settlement_cash_delta_usd({"settlements": {"settlements": all_settlements}})
        cd = ss.get("cash_delta_usd")
        if isinstance(cd, (int, float)):
            settlements_cash_delta_usd_window = float(cd)
            tail = ""
            if isinstance(ss.get("tickers"), list) and ss["tickers"]:
                tail = f" ({', '.join([str(x) for x in ss['tickers'][:5]])})"
            msg_lines.append(f"Settlements cash delta (approx): {_format_usd(float(cd))}{tail}")

    # Entry-quality summary: edge-at-entry vs fill quality (from run artifacts).
    placed_live: List[Dict[str, Any]] = []
    for o in run_objs:
        trade = o.get("trade")
        if not isinstance(trade, dict):
            continue
        placed = trade.get("placed") or []
        if not isinstance(placed, list):
            continue
        post = o.get("post") if isinstance(o.get("post"), dict) else {}
        for p in placed:
            if not isinstance(p, dict) or p.get("mode") != "live":
                continue
            order = p.get("order") if isinstance(p.get("order"), dict) else {}
            order_id = p.get("order_id") if isinstance(p.get("order_id"), str) else ""
            edge_bps = p.get("edge_bps")
            try:
                edge_bps_f = float(edge_bps) if edge_bps is not None else None
            except Exception:
                edge_bps_f = None
            limit_px = None
            try:
                limit_px = float(order.get("price_dollars")) if isinstance(order.get("price_dollars"), str) else None
            except Exception:
                limit_px = None
            fills = match_fills_for_order(post, order_id) if (order_id and isinstance(post, dict)) else {}
            avg_fill = fills.get("avg_price_dollars")
            fee_total = fills.get("fee_total_usd")
            try:
                avg_fill_f = float(avg_fill) if isinstance(avg_fill, (int, float)) else None
            except Exception:
                avg_fill_f = None
            try:
                fee_total_f = float(fee_total) if isinstance(fee_total, (int, float)) else None
            except Exception:
                fee_total_f = None
            slippage_bps = None
            if (limit_px is not None) and (avg_fill_f is not None):
                slippage_bps = (avg_fill_f - limit_px) * 10_000.0
            placed_live.append(
                {
                    "ticker": order.get("ticker"),
                    "side": order.get("side"),
                    "count": order.get("count"),
                    "order_id": order_id,
                    "edge_bps": edge_bps_f,
                    "limit_price": limit_px,
                    "fills_count": int(fills.get("fills_count") or 0),
                    "avg_fill_price": avg_fill_f,
                    "fee_total_usd": fee_total_f,
                    "slippage_bps": slippage_bps,
                    "t_years": p.get("t_years"),
                }
            )

    if placed_live:
        n = len(placed_live)
        filled_orders = sum(1 for x in placed_live if int(x.get("fills_count") or 0) > 0)
        filled_ct = sum(int(x.get("fills_count") or 0) for x in placed_live)
        msg_lines.append(f"Trades (window): placed {n}, filled {filled_orders} (contracts {filled_ct})")
        edges = [float(x["edge_bps"]) for x in placed_live if isinstance(x.get("edge_bps"), (int, float))]
        if edges:
            msg_lines.append(f"Avg edge at entry: {sum(edges)/float(len(edges)):.0f} bps")
        slips = [float(x["slippage_bps"]) for x in placed_live if isinstance(x.get("slippage_bps"), (int, float))]
        if slips:
            msg_lines.append(f"Avg fill slippage: {sum(slips)/float(len(slips)):.0f} bps (price-bps)")
        # Fee awareness: show aggregate fees vs notional for fills in-window.
        fees = []
        notionals = []
        for x in placed_live:
            try:
                fc = int(x.get("fills_count") or 0)
            except Exception:
                fc = 0
            if fc <= 0:
                continue
            try:
                avgp = float(x.get("avg_fill_price"))
            except Exception:
                avgp = None
            try:
                ft = float(x.get("fee_total_usd"))
            except Exception:
                ft = None
            if avgp is not None:
                notionals.append(float(avgp) * float(fc))
            if ft is not None:
                fees.append(float(ft))
        if notionals and fees:
            nsum = sum(notionals)
            fsum = sum(fees)
            pct = (fsum / nsum) * 100.0 if nsum > 0 else None
            if pct is not None:
                msg_lines.append(f"Fees (window): {_format_usd(fsum)} on {_format_usd(nsum)} notional ({pct:.1f}%)")
                fees_total_usd_window = float(fsum)
                fees_pct_window = float(pct)
        ttes = []
        for x in placed_live:
            try:
                t = float(x.get("t_years"))
                ttes.append(t * 365.0 * 24.0 * 60.0)
            except Exception:
                continue
        if ttes:
            msg_lines.append(f"Avg time-to-expiry: {sum(ttes)/float(len(ttes)):.0f} min")

    # Mark-to-market estimate from latest open positions (read-only public market quotes).
    mtm_liq_value_usd: Optional[float] = None
    positions_top: List[Dict[str, Any]] = []
    if isinstance(latest_post, dict):
        try:
            base_url = "https://api.elections.kalshi.com"
            inp = latest_post.get("inputs")
            if isinstance(inp, dict) and isinstance(inp.get("kalshi_base_url"), str) and inp.get("kalshi_base_url"):
                base_url = str(inp.get("kalshi_base_url"))
            kc = KalshiClient(base_url=base_url)
            counts = extract_market_position_counts(latest_post)
            # Exposure summary (best-effort): rank open-position tickers by our tracked notional (state.json).
            try:
                st = _load_json(state_path, default={})
                mk = st.get("markets") if isinstance(st, dict) else None
                if not isinstance(mk, dict):
                    mk = {}
            except Exception:
                mk = {}
            if isinstance(counts, dict) and counts:
                tmp = []
                for t, c in counts.items():
                    if not isinstance(c, dict):
                        continue
                    y = int(c.get("yes") or 0)
                    n = int(c.get("no") or 0)
                    if y <= 0 and n <= 0:
                        continue
                    notional = None
                    mv = mk.get(t) if isinstance(mk, dict) else None
                    if isinstance(mv, dict) and isinstance(mv.get("notional_usd"), (int, float)):
                        notional = float(mv.get("notional_usd"))
                    tmp.append({"ticker": t, "yes": y, "no": n, "notional_usd": notional})
                tmp.sort(key=lambda it: float(it.get("notional_usd") or -1.0), reverse=True)
                positions_top = tmp[:8]
            if counts:
                liq_value = 0.0
                missing_bids = 0
                legs = 0
                for t, c in list(counts.items())[:20]:
                    m = kc.get_market(t)
                    if m is None:
                        continue
                    y = int((c or {}).get("yes") or 0)
                    n = int((c or {}).get("no") or 0)
                    if y > 0:
                        legs += 1
                        if m.yes_bid is not None:
                            liq_value += float(m.yes_bid) * float(y)
                        else:
                            missing_bids += 1
                    if n > 0:
                        legs += 1
                        if m.no_bid is not None:
                            liq_value += float(m.no_bid) * float(n)
                        else:
                            missing_bids += 1
                if legs > 0 and missing_bids > 0 and liq_value <= 0.0:
                    msg_lines.append(f"MTM liquidation value: unavailable (no bids for {missing_bids}/{legs} position legs)")
                else:
                    msg_lines.append(f"MTM liquidation value (est, bids): {_format_usd(liq_value)}")
                    mtm_liq_value_usd = float(liq_value)
                    if legs > 0 and missing_bids > 0:
                        msg_lines.append(f"MTM note: missing bids for {missing_bids}/{legs} position legs")
        except Exception:
            pass

    # Track window fee totals (best-effort), so HTML can show them even if message parsing changes.
    fees_total_usd_window: Optional[float] = None
    fees_pct_window: Optional[float] = None
    # (Values get set above if we observed fills; otherwise stay None.)

    # Last cycle / issue summary for WARN/PAUSED emails.
    last_cycle_ts_et = ""
    last_issue = ""
    try:
        if run_objs:
            ts_last = int(run_objs[-1].get("ts_unix") or 0)
            if ts_last > 0:
                dt_et = datetime.datetime.fromtimestamp(ts_last, tz=ZoneInfo("America/New_York"))
                last_cycle_ts_et = dt_et.strftime("%Y-%m-%d %I:%M %p ET")
        for o in reversed(run_objs):
            bal_rc = int(o.get("balance_rc") or 0)
            trade_rc = int(o.get("trade_rc") or 0)
            post_rc = int(o.get("post_rc") or 0)
            if bal_rc == 0 and trade_rc == 0 and post_rc == 0:
                continue
            t = o.get("trade") if isinstance(o.get("trade"), dict) else {}
            st = str(t.get("status") or "")
            rsn = str(t.get("reason") or "")
            if st == "refused" and rsn:
                last_issue = f"Cycle refused: {rsn} (trade_rc={trade_rc})"
            elif trade_rc != 0:
                last_issue = f"Trade step failed (trade_rc={trade_rc})"
            elif bal_rc != 0:
                last_issue = f"Balance step failed (balance_rc={bal_rc})"
            elif post_rc != 0:
                last_issue = f"Post snapshot failed (post_rc={post_rc})"
            else:
                last_issue = "Non-zero cycle return code observed"
            break
    except Exception:
        pass

    payload = {
        "mode": "kalshi_digest",
        "timestamp_unix": now,
        "window_hours": float(args.window_hours),
        "stats": {
            "cycles": stats.cycles,
            "live_orders": stats.live_orders,
            "live_notional_usd": stats.live_notional_usd,
            "errors": stats.errors,
            "order_failed": stats.order_failed,
            "kill_switch_seen": stats.kill_switch_seen,
        },
        "cash_usd": avail_usd,
        "portfolio_value_usd": port_usd,
        "kill_switch_on": kill_on,
        "summary": {
            "status": status,
            "cash_usd": avail_usd,
            "portfolio_value_usd": port_usd,
            "deployed_notional_usd": rs.get("deployed_notional_usd"),
            "deployed_markets": rs.get("markets"),
            "realized_pnl_usd_approx": realized_pnl_usd_approx,
            "settlements_cash_delta_usd_window": settlements_cash_delta_usd_window,
            "mtm_liq_value_usd": mtm_liq_value_usd,
            "fees_total_usd_window": fees_total_usd_window,
            "fees_pct_window": fees_pct_window,
            "sigma_avg": sigma_s.get("avg_sigma_arg"),
            "sigma_mode": sigma_s.get("mode"),
            "kill_switch_on": bool(kill_on),
            "cooldown_on": bool(cooldown_on),
            "last_cycle_ts_et": last_cycle_ts_et,
            "last_issue": last_issue,
            "positions_top": positions_top,
        },
        "today": {
            "cycles": today_stats.cycles,
            "live_orders": today_stats.live_orders,
            "live_notional_usd": today_stats.live_notional_usd,
            "errors": today_stats.errors,
            "order_failed": today_stats.order_failed,
            "realized_pnl_usd_settled": today_realized_pnl,
        },
        "no_trade": no_trade_diag if isinstance(no_trade_diag, dict) and no_trade_diag else {},
        "sweep_rollup_24h": sweep_roll if isinstance(sweep_roll, dict) else None,
        "param_recommendations": param_recs,
        "message": "\n".join(msg_lines),
    }

    # Persist payload for audit/learning (gitignored tmp/).
    try:
        out_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "digests")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{now}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
    except Exception:
        pass

    # Persist param recs separately so we can trend them over time.
    try:
        if param_recs:
            out_dir = os.path.join(root, "tmp", "kalshi_ref_arb", "recommendations")
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, f"{now}.json"), "w", encoding="utf-8") as f:
                json.dump({"timestamp_unix": now, "window_hours": float(args.window_hours), "recs": param_recs}, f, indent=2, sort_keys=True)
                f.write("\n")
    except Exception:
        pass

    send_tg = bool(args.send or args.send_telegram)
    send_email = bool(args.send_email)

    # If no sends requested, just print JSON.
    if not (send_tg or send_email):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    # Telegram send (optional).
    if send_tg:
        chat_id = _telegram_chat_id()
        if chat_id is None:
            print("ERROR: could not determine Telegram chat id (set ORION_TELEGRAM_CHAT_ID).", file=os.sys.stderr)
            return 2
        ok = _send_telegram(int(chat_id), payload["message"], cwd=root)
        if not ok:
            print("ERROR: telegram send failed", file=os.sys.stderr)
            return 3

    # Email send (optional).
    if send_email:
        to_email = (args.email_to or "").strip() or (_email_to_default() or "")
        if not to_email:
            print("ERROR: missing --email-to (or env KALSHI_ARB_DIGEST_EMAIL_TO/AGENTMAIL_TO).", file=os.sys.stderr)
            return 4
        try:
            import datetime

            subj_ts = datetime.datetime.fromtimestamp(now).astimezone().strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            subj_ts = str(now)
        subject = f"ORION Kalshi digest ({int(args.window_hours)}h) @ {subj_ts}"
        if bool(args.email_html):
            html = _digest_html(subject=subject, window_hours=float(args.window_hours), payload=payload, now_unix=now)
            ok = _send_email_html_via_agentmail(to_email, subject, text_body=payload["message"], html_body=html, cwd=root)
        else:
            ok = _send_email_via_agentmail(to_email, subject, payload["message"], cwd=root)
        if not ok:
            # If email sending fails, alert via Telegram (best-effort) so Cory knows to investigate.
            try:
                chat_id = _telegram_chat_id()
                if chat_id is not None:
                    _send_telegram(
                        int(chat_id),
                        "ORION: Kalshi digest email FAILED. Check tmp/kalshi_ref_arb/last_email_send.json",
                        cwd=root,
                    )
            except Exception:
                pass
            print("ERROR: email send failed", file=os.sys.stderr)
            return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
