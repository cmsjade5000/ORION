def test_best_bid_ask_from_us_book():
    from scripts.arb.polymarket_us import best_bid_ask_from_us_book

    book = {
        "marketData": {
            "bids": [
                {"px": {"currency": "USD", "value": "0.45"}, "qty": "10.0"},
                {"px": {"currency": "USD", "value": "0.50"}, "qty": "1.0"},
            ],
            "offers": [
                {"px": {"currency": "USD", "value": "0.60"}, "qty": "1.0"},
                {"px": {"currency": "USD", "value": "0.59"}, "qty": "2.0"},
            ],
        }
    }
    bid, ask = best_bid_ask_from_us_book(book)
    assert bid == 0.50
    assert ask == 0.59

