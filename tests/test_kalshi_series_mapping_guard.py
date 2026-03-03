from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestKalshiSeriesMappingGuard(unittest.TestCase):
    def test_scan_refuses_unmapped_series(self) -> None:
        import scripts.kalshi_ref_arb as mod

        args = SimpleNamespace(kalshi_base_url="https://api.elections.kalshi.com", series="KX_UNKNOWN")
        with patch("sys.stdout.write") as w:
            rc = mod.cmd_scan(args)
        self.assertEqual(int(rc), 2)
        payload = "".join(str(a[0][0]) for a in w.call_args_list if a and a[0])
        self.assertIn("unmapped_series", payload)


if __name__ == "__main__":
    unittest.main()

