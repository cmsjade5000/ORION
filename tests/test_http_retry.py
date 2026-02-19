from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import patch


def _http_err(code: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    hdrs = {}
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="https://example.test",
        code=int(code),
        msg="err",
        hdrs=hdrs,
        fp=None,
    )


class TestHttpRetry(unittest.TestCase):
    def test_http_client_env_overrides(self) -> None:
        from scripts.arb.http import HttpClient

        with patch.dict("os.environ", {"KALSHI_ARB_RETRY_MAX_ATTEMPTS": "5", "KALSHI_ARB_RETRY_BASE_MS": "300"}, clear=False):
            c = HttpClient()
        self.assertEqual(c._cfg.max_retries, 4)
        self.assertAlmostEqual(c._cfg.retry_backoff_seconds, 0.3, places=9)

    def test_retryable_http_codes(self) -> None:
        from scripts.arb.http import HttpClient

        e1 = _http_err(429)
        e2 = _http_err(503)
        e3 = _http_err(401)
        try:
            self.assertTrue(HttpClient._is_retryable(e1))
            self.assertTrue(HttpClient._is_retryable(e2))
            self.assertFalse(HttpClient._is_retryable(e3))
        finally:
            try:
                e1.close()
            except Exception:
                pass
            try:
                e2.close()
            except Exception:
                pass
            try:
                e3.close()
            except Exception:
                pass

    def test_retry_after_header_is_honored(self) -> None:
        from scripts.arb.http import HttpClient

        e = _http_err(429, retry_after="2")
        try:
            d = HttpClient._retry_delay_seconds(e, attempt=0, base=0.25)
            self.assertAlmostEqual(d, 2.0, places=9)
        finally:
            try:
                e.close()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
