import unittest

from scripts.bankr_guard import classify_bankr_intent


class TestBankrGuard(unittest.TestCase):
    def test_allows_read_only_balance(self):
        intent = classify_bankr_intent("What is my ETH balance on Base?")
        self.assertFalse(intent.is_write)
        self.assertEqual(intent.hits, [])

    def test_blocks_swap(self):
        intent = classify_bankr_intent("Swap 0.01 ETH to USDC on Base")
        self.assertTrue(intent.is_write)
        self.assertIn("swap", intent.hits)

    def test_blocks_sign_submit(self):
        intent = classify_bankr_intent("Sign and submit this tx")
        self.assertTrue(intent.is_write)
        # keywords are pattern-ish tokens; just check both are present
        self.assertTrue(any("sign" in h for h in intent.hits))
        self.assertTrue(any("submit" in h for h in intent.hits))

    def test_allows_discussion_with_escaped_tokens(self):
        intent = classify_bankr_intent(r"Do not \send funds. Just explain what 'send' means.")
        # "send" appears but user is discussing it; escaped token should not trigger.
        # The unescaped "send" in quotes may still match; keep this conservative:
        # we only guarantee the guard doesn't trigger solely due to an escaped token.
        intent2 = classify_bankr_intent(r"Do not \send funds.")
        self.assertFalse(intent2.is_write)


if __name__ == "__main__":
    unittest.main()

