import unittest

from scripts.outbound_text_guard import contains_internal_artifacts, sanitize_outbound_text


class TestOutboundTextGuard(unittest.TestCase):
    def test_strips_olcall_wrapper(self):
        text = 'OLCALL>[{"name":"sessions_spawn","arguments":{"agentId":"polaris"}}]ALL>'
        self.assertEqual(sanitize_outbound_text(text), "Internal runtime output was suppressed.")

    def test_extracts_final_wrapper_content(self):
        text = "<final>Apple Music is open.</final>"
        self.assertEqual(sanitize_outbound_text(text), "Apple Music is open.")

    def test_strips_split_final_lines_and_keeps_plain_text(self):
        text = "<final>\nApple Music is already closed.\n</final>"
        self.assertEqual(sanitize_outbound_text(text), "Apple Music is already closed.")

    def test_strips_json_tool_call_payload(self):
        text = '{"result":{"payloads":[{"type":"toolCall","name":"read"}]}}'
        self.assertEqual(sanitize_outbound_text(text), "Internal runtime output was suppressed.")

    def test_keeps_normal_user_facing_text(self):
        text = "Queued for POLARIS.\n\nI’ll report back when it finishes."
        self.assertEqual(sanitize_outbound_text(text), text)

    def test_rewrites_exec_approval_prompt(self):
        text = (
            "Approval required.\n\n"
            "Run:\n\n"
            "/approve bec1bd41-2775-4fb9-a6ae-299f4a3bdc02 allow-once\n\n"
            "Pending command:\n\n"
            "/Users/corystoner/src/ORION/scripts/kalshi_autotrade_cycle.py\n\n"
            "Other options:\n\n"
            "/approve bec1bd41-2775-4fb9-a6ae-299f4a3bdc02 allow-always\n"
            "/approve bec1bd41-2775-4fb9-a6ae-299f4a3bdc02 deny\n\n"
            "Host: gateway\n"
            "CWD: /Users/corystoner/.openclaw/workspaces/orion-ledger\n"
            "Expires in: 30m\n"
            "Full id: bec1bd41-2775-4fb9-a6ae-299f4a3bdc02"
        )
        self.assertEqual(sanitize_outbound_text(text), "Approval is pending for a requested command.")

    def test_detects_internal_artifacts(self):
        self.assertTrue(contains_internal_artifacts("<think>hidden</think>"))
        self.assertTrue(
            contains_internal_artifacts(
                "Approval required.\nRun:\n/approve abc allow-once\nPending command:\nfoo\nFull id: abc"
            )
        )
        self.assertFalse(contains_internal_artifacts("Normal update only."))


if __name__ == "__main__":
    unittest.main()
