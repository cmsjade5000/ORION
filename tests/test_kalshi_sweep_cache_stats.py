import json
import os
import tempfile


def test_list_markets_cached_hits_cache(tmp_path):
    import scripts.kalshi_ref_arb as mod
    from scripts.arb.kalshi import KalshiMarket

    calls = {"n": 0}

    class DummyKC:
        def list_markets(self, *, status=None, series_ticker=None, limit=0):
            calls["n"] += 1
            return [
                KalshiMarket(
                    ticker="T1",
                    series_ticker=str(series_ticker or ""),
                    event_ticker="E1",
                    title="t",
                    subtitle="s",
                    status=str(status or ""),
                    strike_type="greater",
                    expected_expiration_time="2026-01-01T00:00:00Z",
                    yes_bid=0.4,
                    yes_ask=0.5,
                    no_bid=0.5,
                    no_ask=0.6,
                    liquidity_dollars=123.0,
                    floor_strike=100.0,
                    cap_strike=None,
                )
            ]

    kc = DummyKC()
    repo_root = str(tmp_path)

    mk1, hit1 = mod._list_markets_cached(kc, repo_root=repo_root, status="open", series="KXBTC", limit=10, cache_s=999)
    assert hit1 is False
    assert calls["n"] == 1
    assert mk1 and mk1[0].ticker == "T1"

    mk2, hit2 = mod._list_markets_cached(kc, repo_root=repo_root, status="open", series="KXBTC", limit=10, cache_s=999)
    assert hit2 is True
    assert calls["n"] == 1
    assert mk2 and mk2[0].ticker == "T1"

    cache_dir = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "markets_cache")
    assert os.path.isdir(cache_dir)
    assert any(n.endswith(".json") for n in os.listdir(cache_dir))


def test_update_sweep_stats_prunes_old_entries(tmp_path):
    import scripts.kalshi_ref_arb as mod

    repo_root = str(tmp_path)
    path = os.path.join(repo_root, "tmp", "kalshi_ref_arb", "sweep_stats.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated_ts_unix": 1, "window_s": 10, "entries": [{"ts_unix": 1, "series": "KXBTC"}]}, f)

    mod._update_sweep_stats(repo_root, {"ts_unix": 999999999, "series": "KXETH"}, window_s=10, max_entries=10)
    obj = json.load(open(path, "r", encoding="utf-8"))
    assert isinstance(obj.get("entries"), list)
    # Old entry should be pruned (ts_unix=1 far outside window).
    assert obj["entries"] and obj["entries"][-1]["series"] == "KXETH"
    assert all(int(e.get("ts_unix") or 0) != 1 for e in obj["entries"])

