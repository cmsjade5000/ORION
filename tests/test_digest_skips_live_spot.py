def test_summarize_skips_and_live_spot_counts():
    import scripts.kalshi_digest as dig

    run_objs = [
        {
            "trade": {
                "skipped": [
                    {"reason": "recheck_failed", "detail": "spread_too_wide"},
                    {"reason": "recheck_failed", "detail": "spread_too_wide"},
                    {"reason": "recheck_failed", "detail": "live_spot_required_failed", "ref_spot_live_err": "WS_TIMEOUT"},
                    {"reason": "no_fill", "error": "FOK"},
                ],
                "placed": [
                    {"mode": "live", "ref_spot_live": 50000.0, "ref_spot_live_err": ""},
                    {"mode": "live", "ref_spot_live": None, "ref_spot_live_err": "WS_ERROR"},
                ],
            }
        },
        {"trade": {"skipped": [{"reason": "recheck_failed", "detail": "price_out_of_bounds"}], "placed": []}},
    ]

    out = dig._summarize_skips_and_live_spot(run_objs)
    assert isinstance(out, dict)

    top_skips = out.get("top_skips")
    assert isinstance(top_skips, list)
    # detail should win over reason when present
    reasons = {it.get("reason"): it.get("count") for it in top_skips if isinstance(it, dict)}
    assert reasons.get("spread_too_wide") == 2
    assert reasons.get("live_spot_required_failed") == 1
    assert reasons.get("price_out_of_bounds") == 1
    assert reasons.get("no_fill") == 1

    live = out.get("live_spot")
    assert isinstance(live, dict)
    assert live.get("attempts_with_fields") == 2
    assert live.get("ok_prices") == 1

    top_errors = live.get("top_errors")
    assert isinstance(top_errors, list)
    errors = {it.get("error"): it.get("count") for it in top_errors if isinstance(it, dict)}
    assert errors.get("WS_TIMEOUT") == 1
    assert errors.get("WS_ERROR") == 1
