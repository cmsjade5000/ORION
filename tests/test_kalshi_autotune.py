import json
import os


def _write_ledger(repo_root: str, orders: dict) -> None:
    p = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "closed_loop_ledger.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    obj = {"version": 1, "orders": orders, "unmatched_settlements": [], "settlement_hashes": []}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


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
