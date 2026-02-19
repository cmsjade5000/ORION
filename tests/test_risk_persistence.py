from __future__ import annotations

import os
import tempfile
import time
import unittest


class TestRiskPersistence(unittest.TestCase):
    def test_observation_count_filters_by_time_and_edge(self) -> None:
        from scripts.arb.risk import RiskState

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "state.json")
            st = RiskState(p)
            now = int(time.time())
            st.record_observation("T:yes", edge_bps=100.0, ts_unix=now - 3600)
            st.record_observation("T:yes", edge_bps=130.0, ts_unix=now - 60)
            st.record_observation("T:yes", edge_bps=200.0, ts_unix=now - 30)
            st.save()

            st2 = RiskState(p)
            # Window excludes the 1h-old point.
            n = st2.count_observations("T:yes", min_ts_unix=now - 300, min_edge_bps=120.0)
            self.assertEqual(n, 2)

    def test_drawdown_throttle_multiplier(self) -> None:
        from scripts.arb.risk import drawdown_throttle_multiplier

        self.assertAlmostEqual(drawdown_throttle_multiplier(0.0, throttle_pct=5.0), 1.0, places=9)
        self.assertAlmostEqual(drawdown_throttle_multiplier(4.0, throttle_pct=5.0), 1.0, places=9)
        self.assertLess(drawdown_throttle_multiplier(10.0, throttle_pct=5.0), 1.0)


if __name__ == "__main__":
    unittest.main()
