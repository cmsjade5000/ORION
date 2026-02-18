def test_digest_includes_scan_failed_details_best_effort(tmp_path, monkeypatch):
    # Regression-style: ensure the scan-failed details codepath doesn't crash when fields exist.
    import scripts.kalshi_digest as dig

    run_objs = [
        {
            "ts_unix": 10,
            "balance_rc": 0,
            "trade_rc": 2,
            "post_rc": 0,
            "trade": {"mode": "trade", "status": "refused", "reason": "scan_failed"},
            "cycle_inputs": {
                "scan_summary": {
                    "series": [
                        {"series": "KXBTC", "rc": 124, "rc_reason": "timeout", "stderr_head": "timed out"},
                        {"series": "KXETH", "rc": 1, "rc_reason": "missing_spot_ref", "stderr_head": ""},
                    ]
                }
            },
        }
    ]
    st = dig._extract_stats(run_objs)
    assert st.scan_failed == 1

