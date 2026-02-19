from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class TestKalshiHealthcheck(unittest.TestCase):
    def test_healthcheck_warns_on_bad_runtime(self) -> None:
        import scripts.kalshi_ref_arb as mod

        args = argparse.Namespace(kalshi_base_url="https://api.elections.kalshi.com", check_auth=False)
        buf = io.StringIO()
        with patch.dict("os.environ", {"KALSHI_ARB_EXECUTION_MODE": "invalid"}, clear=False):
            with redirect_stdout(buf):
                rc = mod.cmd_healthcheck(args)
        obj = json.loads(buf.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(obj["status"], "warn")
        self.assertEqual(obj["runtime"]["execution_mode"], "paper")


if __name__ == "__main__":
    unittest.main()

