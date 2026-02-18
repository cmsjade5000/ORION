def test_extract_stats_counts_scan_failed():
    import scripts.kalshi_digest as dig

    runs = [
        {"ts_unix": 1, "balance_rc": 0, "trade_rc": 0, "post_rc": 0, "trade": {"mode": "trade"}},
        {"ts_unix": 2, "balance_rc": 0, "trade_rc": 2, "post_rc": 0, "trade": {"mode": "trade", "status": "refused", "reason": "scan_failed"}},
        {"ts_unix": 3, "balance_rc": 0, "trade_rc": 2, "post_rc": 0, "trade": {"mode": "trade", "status": "refused", "reason": "scan_failed"}},
    ]
    st = dig._extract_stats(runs)
    assert st.cycles == 3
    assert st.scan_failed == 2

