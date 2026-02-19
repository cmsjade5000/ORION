from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch


class TestDigestLockSkip(unittest.TestCase):
    def test_digest_marks_warn_on_recent_lock_skip(self) -> None:
        import scripts.kalshi_digest as dig

        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "tmp", "kalshi_ref_arb", "runs")
            os.makedirs(runs, exist_ok=True)
            ts = int(time.time()) - 60
            with open(os.path.join(runs, f"{ts}.json"), "w", encoding="utf-8") as f:
                json.dump({"ts_unix": ts, "balance_rc": 0, "trade_rc": 0, "post_rc": 0, "trade": {"mode": "trade"}}, f)
            lcs = os.path.join(td, "tmp", "kalshi_ref_arb", "last_cycle_status.json")
            os.makedirs(os.path.dirname(lcs), exist_ok=True)
            with open(lcs, "w", encoding="utf-8") as f:
                json.dump({"ts_unix": ts, "status": "skipped_lock", "detail": "lock held"}, f)

            with patch.object(dig, "_repo_root", return_value=td), patch("sys.argv", ["kalshi_digest.py", "--window-hours", "8"]):
                rc = dig.main()
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

