import unittest

from scripts.arb.kalshi import dollars_to_cents_int


class TestKalshiPriceConv(unittest.TestCase):
    def test_dollars_to_cents(self):
        self.assertEqual(dollars_to_cents_int("0.0100"), 1)
        self.assertEqual(dollars_to_cents_int("0.9900"), 99)
        self.assertEqual(dollars_to_cents_int("1.0000"), 100)

    def test_invalid(self):
        self.assertIsNone(dollars_to_cents_int("nope"))
        self.assertIsNone(dollars_to_cents_int("-0.0100"))
        self.assertIsNone(dollars_to_cents_int("1.5000"))


if __name__ == "__main__":
    unittest.main()

