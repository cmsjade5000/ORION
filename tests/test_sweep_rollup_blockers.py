def test_sweep_rollup_counts_blockers_top():
    import scripts.kalshi_digest as dig

    now = 1000
    obj = {
        "window_s": 24 * 3600,
        "entries": [
            {"ts_unix": now - 10, "blockers_top": ["a", "b", "a"], "signals_computed": 1, "candidates_recommended": 0},
            {"ts_unix": now - 20, "blockers_top": ["b", "c"], "signals_computed": 1, "candidates_recommended": 0},
        ],
    }
    out = dig._sweep_rollup_24h(obj, now_unix=now)
    assert isinstance(out, dict)
    tb = out.get("top_blockers")
    assert isinstance(tb, list)
    counts = {it.get("reason"): it.get("count") for it in tb if isinstance(it, dict)}
    assert counts.get("a") == 2
    assert counts.get("b") == 2
    assert counts.get("c") == 1

