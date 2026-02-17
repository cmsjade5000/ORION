import unittest

from scripts.discord_mass_mention_guard import find_mass_mentions, has_mass_mentions


class TestDiscordMassMentionGuard(unittest.TestCase):
    def test_allows_normal_message(self):
        self.assertFalse(has_mass_mentions("status update: all good"))
        self.assertEqual(find_mass_mentions("status update: all good"), [])

    def test_blocks_everyone(self):
        self.assertTrue(has_mass_mentions("Heads up @everyone"))
        self.assertEqual(find_mass_mentions("Heads up @everyone"), ["@everyone"])

    def test_blocks_here_case_insensitive(self):
        self.assertTrue(has_mass_mentions("Paging @HERE now"))
        self.assertEqual(find_mass_mentions("Paging @HERE now"), ["@here"])

    def test_allows_email_like_text(self):
        self.assertFalse(has_mass_mentions("contact me at ops@here.io"))
        self.assertEqual(find_mass_mentions("contact me at ops@here.io"), [])

    def test_allows_backslash_escaped_token(self):
        self.assertFalse(has_mass_mentions(r"literal token: \@everyone"))
        self.assertEqual(find_mass_mentions(r"literal token: \@everyone"), [])

    def test_deduplicates_multiple_hits(self):
        text = "@everyone then @here then @EVERYONE again"
        self.assertEqual(find_mass_mentions(text), ["@everyone", "@here"])


if __name__ == "__main__":
    unittest.main()
