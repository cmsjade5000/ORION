import unittest

from scripts.discord_routing import DiscordContext, conversation_key, openclaw_target


class TestDiscordRouting(unittest.TestCase):
    def test_dm_conversation_key_includes_user(self):
        ctx = DiscordContext(channel_id="dmchan", user_id="u1", guild_id=None, thread_id=None)
        self.assertEqual(conversation_key(ctx), "discord:dm:channel:dmchan:user:u1")

    def test_guild_channel_conversation_key(self):
        ctx = DiscordContext(channel_id="c1", guild_id="g1")
        self.assertEqual(conversation_key(ctx), "discord:guild:g1:channel:c1:thread:-")

    def test_thread_conversation_key(self):
        ctx = DiscordContext(channel_id="c1", guild_id="g1", thread_id="t1")
        self.assertEqual(conversation_key(ctx), "discord:guild:g1:channel:c1:thread:t1")

    def test_openclaw_target_dm(self):
        ctx = DiscordContext(channel_id="dmchan", user_id="u1")
        self.assertEqual(openclaw_target(ctx), "user:u1")

    def test_openclaw_target_channel(self):
        ctx = DiscordContext(channel_id="c1", guild_id="g1")
        self.assertEqual(openclaw_target(ctx), "channel:c1")

    def test_openclaw_target_thread(self):
        ctx = DiscordContext(channel_id="c1", guild_id="g1", thread_id="t1")
        self.assertEqual(openclaw_target(ctx), "channel:t1")

    def test_dm_requires_user_id(self):
        with self.assertRaises(ValueError):
            conversation_key(DiscordContext(channel_id="dmchan", user_id=None))
        with self.assertRaises(ValueError):
            openclaw_target(DiscordContext(channel_id="dmchan", user_id=None))

