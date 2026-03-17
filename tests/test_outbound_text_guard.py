import unittest

from scripts.outbound_text_guard import contains_internal_artifacts, sanitize_outbound_text


class TestOutboundTextGuard(unittest.TestCase):
    def test_strips_olcall_wrapper(self):
        text = 'OLCALL>[{"name":"sessions_spawn","arguments":{"agentId":"polaris"}}]ALL>'
        self.assertEqual(sanitize_outbound_text(text), "Internal runtime output was suppressed.")

    def test_strips_json_tool_call_payload(self):
        text = '{"result":{"payloads":[{"type":"toolCall","name":"read"}]}}'
        self.assertEqual(sanitize_outbound_text(text), "Internal runtime output was suppressed.")

    def test_keeps_normal_user_facing_text(self):
        text = "Queued for POLARIS.\n\nI’ll report back when it finishes."
        self.assertEqual(sanitize_outbound_text(text), text)

    def test_detects_internal_artifacts(self):
        self.assertTrue(contains_internal_artifacts("<think>hidden</think>"))
        self.assertFalse(contains_internal_artifacts("Normal update only."))


if __name__ == "__main__":
    unittest.main()
