import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_router():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "email_triage_router.py"
    spec = importlib.util.spec_from_file_location("email_triage_router", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestEmailTriageRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _load_router()

    def test_extract_email_and_domain(self):
        addr = self.r.extract_email("PayPal Security <Alerts@PayPal.COM>")
        self.assertEqual(addr, "alerts@paypal.com")
        self.assertEqual(self.r.domain_from_email(addr), "paypal.com")

    def test_extract_link_domains_dedup_and_normalize(self):
        text = "See https://EXAMPLE.com/a and https://example.com:443/b and http://8.8.8.8/x"
        domains = self.r.extract_link_domains(text)
        self.assertEqual(domains, ["example.com", "8.8.8.8"])

    def test_extract_attachment_types_dedup(self):
        message = {
            "attachments": [
                {"filename": "invoice.PDF"},
                {"filename": "photo.JPG"},
                {"filename": "run.EXE"},
                {"filename": "dup.pdf"},
            ]
        }
        self.assertEqual(self.r.extract_attachment_types(message), ["pdf", "jpg", "exe"])

    def test_classify_intent(self):
        self.assertEqual(self.r.classify_intent("Need budget review", "Should we buy this?"), "money")
        self.assertEqual(self.r.classify_intent("Please draft a reply", "Polish this email"), "draft")
        self.assertEqual(self.r.classify_intent("Any latest AI news", "headlines please"), "news")

    def test_assess_risk_executable_and_raw_ip(self):
        reasons = self.r.assess_risk(
            sender_domain="example.com",
            link_domains=["8.8.8.8"],
            attachment_types=["exe"],
            subject="update",
            body="see attached",
            trusted_domains={"example.com"},
        )
        self.assertTrue(any("executable" in x for x in reasons), reasons)
        self.assertTrue(any("raw IP" in x for x in reasons), reasons)

    def test_triage_message_quarantines_when_risky(self):
        message = {
            "message_id": "m-1",
            "from": "Unknown <alerts@weird-domain.biz>",
            "subject": "Urgent password reset",
            "text": "login now https://bit.ly/abc",
            "labels": ["received"],
            "attachments": [{"filename": "tool.exe"}],
            "timestamp": "2026-02-24T12:00:00Z",
        }
        triage = self.r.triage_message(message, default_owner="POLARIS", trusted_domains={"paypal.com"})
        self.assertTrue(triage.quarantine)
        self.assertEqual(triage.owner, "POLARIS")
        self.assertTrue(len(triage.reasons) >= 1)

    def test_render_task_packet_contains_required_fields(self):
        triage = self.r.TriageResult(
            message_id="m-2",
            owner="POLARIS",
            intent="admin",
            quarantine=False,
            sender="Ops <ops@example.com>",
            sender_domain="example.com",
            subject="Schedule follow-up",
            request_summary="Subject: Schedule follow-up. Ask: Please remind me tomorrow.",
            link_domains=["example.com"],
            attachment_types=["pdf"],
            reasons=[],
            timestamp="2026-02-24T12:00:00Z",
        )
        packet = self.r.render_task_packet(triage, notify="telegram", opened=self.r.date(2026, 2, 24), due_days=2)
        self.assertIn("TASK_PACKET v1", packet)
        self.assertIn("Owner: POLARIS", packet)
        self.assertIn("Requester: ORION", packet)
        self.assertIn("Objective:", packet)
        self.assertIn("Success Criteria:", packet)
        self.assertIn("Constraints:", packet)
        self.assertIn("Inputs:", packet)
        self.assertIn("Risks:", packet)
        self.assertIn("Stop Gates:", packet)
        self.assertIn("Output Format:", packet)
        self.assertIn("Opened: 2026-02-24", packet)
        self.assertIn("Due: 2026-02-26", packet)

    def test_compute_idempotency_key_is_stable(self):
        a = self.r.compute_idempotency_key("m-3", "POLARIS")
        b = self.r.compute_idempotency_key("m-3", "POLARIS")
        c = self.r.compute_idempotency_key("m-3", "ATLAS")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            state = {
                "processed_message_ids": ["m-1", "m-2"],
                "written_keys": ["k-1"],
                "updated_at": "2026-02-24T00:00:00Z",
            }
            self.r._save_state(p, state)
            loaded = self.r._load_state(p)
            self.assertEqual(loaded["processed_message_ids"], ["m-1", "m-2"])
            self.assertEqual(loaded["written_keys"], ["k-1"])


if __name__ == "__main__":
    unittest.main()
