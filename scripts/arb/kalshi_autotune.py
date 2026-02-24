from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .kalshi_ledger import load_ledger  # type: ignore


OVERRIDE_PATH_REL = os.path.join("tmp", "kalshi_ref_arb", "params_override.json")
TUNE_STATE_PATH_REL = os.path.join("tmp", "kalshi_ref_arb", "tune_state.json")
SWEEP_STATS_PATH_REL = os.path.join("tmp", "kalshi_ref_arb", "sweep_stats.json")


@dataclass(frozen=True)
class TuneBounds:
    min_edge_bps: Tuple[int, int] = (80, 250)
    uncertainty_bps: Tuple[int, int] = (20, 140)
    persistence_cycles: Tuple[int, int] = (1, 3)
    min_liquidity_usd: Tuple[int, int] = (8, 300)
    min_seconds_to_expiry: Tuple[int, int] = (300, 3600)
    min_notional_usd: Tuple[float, float] = (0.10, 2.00)
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
        "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY",
        "KALSHI_ARB_MIN_NOTIONAL_USD",
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
    out.setdefault("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY", "900")
    out.setdefault("KALSHI_ARB_MIN_NOTIONAL_USD", "0.20")
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
    out["KALSHI_ARB_MIN_SECONDS_TO_EXPIRY"] = str(
        _clamp_int(int(float(out.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY") or 900)), *BOUNDS.min_seconds_to_expiry)
    )
    out["KALSHI_ARB_MIN_NOTIONAL_USD"] = (
        f"{_clamp_float(float(out.get('KALSHI_ARB_MIN_NOTIONAL_USD') or 0.20), *BOUNDS.min_notional_usd):.2f}"
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


def _load_sweep_rollup(repo_root: str, *, window_s: int) -> Dict[str, Any]:
    p = _repo_path(repo_root, SWEEP_STATS_PATH_REL)
    try:
        obj = _load_json(p, default={})
    except Exception:
        return {}
    entries = obj.get("entries")
    if not isinstance(entries, list) or not entries:
        return {}
    now = int(time.time())
    start = int(now - max(60, int(window_s)))
    cycles = 0
    recommended = 0
    placed_live = 0
    placed_paper = 0
    placed_total = 0
    blocker_counts: Dict[str, int] = {}
    for it in entries:
        if not isinstance(it, dict):
            continue
        try:
            ts = int(it.get("ts_unix") or 0)
        except Exception:
            ts = 0
        if ts < start:
            continue
        cycles += 1
        try:
            recommended += int(it.get("candidates_recommended") or 0)
        except Exception:
            pass
        try:
            placed_live += int(it.get("placed_live") or 0)
        except Exception:
            pass
        try:
            placed_paper += int(it.get("placed_paper") or 0)
        except Exception:
            pass
        try:
            placed_total += int(it.get("placed_total") or 0)
        except Exception:
            pass
        if "placed_total" not in it:
            # Backward compatibility with older sweep entries.
            try:
                placed_total += int(it.get("placed_live") or 0) + int(it.get("placed_paper") or 0)
            except Exception:
                pass
        bt = it.get("blockers_top")
        if isinstance(bt, list):
            for r in bt:
                if not isinstance(r, str) or not r:
                    continue
                blocker_counts[r] = blocker_counts.get(r, 0) + 1
    if cycles <= 0:
        return {}
    return {
        "window_s": int(window_s),
        "cycles": int(cycles),
        "recommended": int(recommended),
        "placed_live": int(placed_live),
        "placed_paper": int(placed_paper),
        "placed_total": int(placed_total),
        "blocker_counts": blocker_counts,
    }


def _load_sweep_group_rollup(
    repo_root: str,
    *,
    round_cycles: int,
    groups_lookback: int,
    window_s_fallback: int,
) -> Dict[str, Any]:
    """Grouped-round sweep aggregation for round-by-round gate tuning.

    - Uses the latest N entries where N = round_cycles * groups_lookback.
    - Falls back to a time window when too few entries are present.
    - Exposes round boundary metadata so we can tune at most once per round.
    """
    p = _repo_path(repo_root, SWEEP_STATS_PATH_REL)
    try:
        obj = _load_json(p, default={})
    except Exception:
        return {}

    entries = obj.get("entries")
    if not isinstance(entries, list) or not entries:
        return {}

    all_entries: List[Dict[str, Any]] = []
    for it in entries:
        if not isinstance(it, dict):
            continue
        try:
            ts = int(it.get("ts_unix") or 0)
        except Exception:
            ts = 0
        if ts <= 0:
            continue
        row = dict(it)
        row["ts_unix"] = ts
        all_entries.append(row)

    if not all_entries:
        return {}

    all_entries.sort(key=lambda x: int(x.get("ts_unix") or 0))
    tail_n = max(1, int(round_cycles) * max(1, int(groups_lookback)))
    recent = all_entries[-tail_n:]

    # Fallback to time-window slice when an early run has very few entries.
    if len(recent) < max(4, int(round_cycles)):
        now = int(time.time())
        start = int(now - max(60, int(window_s_fallback)))
        recent = [x for x in all_entries if int(x.get("ts_unix") or 0) >= start]
        if not recent:
            recent = all_entries[-max(1, int(round_cycles)) :]

    cycles = 0
    recommended = 0
    placed_live = 0
    placed_paper = 0
    placed_total = 0
    best_eff_edge_bps_max: float | None = None
    blocker_counts: Dict[str, int] = {}
    for it in recent:
        cycles += 1
        try:
            recommended += int(it.get("candidates_recommended") or 0)
        except Exception:
            pass
        try:
            placed_live += int(it.get("placed_live") or 0)
        except Exception:
            pass
        try:
            placed_paper += int(it.get("placed_paper") or 0)
        except Exception:
            pass
        try:
            placed_total += int(it.get("placed_total") or 0)
        except Exception:
            pass
        if "placed_total" not in it:
            try:
                placed_total += int(it.get("placed_live") or 0) + int(it.get("placed_paper") or 0)
            except Exception:
                pass
        try:
            be = float(it.get("best_effective_edge_bps")) if it.get("best_effective_edge_bps") is not None else None
        except Exception:
            be = None
        if isinstance(be, float):
            if best_eff_edge_bps_max is None or be > best_eff_edge_bps_max:
                best_eff_edge_bps_max = float(be)
        bt = it.get("blockers_top")
        if isinstance(bt, list):
            for r in bt:
                if not isinstance(r, str) or not r:
                    continue
                blocker_counts[r] = blocker_counts.get(r, 0) + 1

    rc = max(1, int(round_cycles))
    entries_total = len(all_entries)
    completed_rounds = int(entries_total // rc)
    last_completed_round_id = int(completed_rounds - 1) if completed_rounds > 0 else -1
    current_round = all_entries[-rc:] if len(all_entries) >= rc else all_entries
    round_recommended = 0
    round_placed_live = 0
    round_placed_paper = 0
    round_placed_total = 0
    for it in current_round:
        try:
            round_recommended += int(it.get("candidates_recommended") or 0)
        except Exception:
            pass
        try:
            round_placed_live += int(it.get("placed_live") or 0)
        except Exception:
            pass
        try:
            round_placed_paper += int(it.get("placed_paper") or 0)
        except Exception:
            pass
        try:
            round_placed_total += int(it.get("placed_total") or 0)
        except Exception:
            pass
        if "placed_total" not in it:
            try:
                round_placed_total += int(it.get("placed_live") or 0) + int(it.get("placed_paper") or 0)
            except Exception:
                pass

    out = {
        "window_s": int(window_s_fallback),
        "cycles": int(cycles),
        "recommended": int(recommended),
        "placed_live": int(placed_live),
        "placed_paper": int(placed_paper),
        "placed_total": int(placed_total),
        "blocker_counts": blocker_counts,
        "entries_total": int(entries_total),
        "completed_rounds": int(completed_rounds),
        "last_completed_round_id": int(last_completed_round_id),
        "round_cycles": int(rc),
        "groups_lookback": int(max(1, int(groups_lookback))),
        "round_recommended": int(round_recommended),
        "round_placed_live": int(round_placed_live),
        "round_placed_paper": int(round_placed_paper),
        "round_placed_total": int(round_placed_total),
    }
    if best_eff_edge_bps_max is not None:
        out["best_eff_edge_bps_max"] = float(best_eff_edge_bps_max)
    return out


def _recommend_params_from_sweep(
    *,
    current: Dict[str, str],
    sweep: Dict[str, Any],
    target_min_recommended: int,
    target_max_recommended: int,
    target_min_placed: int,
    target_max_placed: int,
    max_changes: int = 2,
) -> List[Dict[str, Any]]:
    cycles = int(sweep.get("cycles") or 0)
    if cycles <= 0:
        return []
    rec_n = int(sweep.get("recommended") or 0)
    placed_live = int(sweep.get("placed_live") or 0)
    placed_total = int(sweep.get("placed_total") or 0)
    round_recommended = int(sweep.get("round_recommended") or 0)
    round_placed_live = int(sweep.get("round_placed_live") or 0)
    round_placed_total = int(sweep.get("round_placed_total") or 0)
    bc = sweep.get("blocker_counts") if isinstance(sweep.get("blocker_counts"), dict) else {}

    def _share(reason: str) -> float:
        try:
            return float(int(bc.get(reason) or 0)) / float(max(1, cycles))
        except Exception:
            return 0.0

    cur_edge = int(float(current.get("KALSHI_ARB_MIN_EDGE_BPS") or 120))
    cur_liq = int(float(current.get("KALSHI_ARB_MIN_LIQUIDITY_USD") or 200))
    cur_tte = int(float(current.get("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY") or 900))
    try:
        cur_notional = float(current.get("KALSHI_ARB_MIN_NOTIONAL_USD") or 0.20)
    except Exception:
        cur_notional = 0.20

    scored: List[Tuple[float, Dict[str, Any]]] = []
    # If live placements happened in the round, avoid paper auto-tuning decisions.
    if round_placed_live > 0:
        return []
    if (
        int(target_min_recommended) <= round_recommended <= int(target_max_recommended)
        and int(target_min_placed) <= round_placed_total <= int(target_max_placed)
    ):
        return []

    high_flow = (
        rec_n > int(target_max_recommended)
        or placed_total > int(target_max_placed)
        or round_recommended > int(target_max_recommended)
        or round_placed_total > int(target_max_placed)
    )

    if high_flow:
        # Too many opportunities: score tighten-options by overflow severity.
        overflow_rec = max(
            float(max(0, rec_n - int(target_max_recommended))) / float(max(1, int(target_max_recommended))),
            float(max(0, round_recommended - int(target_max_recommended))) / float(max(1, int(target_max_recommended))),
        )
        overflow_placed = max(
            float(max(0, placed_total - int(target_max_placed))) / float(max(1, int(target_max_placed))),
            float(max(0, round_placed_total - int(target_max_placed))) / float(max(1, int(target_max_placed))),
        )
        overflow = max(overflow_rec, overflow_placed)
        nxt = _clamp_int(cur_edge + 5, *BOUNDS.min_edge_bps)
        if nxt != cur_edge:
            scored.append(
                (
                    0.20 + overflow,
                    {
                        "env": "KALSHI_ARB_MIN_EDGE_BPS",
                        "value": str(nxt),
                        "why": "Opportunity flow is high; slightly tighten min-edge to preserve quality.",
                    },
                )
            )
        if rec_n > int(target_max_recommended) * 2:
            nxt_liq = _clamp_int(cur_liq + 2, *BOUNDS.min_liquidity_usd)
            if nxt_liq != cur_liq:
                scored.append(
                    (
                        0.12 + overflow,
                        {
                            "env": "KALSHI_ARB_MIN_LIQUIDITY_USD",
                            "value": str(nxt_liq),
                            "why": "Opportunity flow far above target; modestly raise liquidity floor.",
                        },
                    )
                )
    elif rec_n < int(target_min_recommended) and round_recommended < int(target_min_recommended):
        # Not enough opportunities: score loosen-options by blocker dominance.
        scarcity = max(
            float(max(0, int(target_min_recommended) - int(round_recommended))) / float(max(1, int(target_min_recommended))),
            float(max(0, int(target_min_placed) - int(round_placed_total))) / float(max(1, int(target_min_placed))),
        )
        liq_share = _share("liquidity_below_min")
        if liq_share >= 0.05:
            nxt = _clamp_int(cur_liq - 2, *BOUNDS.min_liquidity_usd)
            if nxt != cur_liq:
                scored.append(
                    (
                        0.10 + liq_share + 0.10 * scarcity,
                        {
                            "env": "KALSHI_ARB_MIN_LIQUIDITY_USD",
                            "value": str(nxt),
                            "why": "Low opportunity flow with frequent liquidity blocker; slightly lower liquidity floor.",
                        },
                    )
                )

        tte_share = _share("too_close_to_expiry")
        if tte_share >= 0.05:
            nxt = _clamp_int(cur_tte - 120, *BOUNDS.min_seconds_to_expiry)
            if nxt != cur_tte:
                scored.append(
                    (
                        0.08 + tte_share + 0.08 * scarcity,
                        {
                            "env": "KALSHI_ARB_MIN_SECONDS_TO_EXPIRY",
                            "value": str(nxt),
                            "why": "Low opportunity flow with frequent expiry blocker; slightly allow closer expiries.",
                        },
                    )
                )

        no_notional = max(_share("yes_notional_below_min"), _share("no_notional_below_min"))
        if no_notional >= 0.05:
            nxt = _clamp_float(cur_notional - 0.05, *BOUNDS.min_notional_usd)
            if abs(nxt - cur_notional) > 1e-9:
                scored.append(
                    (
                        0.06 + no_notional + 0.06 * scarcity,
                        {
                            "env": "KALSHI_ARB_MIN_NOTIONAL_USD",
                            "value": f"{nxt:.2f}",
                            "why": "Low opportunity flow with notional blocker; slightly lower probe notional floor.",
                        },
                    )
                )

        # Generic edge loosen fallback if blocker-specific options are weak.
        edge_miss = max(_share("yes_edge_below_min"), _share("no_edge_below_min"))
        nxt_edge = _clamp_int(cur_edge - 5, *BOUNDS.min_edge_bps)
        if nxt_edge != cur_edge:
            scored.append(
                (
                    0.04 + max(0.02, edge_miss) + 0.05 * scarcity,
                    {
                        "env": "KALSHI_ARB_MIN_EDGE_BPS",
                        "value": str(nxt_edge),
                        "why": "Low opportunity flow; slightly lower min-edge to admit near-threshold setups.",
                    },
                )
            )
    out: List[Dict[str, Any]] = [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)]

    seen: set[str] = set()
    dedup: List[Dict[str, Any]] = []
    for r in out:
        e = r.get("env")
        if not isinstance(e, str) or not e.startswith("KALSHI_ARB_") or e in seen:
            continue
        seen.add(e)
        dedup.append(r)
        if len(dedup) >= int(max(1, int(max_changes))):
            break
    return dedup


def _maybe_apply_sweep_tune(
    *,
    repo_root: str,
    state: Dict[str, Any],
    champion: Dict[str, Any],
    now: int,
    current: Dict[str, str],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Apply paper-only sweep-based threshold nudges.

    Returns (action, recs) where action is one of:
    - disabled
    - insufficient_cycles
    - cooldown
    - no_change
    - applied
    """
    sweep_enabled = str(os.environ.get("KALSHI_ARB_TUNE_SWEEP_ENABLED", "1") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    exec_mode = str(os.environ.get("KALSHI_ARB_EXECUTION_MODE", "paper") or "paper").strip().lower()
    live_armed = str(os.environ.get("KALSHI_ARB_LIVE_ARMED", "0") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if (not sweep_enabled) or exec_mode != "paper" or live_armed:
        return "disabled", []

    window_s = max(900, _get_env_int("KALSHI_ARB_TUNE_SWEEP_WINDOW_S", 6 * 3600))
    min_cycles = max(12, _get_env_int("KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES", 24))
    cooldown_s = max(900, _get_env_int("KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S", 2 * 3600))
    target_min = max(0, _get_env_int("KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED", 1))
    target_max = max(target_min + 1, _get_env_int("KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED", 8))
    target_min_placed = max(0, _get_env_int("KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_PLACED", 1))
    target_max_placed = max(target_min_placed + 1, _get_env_int("KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_PLACED", 6))
    round_cycles = max(6, _get_env_int("KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES", 12))
    groups_lookback = max(1, _get_env_int("KALSHI_ARB_TUNE_SWEEP_GROUPS_LOOKBACK", 3))
    min_rounds = max(1, _get_env_int("KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS", 2))
    max_changes = max(1, _get_env_int("KALSHI_ARB_TUNE_SWEEP_MAX_CHANGES_PER_ROUND", 2))

    sweep = _load_sweep_group_rollup(
        repo_root,
        round_cycles=round_cycles,
        groups_lookback=groups_lookback,
        window_s_fallback=window_s,
    )
    if not sweep:
        # Compatibility fallback.
        sweep = _load_sweep_rollup(repo_root, window_s=window_s)
        if isinstance(sweep, dict) and sweep:
            sweep.setdefault("entries_total", int(sweep.get("cycles") or 0))
            sweep.setdefault("completed_rounds", 0)
            sweep.setdefault("last_completed_round_id", -1)
            sweep.setdefault("round_cycles", int(round_cycles))
            sweep.setdefault("groups_lookback", int(groups_lookback))
            sweep.setdefault("round_recommended", int(sweep.get("recommended") or 0))
            sweep.setdefault("round_placed_live", int(sweep.get("placed_live") or 0))
            sweep.setdefault("placed_paper", int(sweep.get("placed_paper") or 0))
            sweep.setdefault("placed_total", int(sweep.get("placed_total") or sweep.get("placed_live") or 0))
            sweep.setdefault("round_placed_paper", int(sweep.get("round_placed_paper") or 0))
            sweep.setdefault("round_placed_total", int(sweep.get("round_placed_total") or sweep.get("round_placed_live") or 0))

    stn = state.get("sweep_tune") if isinstance(state.get("sweep_tune"), dict) else {}
    if not isinstance(stn, dict):
        stn = {}
    stn["window_s"] = int(window_s)
    stn["cycles"] = int(sweep.get("cycles") or 0) if isinstance(sweep, dict) else 0
    stn["recommended"] = int(sweep.get("recommended") or 0) if isinstance(sweep, dict) else 0
    stn["placed_live"] = int(sweep.get("placed_live") or 0) if isinstance(sweep, dict) else 0
    stn["placed_paper"] = int(sweep.get("placed_paper") or 0) if isinstance(sweep, dict) else 0
    stn["placed_total"] = int(sweep.get("placed_total") or 0) if isinstance(sweep, dict) else 0
    stn["entries_total"] = int(sweep.get("entries_total") or 0) if isinstance(sweep, dict) else 0
    stn["completed_rounds"] = int(sweep.get("completed_rounds") or 0) if isinstance(sweep, dict) else 0
    stn["last_completed_round_id"] = int(sweep.get("last_completed_round_id") or -1) if isinstance(sweep, dict) else -1
    stn["round_cycles"] = int(sweep.get("round_cycles") or round_cycles) if isinstance(sweep, dict) else int(round_cycles)
    stn["groups_lookback"] = int(sweep.get("groups_lookback") or groups_lookback) if isinstance(sweep, dict) else int(groups_lookback)
    stn["round_recommended"] = int(sweep.get("round_recommended") or 0) if isinstance(sweep, dict) else 0
    stn["round_placed_live"] = int(sweep.get("round_placed_live") or 0) if isinstance(sweep, dict) else 0
    stn["round_placed_paper"] = int(sweep.get("round_placed_paper") or 0) if isinstance(sweep, dict) else 0
    stn["round_placed_total"] = int(sweep.get("round_placed_total") or 0) if isinstance(sweep, dict) else 0
    stn["target_min_placed"] = int(target_min_placed)
    stn["target_max_placed"] = int(target_max_placed)
    stn["target_min_recommended"] = int(target_min)
    stn["target_max_recommended"] = int(target_max)
    state["sweep_tune"] = stn

    # Always compute top candidate moves for operator visibility, even when gated.
    candidate_recs = _recommend_params_from_sweep(
        current=current,
        sweep=sweep,
        target_min_recommended=int(target_min),
        target_max_recommended=int(target_max),
        target_min_placed=int(target_min_placed),
        target_max_placed=int(target_max_placed),
        max_changes=2,
    )
    stn["candidate_recs"] = [r for r in candidate_recs if isinstance(r, dict)][:2]
    stn["next_eligible_ts"] = 0
    stn["next_eligible_reason"] = ""

    if int(stn.get("cycles") or 0) < int(min_cycles):
        stn["status"] = "insufficient_cycles"
        stn["next_eligible_reason"] = "need_more_cycles"
        state["sweep_tune"] = stn
        return "insufficient_cycles", []
    if int(stn.get("completed_rounds") or 0) < int(min_rounds):
        stn["status"] = "insufficient_rounds"
        stn["next_eligible_reason"] = "need_more_rounds"
        state["sweep_tune"] = stn
        return "insufficient_rounds", []

    last_sw = int(stn.get("last_apply_ts") or 0)
    if last_sw and (int(now) - last_sw) < cooldown_s:
        stn["status"] = "cooldown"
        stn["next_eligible_ts"] = int(last_sw + cooldown_s)
        stn["next_eligible_reason"] = "cooldown"
        state["sweep_tune"] = stn
        return "cooldown", []
    last_round_applied = int(stn.get("last_round_id_applied") or -1)
    current_round = int(stn.get("last_completed_round_id") or -1)
    if current_round >= 0 and current_round <= last_round_applied:
        stn["status"] = "round_wait"
        stn["next_eligible_reason"] = "await_next_round"
        state["sweep_tune"] = stn
        return "round_wait", []

    recs = _recommend_params_from_sweep(
        current=current,
        sweep=sweep,
        target_min_recommended=int(target_min),
        target_max_recommended=int(target_max),
        target_min_placed=int(target_min_placed),
        target_max_placed=int(target_max_placed),
        max_changes=int(max_changes),
    )
    if not recs:
        stn["status"] = "target_met_or_no_change"
        stn["next_eligible_reason"] = "targets_met_or_no_change"
        state["sweep_tune"] = stn
        return "no_change", []

    newp = dict(current)
    for r in recs:
        e = r.get("env")
        v = r.get("value")
        if isinstance(e, str) and isinstance(v, str) and e.startswith("KALSHI_ARB_"):
            newp[e] = v
    newp = _bounded(newp)
    if newp == current:
        stn["status"] = "no_change"
        state["sweep_tune"] = stn
        return "no_change", []

    ov = _load_override_obj(repo_root)
    ov["applied_ts"] = int(now)
    ov["params"] = dict(newp)
    ov["meta"] = {
        "action": "sweep_apply",
        "recs": recs,
        "sweep": {
            "cycles": int(sweep.get("cycles") or 0),
            "recommended": int(sweep.get("recommended") or 0),
            "placed_live": int(sweep.get("placed_live") or 0),
        },
    }
    _save_override_obj(repo_root, ov)
    apply_overrides_to_environ(newp)
    state["current_params"] = dict(newp)
    champion["params"] = dict(newp)
    champion["status"] = "active"
    stn["last_apply_ts"] = int(now)
    stn["last_round_id_applied"] = int(current_round)
    stn["next_eligible_ts"] = int(now + cooldown_s)
    stn["next_eligible_reason"] = "cooldown_after_apply"
    stn["status"] = "applied"
    state["sweep_tune"] = stn
    return "applied", recs


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
            "sweep_tune": {
                "last_apply_ts": 0,
                "last_round_id_applied": -1,
                "status": "idle",
                "window_s": 0,
                "cycles": 0,
                "recommended": 0,
                "placed_live": 0,
                "placed_paper": 0,
                "placed_total": 0,
                "entries_total": 0,
                "completed_rounds": 0,
                "last_completed_round_id": -1,
                "round_cycles": 0,
                "groups_lookback": 0,
                "round_recommended": 0,
                "round_placed_live": 0,
                "round_placed_paper": 0,
                "round_placed_total": 0,
                "target_min_placed": 0,
                "target_max_placed": 0,
                "target_min_recommended": 0,
                "target_max_recommended": 0,
                "candidate_recs": [],
                "next_eligible_ts": 0,
                "next_eligible_reason": "",
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
    if not isinstance(state.get("sweep_tune"), dict):
        state["sweep_tune"] = {
            "last_apply_ts": 0,
            "last_round_id_applied": -1,
            "status": "idle",
            "window_s": 0,
            "cycles": 0,
            "recommended": 0,
            "placed_live": 0,
            "placed_paper": 0,
            "placed_total": 0,
            "entries_total": 0,
            "completed_rounds": 0,
            "last_completed_round_id": -1,
            "round_cycles": 0,
            "groups_lookback": 0,
            "round_recommended": 0,
            "round_placed_live": 0,
            "round_placed_paper": 0,
            "round_placed_total": 0,
            "target_min_placed": 0,
            "target_max_placed": 0,
            "target_min_recommended": 0,
            "target_max_recommended": 0,
            "candidate_recs": [],
            "next_eligible_ts": 0,
            "next_eligible_reason": "",
        }
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
    st = state.get("sweep_tune") if isinstance(state.get("sweep_tune"), dict) else {}
    if isinstance(st, dict) and st:
        out["sweep_tune"] = {
            "last_apply_ts": int(st.get("last_apply_ts") or 0),
            "last_round_id_applied": int(st.get("last_round_id_applied") or -1),
            "status": str(st.get("status") or ""),
            "window_s": int(st.get("window_s") or 0),
            "cycles": int(st.get("cycles") or 0),
            "recommended": int(st.get("recommended") or 0),
            "placed_live": int(st.get("placed_live") or 0),
            "placed_paper": int(st.get("placed_paper") or 0),
            "placed_total": int(st.get("placed_total") or 0),
            "entries_total": int(st.get("entries_total") or 0),
            "completed_rounds": int(st.get("completed_rounds") or 0),
            "last_completed_round_id": int(st.get("last_completed_round_id") or -1),
            "round_cycles": int(st.get("round_cycles") or 0),
            "groups_lookback": int(st.get("groups_lookback") or 0),
            "round_recommended": int(st.get("round_recommended") or 0),
            "round_placed_live": int(st.get("round_placed_live") or 0),
            "round_placed_paper": int(st.get("round_placed_paper") or 0),
            "round_placed_total": int(st.get("round_placed_total") or 0),
            "target_min_placed": int(st.get("target_min_placed") or 0),
            "target_max_placed": int(st.get("target_max_placed") or 0),
            "target_min_recommended": int(st.get("target_min_recommended") or 0),
            "target_max_recommended": int(st.get("target_max_recommended") or 0),
            "candidate_recs": (st.get("candidate_recs") if isinstance(st.get("candidate_recs"), list) else []),
            "next_eligible_ts": int(st.get("next_eligible_ts") or 0),
            "next_eligible_reason": str(st.get("next_eligible_reason") or ""),
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
        state["settled_total"] = settled_n
        cur = _bounded(_current_params_from_env())
        sweep_action, sweep_recs = _maybe_apply_sweep_tune(
            repo_root=repo_root,
            state=state,
            champion=champion,
            now=now,
            current=cur,
        )
        if sweep_action == "applied":
            state["status"] = "sweep_applied"
            _save_tune_state(repo_root, state)
            return _status_payload(state, settled_total=settled_n, recs=sweep_recs)
        if sweep_action == "cooldown":
            state["status"] = "sweep_cooldown"
            _save_tune_state(repo_root, state)
            return _status_payload(state, settled_total=settled_n)
        if sweep_action == "round_wait":
            state["status"] = "sweep_round_wait"
            _save_tune_state(repo_root, state)
            return _status_payload(state, settled_total=settled_n)
        if sweep_action == "insufficient_rounds":
            state["status"] = "sweep_insufficient_rounds"
            _save_tune_state(repo_root, state)
            return _status_payload(state, settled_total=settled_n)

        state["status"] = "waiting_sample"
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
        sweep_action, sweep_recs = _maybe_apply_sweep_tune(
            repo_root=repo_root,
            state=state,
            champion=champion,
            now=now,
            current=cur,
        )
        if sweep_action == "applied":
            state["status"] = "sweep_applied"
            state["settled_total"] = settled_n
            champion["baseline"] = dict(base_metrics)
            state["baseline"] = dict(base_metrics)
            _save_tune_state(repo_root, state)
            return _status_payload(state, settled_total=settled_n, recs=sweep_recs)

        if sweep_action == "cooldown":
            state["status"] = "sweep_cooldown"
        elif sweep_action == "round_wait":
            state["status"] = "sweep_round_wait"
        elif sweep_action == "insufficient_rounds":
            state["status"] = "sweep_insufficient_rounds"
        else:
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
