def test_latest_issue_trade_stderr_head():
    import scripts.kalshi_digest as dig

    run_objs = [
        {"ts_unix": 1, "balance_rc": 0, "trade_rc": 0, "post_rc": 0, "trade": {"mode": "trade"}},
        {
            "ts_unix": 2,
            "balance_rc": 0,
            "trade_rc": 1,
            "post_rc": 0,
            "trade": {"raw_stderr": "Traceback\\nBoom happened\\nMore"},
        },
    ]
    iss = dig._latest_issue(run_objs)
    assert iss.get("kind") == "trade"
    assert "Boom happened" in str(iss.get("detail") or "")


def test_latest_issue_balance_stderr_head():
    import scripts.kalshi_digest as dig

    run_objs = [
        {
            "ts_unix": 3,
            "balance_rc": 2,
            "trade_rc": 0,
            "post_rc": 0,
            "balance": {"raw_stderr": "HTTP Error 401: Unauthorized"},
            "trade": {"mode": "trade"},
        }
    ]
    iss = dig._latest_issue(run_objs)
    assert iss.get("kind") == "balance"
    assert "Unauthorized" in str(iss.get("detail") or "")

