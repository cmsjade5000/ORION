from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


class TestMomentum(unittest.TestCase):
    def test_momentum_pct_basic(self) -> None:
        from scripts.arb.momentum import HISTORY_REL, momentum_pct

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / HISTORY_REL
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "series": {
                            "KXBTC": [
                                {"ts_unix": 1000, "spot_ref": 100.0},
                                {"ts_unix": 1600, "spot_ref": 110.0},
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            m = momentum_pct(str(root), series="KXBTC", lookback_s=600, now_ts_unix=1600)
            self.assertIsNotNone(m)
            assert m is not None
            self.assertAlmostEqual(m, 0.10, places=6)

    def test_update_history_dedup_interval(self) -> None:
        from scripts.arb.momentum import HISTORY_REL, update_ref_spot_history

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            update_ref_spot_history(str(root), series="KXETH", spot_ref=2000.0, ts_unix=1000, min_interval_s=60)
            update_ref_spot_history(str(root), series="KXETH", spot_ref=2001.0, ts_unix=1010, min_interval_s=60)
            p = root / HISTORY_REL
            obj = json.loads(p.read_text(encoding="utf-8"))
            arr = obj["series"]["KXETH"]
            self.assertEqual(len(arr), 1)


if __name__ == "__main__":
    unittest.main()

