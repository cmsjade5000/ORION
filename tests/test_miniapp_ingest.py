import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


def _load_ingest_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "miniapp_ingest.py"
    spec = importlib.util.spec_from_file_location("miniapp_ingest", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class _FakeResponse:
    def __init__(self, status: int, body: bytes = b"{}"):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class TestMiniappIngest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_ingest_module()

    def test_token_transport_guard_allows_https_and_local_http(self):
        self.assertTrue(self.m._token_auth_transport_allowed("https://example.com/api/ingest"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://localhost:8787/api/ingest"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://127.0.0.1:8787/api/ingest"))
        self.assertTrue(self.m._token_auth_transport_allowed("http://[::1]:8787/api/ingest"))
        self.assertFalse(self.m._token_auth_transport_allowed("http://example.com/api/ingest"))

    def test_emit_event_rejects_insecure_http_when_token_present(self):
        with mock.patch.object(self.m, "_get_ingest_url", return_value="http://example.com/api/ingest"), mock.patch.object(
            self.m,
            "_get_ingest_token",
            return_value="secret",
        ), mock.patch.object(self.m.urllib.request, "urlopen") as urlopen_mock:
            ok = self.m.emit_event({"type": "task.started"})

        self.assertFalse(ok)
        self.assertEqual(urlopen_mock.call_count, 0)

    def test_emit_event_allows_local_http_when_token_present(self):
        with mock.patch.object(self.m, "_get_ingest_url", return_value="http://localhost:8787/api/ingest"), mock.patch.object(
            self.m,
            "_get_ingest_token",
            return_value="secret",
        ), mock.patch.object(self.m.urllib.request, "urlopen", return_value=_FakeResponse(200)):
            ok = self.m.emit_event({"type": "task.started"})

        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
