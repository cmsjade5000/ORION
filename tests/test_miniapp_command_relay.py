import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


def _load_relay_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "miniapp_command_relay.py"
    spec = importlib.util.spec_from_file_location("miniapp_command_relay", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestMiniappCommandRelay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_relay_module()

    def test_token_transport_guard_allows_https_and_local_http(self):
        self.assertTrue(self.m._token_auth_transport_allowed("https://example.com"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://localhost:8787"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://127.0.0.1:8787"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://[::1]:8787"))
        self.assertFalse(self.m._token_auth_transport_allowed("http://example.com"))

    def test_http_post_json_short_circuits_on_insecure_token_transport(self):
        with mock.patch.object(self.m.urllib.request, "urlopen") as urlopen_mock:
            status, payload = self.m.http_post_json("http://example.com/api/relay/claim", "secret", {"workerId": "w"})
        self.assertEqual(status, 0)
        self.assertIsNone(payload)
        self.assertEqual(urlopen_mock.call_count, 0)

    def test_main_refuses_insecure_http_base_with_token(self):
        with mock.patch.object(self.m, "get_base_url", return_value="http://example.com"), mock.patch.object(
            self.m,
            "get_token",
            return_value="secret",
        ), mock.patch.object(sys, "argv", ["miniapp_command_relay.py", "--once"]):
            stderr = io.StringIO()
            with mock.patch.object(sys, "stderr", stderr):
                rc = self.m.main()

        self.assertEqual(rc, 2)
        self.assertIn("non-HTTPS transport", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
