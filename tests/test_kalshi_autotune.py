import json
import os
import time


def _write_ledger(repo_root: str, orders: dict) -> None:
    p = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "closed_loop_ledger.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    obj = {"version": 1, "orders": orders, "unmatched_settlements": [], "settlement_hashes": []}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def _write_sweep(repo_root: str, entries: list[dict]) -> None:
    p = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "sweep_stats.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"entries": entries, "updated_ts_unix": int(time.time()), "window_s": 24 * 3600}, f)


def test_autotune_applies_after_min_settled(tmp_path, monkeypatch):
    repo_root = str(tmp_path)

    # Create 20 settled orders with negative pnl to trigger conservative recs.
    orders = {}
    for i in range(20):
        oid = f"o{i}"
        orders[oid] = {
            "ts_unix": 1700000000 + i,
            "side": "yes",
            "p_yes": 0.6,
            "settlement": {
                "ts_seen": 1700001000 + i,
                "parsed": {"outcome_yes": False, "cash_delta_usd": -0.05},
                "raw": {},
                "settled_count": 1,
            },
        }
    _write_ledger(repo_root, orders)

    from scripts.arb.kalshi_autotune import maybe_autotune

    monkeypatch.setenv("KALSHI_ARB_TUNE_ENABLED", "1")
    monkeypatch.setenv("KALSHI_ARB_TUNE_MIN_SETTLED", "20")
    monkeypatch.setenv("KALSHI_ARB_TUNE_EVAL_SETTLED", "10")
    monkeypatch.setenv("KALSHI_ARB_MIN_EDGE_BPS", "100")
    monkeypatch.setenv("KALSHI_ARB_UNCERTAINTY_BPS", "40")
    monkeypatch.setenv("KALSHI_ARB_PERSISTENCE_CYCLES", "2")

    st = maybe_autotune(repo_root)
    assert st.get("enabled") is True
    assert st.get("status") in ("applied", "no_change")
    assert st.get("active_variant") in ("champion", "challenger")
    assert isinstance(st.get("champion"), dict)
    assert isinstance(st.get("challenger"), dict)

    # If applied, override file should exist and contain bounded params.
    ovp = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "params_override.json")
    if st.get("status") == "applied":
        assert os.path.exists(ovp)
        ov = json.load(open(ovp, "r", encoding="utf-8"))
        params = ov.get("params") or {}
        assert isinstance(params, dict)
        # Should never set nonsensical values outside bounds.
        assert 80 <= int(float(params.get("KALSHI_ARB_MIN_EDGE_BPS", 120))) <= 250
        assert 20 <= int(float(params.get("KALSHI_ARB_UNCERTAINTY_BPS", 50))) <= 140
        assert st.get("active_variant") == "challenger"


def test_autotune_sweep_can_loosen_when_zero_opportunities(tmp_path, monkeypatch):
    repo_root = str(tmp_path)
    _write_ledger(repo_root, {})

    now = int(time.time())
    entries = []
    for i in range(30):
        entries.append(
            {
                "ts_unix": now - (30 - i) * 60,
                "candidates_recommended": 0,
                "placed_live": 0,
                "blockers_top": ["liquidity_below_min"],
            }
        )
    _write_sweep(repo_root, entries)

    from scripts.arb.kalshi_autotune import maybe_autotune

    monkeypatch.setenv("KALSHI_ARB_TUNE_ENABLED", "1")
    monkeypatch.setenv("KALSHI_ARB_TUNE_MIN_SETTLED", "20")
    monkeypatch.setenv("KALSHI_ARB_EXECUTION_MODE", "paper")
    monkeypatch.setenv("KALSHI_ARB_LIVE_ARMED", "0")
    monkeypatch.setenv("KALSHI_ARB_MIN_LIQUIDITY_USD", "20")
    monkeypatch.setenv("KALSHI_ARB_MIN_SECONDS_TO_EXPIRY", "900")
    monkeypatch.setenv("KALSHI_ARB_MIN_EDGE_BPS", "170")
    monkeypatch.setenv("KALSHI_ARB_MIN_NOTIONAL_USD", "0.50")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES", "24")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED", "1")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED", "8")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S", "1")

    st = maybe_autotune(repo_root)
    assert st.get("enabled") is True
    assert st.get("status") == "sweep_applied"
    ovp = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "params_override.json")
    assert os.path.exists(ovp)
    ov = json.load(open(ovp, "r", encoding="utf-8"))
    params = ov.get("params") or {}
    assert int(float(params.get("KALSHI_ARB_MIN_LIQUIDITY_USD", 20))) < 20


def test_autotune_sweep_can_tighten_when_opportunity_flow_too_high(tmp_path, monkeypatch):
    repo_root = str(tmp_path)
    _write_ledger(repo_root, {})

    now = int(time.time())
    entries = []
    for i in range(30):
        entries.append(
            {
                "ts_unix": now - (30 - i) * 60,
                "candidates_recommended": 2,
                "placed_live": 0,
                "blockers_top": [],
            }
        )
    _write_sweep(repo_root, entries)

    from scripts.arb.kalshi_autotune import maybe_autotune

    monkeypatch.setenv("KALSHI_ARB_TUNE_ENABLED", "1")
    monkeypatch.setenv("KALSHI_ARB_TUNE_MIN_SETTLED", "20")
    monkeypatch.setenv("KALSHI_ARB_EXECUTION_MODE", "paper")
    monkeypatch.setenv("KALSHI_ARB_LIVE_ARMED", "0")
    monkeypatch.setenv("KALSHI_ARB_MIN_EDGE_BPS", "170")
    monkeypatch.setenv("KALSHI_ARB_MIN_LIQUIDITY_USD", "13")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_MIN_CYCLES", "24")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED", "1")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED", "8")
    monkeypatch.setenv("KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S", "1")

    st = maybe_autotune(repo_root)
    assert st.get("enabled") is True
    assert st.get("status") == "sweep_applied"
    ovp = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "params_override.json")
    ov = json.load(open(ovp, "r", encoding="utf-8"))
    params = ov.get("params") or {}
    assert int(float(params.get("KALSHI_ARB_MIN_EDGE_BPS", 170))) > 170
