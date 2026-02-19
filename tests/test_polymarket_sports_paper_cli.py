from __future__ import annotations

import argparse
import io
import unittest
from contextlib import redirect_stdout


class TestPolymarketSportsPaperCli(unittest.TestCase):
    def test_trade_refuses_allow_write(self) -> None:
        import scripts.polymarket_sports_paper as mod

        args = argparse.Namespace(allow_write=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_trade(args)
        self.assertEqual(int(rc), 2)
        out = buf.getvalue()
        self.assertIn("paper_only_module", out)


if __name__ == "__main__":
    unittest.main()

