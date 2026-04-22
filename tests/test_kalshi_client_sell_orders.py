from __future__ import annotations

import unittest
from unittest.mock import patch


class TestKalshiClientSellOrders(unittest.TestCase):
    def test_create_order_supports_reduce_only_sell(self) -> None:
        from scripts.arb.kalshi import KalshiClient, KalshiOrder

        client = KalshiClient(api_key_id="key", private_key_path="/tmp/fake-key.pem")

        with patch.object(client, "_require_auth", return_value=None):
            with patch.object(client, "_post_json", return_value={"ok": True}) as post_mock:
                resp = client.create_order(
                    KalshiOrder(
                        ticker="KXBTC-TEST",
                        side="no",
                        action="sell",
                        count=4,
                        price_dollars="0.9100",
                        client_order_id="cid-1",
                        time_in_force="immediate_or_cancel",
                        reduce_only=True,
                    )
                )

        self.assertEqual(resp, {"ok": True})
        body = post_mock.call_args.kwargs["body"]
        self.assertEqual(body["ticker"], "KXBTC-TEST")
        self.assertEqual(body["side"], "no")
        self.assertEqual(body["action"], "sell")
        self.assertEqual(body["count"], 4)
        self.assertEqual(body["no_price"], 91)
        self.assertEqual(body["time_in_force"], "immediate_or_cancel")
        self.assertTrue(body["reduce_only"])
        self.assertTrue(body["cancel_order_on_pause"])
        self.assertNotIn("yes_price", body)


if __name__ == "__main__":
    unittest.main()
