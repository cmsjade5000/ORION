from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .kalshi_ledger import load_ledger  # type: ignore


OVERRIDE_PATH_REL = os.path.join("tmp", "kalshi_ref_arb", "params_override.json")
TUNE_STATE_PATH_REL = os.path.join("tmp", "kalshi_ref_arb", "tune_state.json")


@dataclass(frozen=True)
class TuneBounds:
    min_edge_bps: Tuple[int, int] = (80, 250)
    uncertainty_bps: Tuple[int, int] = (20, 140)
    persistence_cycles: Tuple[int, int] = (1, 3)
    min_liquidity_usd: Tuple[int, int] = (20, 300)
    max_spread: Tuple[float, float] = (0.05, 0.12)
    limit: Tuple[int, int] = (50, 200)
    min_price: Tuple[float, float] = (0.01, 0.05)


BOUNDS = TuneBounds()


def _repo_path(repo_root: str, rel: str) -> str:
    return os.path.join(repo_root, rel)


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            out = dict(default)
            out.update(obj)
            return out
    except Exception:
        pass
    return dict(default)


def _save_json_atomic(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def load_overrides(repo_root: str) -> Dict[str, str]:
    p = _repo_path(repo_root, OVERRIDE_PATH_REL)
    obj = _load_json(p, default={})
    params = obj.get("params")
    if isinstance(params, dict):
        out: Dict[str, str] = {}
        for k, v in params.items():
            if isinstance(k, str) and k.startswith("KALSHI_ARB_"):
                out[k] = str(v)
        return out
    return {}


def apply_overrides_to_environ(params: Dict[str, str]) -> None:
    for k, v in params.items():
        if isinstance(k, str) and k.startswith("KALSHI_ARB_"):
            os.environ[k] = str(v)


def _get_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return int(default)
    try:
        return int(float(str(raw).strip()))
    except Exception:
        return int(default)


def _clamp_int(x: int, lo: int, hi: int) -> int:
    return max(int(lo), min(int(hi), int(x)))


def _clamp_float(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


def _settled_orders(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    orders = ledger.get("orders")
    if not isinstance(orders, dict):
        return []
    out: List[Dict[str, Any]] = []
    for _, o in orders.items():
        if not isinstance(o, dict):
            continue
        if isinstance(o.get("settlement"), dict):
            out.append(o)
    out.sort(key=lambda o: int(o.get("ts_unix") or 0))
    return out


def _metrics_for_orders(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    settled = 0
    wins = 0
    losses = 0
    pnl = 0.0
    pnl_any = False
    probs: List[float] = []
    brier: List[float] = []

    for o in orders:
        st = o.get("settlement") if isinstance(o.get("settlement"), dict) else None
        if not isinstance(st, dict):
            continue
        settled += 1
        parsed = st.get("parsed") if isinstance(st.get("parsed"), dict) else {}
        outcome_yes = parsed.get("outcome_yes")
        side = o.get("side")

        try:
            p_yes_f = float(o.get("p_yes")) if o.get("p_yes") is not None else None
        except Exception:
            p_yes_f = None

        win = None
        if isinstance(outcome_yes, bool) and side in ("yes", "no"):
            win = bool(outcome_yes) if side == "yes" else (not bool(outcome_yes))
        if win is True:
            wins += 1
        elif win is False:
            losses += 1

        cd = parsed.get("cash_delta_usd")
        if isinstance(cd, (int, float)):
            pnl_any = True
            pnl += float(cd)

        if isinstance(win, bool) and p_yes_f is not None and side in ("yes", "no"):
            p = float(p_yes_f if side == "yes" else (1.0 - p_yes_f))
            probs.append(p)
            y = 1.0 if win else 0.0
            brier.append((p - y) ** 2)

    wr = (float(wins) / float(max(1, wins + losses))) if (wins + losses) else None
    ap = (sum(probs) / float(len(probs))) if probs else None
    brier_s = (sum(brier) / float(len(brier))) if brier else None
    pnl_out = float(pnl) if pnl_any else None
    pnl_per = (float(pnl) / float(max(1, settled))) if pnl_any and settled else None
    return {
        "settled_orders": int(settled),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": wr,
        "avg_implied_win_prob_settled": ap,
        "brier_score_settled": brier_s,
        "realized_pnl_usd_approx": pnl_out,
        "realized_pnl_per_trade_usd_approx": pnl_per,
    }


def _current_params_from_env() -> Dict[str, str]:
    keys = [
        "KALSHI_ARB_MIN_EDGE_BPS",
        "KALSHI_ARB_UNCERTAINTY_BPS",
        "KALSHI_ARB_PERSISTENCE_CYCLES",
        "KALSHI_ARB_MIN_LIQUIDITY_USD",
        "KALSHI_ARB_MAX_SPREAD",
        "KALSHI_ARB_LIMIT",
        "KALSHI_ARB_MIN_PRICE",
    ]
    out: Dict[str, str] = {}
    for k in keys:
        v = os.environ.get(k)
        if v is not None and str(v).strip():
            out[k] = str(v).strip()
    # Defaults match the cycle defaults.
    out.setdefault("KALSHI_ARB_MIN_EDGE_BPS", "120")
    out.setdefault("KALSHI_ARB_UNCERTAINTY_BPS", "50")
    out.setdefault("KALSHI_ARB_PERSISTENCE_CYCLES", "2")
    out.setdefault("KALSHI_ARB_MIN_LIQUIDITY_USD", "200")
    out.setdefault("KALSHI_ARB_MAX_SPREAD", "0.05")
    out.setdefault("KALSHI_ARB_LIMIT", "20")
    out.setdefault("KALSHI_ARB_MIN_PRICE", "0.05")
    return out


def _bounded(params: Dict[str, str]) -> Dict[str, str]:
    out = dict(params)
    out["KALSHI_ARB_MIN_EDGE_BPS"] = str(
        _clamp_int(int(float(out.get("KALSHI_ARB_MIN_EDGE_BPS") or 120)), *BOUNDS.min_edge_bps)
    )
    out["KALSHI_ARB_UNCERTAINTY_BPS"] = str(
        _clamp_int(int(float(out.get("KALSHI_ARB_UNCERTAINTY_BPS") or 50)), *BOUNDS.uncertainty_bps)
    )
    out["KALSHI_ARB_PERSISTENCE_CYCLES"] = str(
        _clamp_int(int(float(out.get("KALSHI_ARB_PERSISTENCE_CYCLES") or 2)), *BOUNDS.persistence_cycles)
    )
    out["KALSHI_ARB_MIN_LIQUIDITY_USD"] = str(
        _clamp_int(int(float(out.get("KALSHI_ARB_MIN_LIQUIDITY_USD") or 200)), *BOUNDS.min_liquidity_usd)
    )
    out["KALSHI_ARB_MAX_SPREAD"] = (
        f"{_clamp_float(float(out.get('KALSHI_ARB_MAX_SPREAD') or 0.05), *BOUNDS.max_spread):.4f}".rstrip("0").rstrip(".")
    )
    out["KALSHI_ARB_LIMIT"] = str(_clamp_int(int(float(out.get("KALSHI_ARB_LIMIT") or 20)), *BOUNDS.limit))
    out["KALSHI_ARB_MIN_PRICE"] = (
        f"{_clamp_float(float(out.get('KALSHI_ARB_MIN_PRICE') or 0.05), *BOUNDS.min_price):.4f}".rstrip("0").rstrip(".")
    )
    return out


def recommend_params(*, baseline: Dict[str, Any], current: Dict[str, str]) -> List[Dict[str, Any]]:
    """Return <=2 bounded, incremental changes."""
    recs: List[Dict[str, Any]] = []
    settled = int(baseline.get("settled_orders") or 0)
    if settled <= 0:
        return []

    wr = baseline.get("win_rate")
    ap = baseline.get("avg_implied_win_prob_settled")
    brier = baseline.get("brier_score_settled")
    pnl = baseline.get("realized_pnl_usd_approx")

    cur_edge = int(float(current.get("KALSHI_ARB_MIN_EDGE_BPS") or 120))
    cur_unc = int(float(current.get("KALSHI_ARB_UNCERTAINTY_BPS") or 50))
    cur_pers = int(float(current.get("KALSHI_ARB_PERSISTENCE_CYCLES") or 2))

    if isinstance(wr, (int, float)) and isinstance(ap, (int, float)) and wr + 0.05 < ap:
        nxt = _clamp_int(cur_unc + 10, *BOUNDS.uncertainty_bps)
        if nxt != cur_unc:
            recs.append({"env": "KALSHI_ARB_UNCERTAINTY_BPS", "value": str(nxt), "why": "Win-rate below implied; add buffer."})
    if isinstance(brier, (int, float)) and brier > 0.25:
        nxt = _clamp_int(cur_unc + 10, *BOUNDS.uncertainty_bps)
        if nxt != cur_unc:
            recs.append({"env": "KALSHI_ARB_UNCERTAINTY_BPS", "value": str(nxt), "why": "High Brier; add buffer."})
    if isinstance(pnl, (int, float)) and float(pnl) < 0.0:
        nxtp = _clamp_int(cur_pers + 1, *BOUNDS.persistence_cycles)
        if nxtp != cur_pers:
            recs.append({"env": "KALSHI_ARB_PERSISTENCE_CYCLES", "value": str(nxtp), "why": "Negative P/L; require more persistence."})
        nxte = _clamp_int(cur_edge + 10, *BOUNDS.min_edge_bps)
        if nxte != cur_edge:
            recs.append({"env": "KALSHI_ARB_MIN_EDGE_BPS", "value": str(nxte), "why": "Negative P/L; require clearer edge."})

    # If we outperform implied odds over a meaningful sample, cautiously loosen min-edge a hair.
    if isinstance(pnl, (int, float)) and float(pnl) > 0.0 and isinstance(wr, (int, float)) and isinstance(ap, (int, float)):
        if wr > ap + 0.05 and settled >= 20:
            nxt = _clamp_int(cur_edge - 5, *BOUNDS.min_edge_bps)
            if nxt != cur_edge:
                recs.append({"env": "KALSHI_ARB_MIN_EDGE_BPS", "value": str(nxt), "why": "Performance above implied; slightly lower min-edge."})

    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in recs:
        e = r.get("env")
        if not isinstance(e, str) or not e.startswith("KALSHI_ARB_"):
            continue
        if e in seen:
            continue
        seen.add(e)
        out.append(r)
        if len(out) >= 2:
            break
    return out


def _load_tune_state(repo_root: str) -> Dict[str, Any]:
    p = _repo_path(repo_root, TUNE_STATE_PATH_REL)
    state = _load_json(
        p,
        default={
            "version": 2,
            "enabled": False,
            "min_settled": 20,
            "eval_settled": 10,
            "last_apply_ts": 0,
            "status": "idle",
            "current_params": {},
            "prev_params": {},
            "baseline": {},
            "champion": {"name": "champion", "params": {}, "baseline": {}, "applied_ts": 0},
            "challenger": {
                "name": "challenger",
                "status": "idle",
                "params": {},
                "baseline": {},
                "eval_metrics": {},
                "applied_ts": 0,
                "completed_ts": 0,
            },
        },
    )
    if not isinstance(state.get("champion"), dict):
        state["champion"] = {"name": "champion", "params": {}, "baseline": {}, "applied_ts": 0}
    if not isinstance(state.get("challenger"), dict):
        state["challenger"] = {
            "name": "challenger",
            "status": "idle",
            "params": {},
            "baseline": {},
            "eval_metrics": {},
            "applied_ts": 0,
            "completed_ts": 0,
        }

    # Backward-compat: lift old current/prev schema into champion/challenger fields.
    cur = state.get("current_params") if isinstance(state.get("current_params"), dict) else {}
    prev = state.get("prev_params") if isinstance(state.get("prev_params"), dict) else {}
    baseline = state.get("baseline") if isinstance(state.get("baseline"), dict) else {}
    champion = state.get("champion") if isinstance(state.get("champion"), dict) else {}
    challenger = state.get("challenger") if isinstance(state.get("challenger"), dict) else {}

    if not isinstance(champion.get("params"), dict) or not champion.get("params"):
        champion["params"] = dict(prev if prev else cur)
    if not isinstance(champion.get("baseline"), dict) or not champion.get("baseline"):
        champion["baseline"] = dict(baseline)
    champion.setdefault("name", "champion")
    champion["applied_ts"] = int(champion.get("applied_ts") or 0)

    challenger.setdefault("name", "challenger")
    challenger.setdefault("status", "idle")
    if not isinstance(challenger.get("params"), dict):
        challenger["params"] = {}
    if not isinstance(challenger.get("baseline"), dict):
        challenger["baseline"] = {}
    if not isinstance(challenger.get("eval_metrics"), dict):
        challenger["eval_metrics"] = {}
    challenger["applied_ts"] = int(challenger.get("applied_ts") or 0)
    challenger["completed_ts"] = int(challenger.get("completed_ts") or 0)

    state["champion"] = champion
    state["challenger"] = challenger
    state.setdefault("version", 2)
    return state


def _save_tune_state(repo_root: str, state: Dict[str, Any]) -> None:
    p = _repo_path(repo_root, TUNE_STATE_PATH_REL)
    _save_json_atomic(p, state)


def _load_override_obj(repo_root: str) -> Dict[str, Any]:
    p = _repo_path(repo_root, OVERRIDE_PATH_REL)
    return _load_json(p, default={"version": 1, "applied_ts": 0, "params": {}})


def _save_override_obj(repo_root: str, obj: Dict[str, Any]) -> None:
    p = _repo_path(repo_root, OVERRIDE_PATH_REL)
    _save_json_atomic(p, obj)


def _variant_payload(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(obj.get("name") or ""),
        "status": str(obj.get("status") or ""),
        "params": dict(obj.get("params") or {}) if isinstance(obj.get("params"), dict) else {},
        "baseline": dict(obj.get("baseline") or {}) if isinstance(obj.get("baseline"), dict) else {},
        "eval_metrics": dict(obj.get("eval_metrics") or {}) if isinstance(obj.get("eval_metrics"), dict) else {},
        "applied_ts": int(obj.get("applied_ts") or 0),
        "completed_ts": int(obj.get("completed_ts") or 0),
    }


def _active_variant(state: Dict[str, Any]) -> str:
    challenger = state.get("challenger") if isinstance(state.get("challenger"), dict) else {}
    ch_status = str(challenger.get("status") or "").strip().lower()
    if int(state.get("last_apply_ts") or 0) > 0 and ch_status in ("evaluating", "applied"):
        return "challenger"
    return "champion"


def _status_payload(
    state: Dict[str, Any],
    *,
    settled_total: Optional[int],
    recs: Optional[List[Dict[str, Any]]] = None,
    eval_progress: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "enabled": bool(state.get("enabled")),
        "status": str(state.get("status") or "unknown"),
        "settled_total": int(settled_total) if isinstance(settled_total, int) else None,
        "active_variant": _active_variant(state),
        "champion": _variant_payload(state.get("champion") if isinstance(state.get("champion"), dict) else {}),
        "challenger": _variant_payload(state.get("challenger") if isinstance(state.get("challenger"), dict) else {}),
    }
    if isinstance(recs, list) and recs:
        out["recs"] = recs
    if isinstance(eval_progress, dict) and eval_progress:
        out["eval_progress"] = {
            "have": int(eval_progress.get("have") or 0),
            "target": int(eval_progress.get("target") or 0),
        }
    return out


def maybe_autotune(repo_root: str) -> Dict[str, Any]:
    """Auto-apply bounded param changes after enough settled data; rollback if worse."""
    enabled = str(os.environ.get("KALSHI_ARB_TUNE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")
    state = _load_tune_state(repo_root)
    state["enabled"] = bool(enabled)
    state["min_settled"] = int(_get_env_int("KALSHI_ARB_TUNE_MIN_SETTLED", int(state.get("min_settled") or 20)))
    state["eval_settled"] = int(_get_env_int("KALSHI_ARB_TUNE_EVAL_SETTLED", int(state.get("eval_settled") or 10)))

    if not enabled:
        state["status"] = "disabled"
        _save_tune_state(repo_root, state)
        return _status_payload(state, settled_total=None)

    led = load_ledger(repo_root)
    settled_all = _settled_orders(led)
    settled_n = len(settled_all)
    min_settled = int(state.get("min_settled") or 20)
    eval_settled = int(state.get("eval_settled") or 10)
    now = int(time.time())

    champion = state.get("champion") if isinstance(state.get("champion"), dict) else {"name": "champion", "params": {}, "baseline": {}}
    challenger = state.get("challenger") if isinstance(state.get("challenger"), dict) else {"name": "challenger", "status": "idle", "params": {}}

    # Backward compatibility fields stay updated.
    if not isinstance(champion.get("params"), dict) or not champion.get("params"):
        champion["params"] = _bounded(_current_params_from_env())
    if not isinstance(champion.get("baseline"), dict):
        champion["baseline"] = {}
    champion.setdefault("name", "champion")
    champion["applied_ts"] = int(champion.get("applied_ts") or 0)
    challenger.setdefault("name", "challenger")
    challenger.setdefault("status", "idle")
    if not isinstance(challenger.get("params"), dict):
        challenger["params"] = {}
    if not isinstance(challenger.get("baseline"), dict):
        challenger["baseline"] = {}
    if not isinstance(challenger.get("eval_metrics"), dict):
        challenger["eval_metrics"] = {}
    challenger["applied_ts"] = int(challenger.get("applied_ts") or 0)
    challenger["completed_ts"] = int(challenger.get("completed_ts") or 0)

    state["champion"] = champion
    state["challenger"] = challenger
    state["current_params"] = dict(champion.get("params") if isinstance(champion.get("params"), dict) else {})
    state["prev_params"] = {}
    state["baseline"] = dict(champion.get("baseline") if isinstance(champion.get("baseline"), dict) else {})

    # Challenger evaluation / rollback gate.
    last_apply = int(state.get("last_apply_ts") or 0)
    ch_status = str(challenger.get("status") or "").strip().lower()
    if last_apply and ch_status in ("evaluating", "applied") and isinstance(challenger.get("params"), dict) and challenger.get("params"):
        post_orders = [o for o in settled_all if int(o.get("ts_unix") or 0) >= last_apply]
        eval_have = len(post_orders)
        if len(post_orders) >= eval_settled:
            post_metrics = _metrics_for_orders(post_orders[-eval_settled:])
            baseline = challenger.get("baseline") if isinstance(challenger.get("baseline"), dict) else {}
            if not baseline:
                baseline = champion.get("baseline") if isinstance(champion.get("baseline"), dict) else {}
            base_ppt = baseline.get("realized_pnl_per_trade_usd_approx") if isinstance(baseline, dict) else None
            post_ppt = post_metrics.get("realized_pnl_per_trade_usd_approx")
            base_wr = baseline.get("win_rate") if isinstance(baseline, dict) else None
            post_wr = post_metrics.get("win_rate")
            base_brier = baseline.get("brier_score_settled") if isinstance(baseline, dict) else None
            post_brier = post_metrics.get("brier_score_settled")

            worse = False
            if isinstance(base_ppt, (int, float)) and isinstance(post_ppt, (int, float)) and float(post_ppt) < float(base_ppt) - 0.05:
                worse = True
            if isinstance(base_wr, (int, float)) and isinstance(post_wr, (int, float)) and float(post_wr) < float(base_wr) - 0.10:
                worse = True
            if (
                isinstance(base_brier, (int, float))
                and isinstance(post_brier, (int, float))
                and float(post_brier) > float(base_brier) + 0.05
            ):
                worse = True

            if worse:
                ov = _load_override_obj(repo_root)
                ov["applied_ts"] = int(now)
                champion_params = champion.get("params") if isinstance(champion.get("params"), dict) else {}
                ov["params"] = dict(champion_params)
                ov["meta"] = {
                    "action": "rollback",
                    "rolled_back_from": dict(challenger.get("params") if isinstance(challenger.get("params"), dict) else {}),
                    "baseline": baseline,
                    "post_metrics": post_metrics,
                }
                _save_override_obj(repo_root, ov)
                state["status"] = "rolled_back"
                state["current_params"] = dict(champion_params)
                state["prev_params"] = {}
                state["last_apply_ts"] = 0
                state["baseline"] = dict(champion.get("baseline") if isinstance(champion.get("baseline"), dict) else {})
                challenger["status"] = "rejected"
                challenger["eval_metrics"] = dict(post_metrics)
                challenger["completed_ts"] = int(now)
                _save_tune_state(repo_root, state)
                apply_overrides_to_environ(dict(champion_params))
                return _status_payload(state, settled_total=settled_n, eval_progress={"have": eval_have, "target": eval_settled})

            # Promote challenger to champion.
            challenger_params = challenger.get("params") if isinstance(challenger.get("params"), dict) else {}
            champion["params"] = dict(challenger_params)
            champion["baseline"] = dict(post_metrics)
            champion["applied_ts"] = int(last_apply or now)
            champion["status"] = "active"
            challenger["status"] = "promoted"
            challenger["eval_metrics"] = dict(post_metrics)
            challenger["completed_ts"] = int(now)
            state["status"] = "stable"
            state["post_metrics"] = post_metrics
            state["current_params"] = dict(champion.get("params") if isinstance(champion.get("params"), dict) else {})
            state["prev_params"] = {}
            state["baseline"] = dict(champion.get("baseline") if isinstance(champion.get("baseline"), dict) else {})
            state["last_apply_ts"] = 0

            ov = _load_override_obj(repo_root)
            ov["applied_ts"] = int(now)
            ov["params"] = dict(champion.get("params") if isinstance(champion.get("params"), dict) else {})
            ov["meta"] = {"action": "promote", "post_metrics": post_metrics}
            _save_override_obj(repo_root, ov)
            _save_tune_state(repo_root, state)
            apply_overrides_to_environ(dict(champion.get("params") if isinstance(champion.get("params"), dict) else {}))
            return _status_payload(state, settled_total=settled_n, eval_progress={"have": eval_have, "target": eval_settled})

        state["status"] = "evaluating"
        state["settled_total"] = settled_n
        _save_tune_state(repo_root, state)
        return _status_payload(state, settled_total=settled_n, eval_progress={"have": eval_have, "target": eval_settled})

    # Apply check: at most once per 24h.
    if settled_n < min_settled:
        state["status"] = "waiting_sample"
        state["settled_total"] = settled_n
        _save_tune_state(repo_root, state)
        return _status_payload(state, settled_total=settled_n)

    if int(state.get("last_apply_ts") or 0) and (now - int(state.get("last_apply_ts") or 0)) < 24 * 3600:
        state["status"] = "cooldown"
        _save_tune_state(repo_root, state)
        return _status_payload(state, settled_total=settled_n)

    base_orders = settled_all[-min_settled:]
    base_metrics = _metrics_for_orders(base_orders)
    cur = _bounded(_current_params_from_env())
    recs = recommend_params(baseline=base_metrics, current=cur)
    if not recs:
        state["status"] = "no_change"
        state["settled_total"] = settled_n
        champion["params"] = dict(cur)
        champion["baseline"] = dict(base_metrics)
        champion["status"] = "active"
        state["baseline"] = dict(base_metrics)
        state["current_params"] = dict(cur)
        _save_tune_state(repo_root, state)
        return _status_payload(state, settled_total=settled_n)

    ov = _load_override_obj(repo_root)
    prev = dict(cur)
    newp = dict(cur)
    for r in recs:
        e = r.get("env")
        v = r.get("value")
        if isinstance(e, str) and isinstance(v, str) and e.startswith("KALSHI_ARB_"):
            newp[e] = v
    newp = _bounded(newp)

    ov["applied_ts"] = int(now)
    ov["params"] = dict(newp)
    ov["meta"] = {"action": "apply", "recs": recs, "baseline": base_metrics}
    _save_override_obj(repo_root, ov)

    state["status"] = "applied"
    state["last_apply_ts"] = int(now)
    state["prev_params"] = dict(prev)
    state["current_params"] = dict(newp)
    state["baseline"] = dict(base_metrics)
    champion["name"] = "champion"
    champion["params"] = dict(prev)
    champion["baseline"] = dict(base_metrics)
    champion["status"] = "active"
    challenger["name"] = "challenger"
    challenger["status"] = "evaluating"
    challenger["params"] = dict(newp)
    challenger["baseline"] = dict(base_metrics)
    challenger["eval_metrics"] = {}
    challenger["applied_ts"] = int(now)
    challenger["completed_ts"] = 0
    _save_tune_state(repo_root, state)

    apply_overrides_to_environ(newp)
    return _status_payload(state, settled_total=settled_n, recs=recs, eval_progress={"have": 0, "target": eval_settled})
