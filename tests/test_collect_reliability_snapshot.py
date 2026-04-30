import unittest

from scripts.collect_reliability_snapshot import _slo_status


class TestCollectReliabilitySnapshot(unittest.TestCase):
    def test_slo_warns_when_eval_gate_fails(self):
        status = _slo_status(
            queue_health={"status": "pass"},
            queue_growth={"slo_pass": True},
            inbox_contract={"status": "pass"},
            eval_gate={"status": "fail"},
        )

        self.assertEqual(status, "warn")

    def test_slo_passes_when_all_gates_pass(self):
        status = _slo_status(
            queue_health={"status": "pass"},
            queue_growth={"slo_pass": True},
            inbox_contract={"status": "pass"},
            eval_gate={"status": "pass"},
        )

        self.assertEqual(status, "pass")


if __name__ == "__main__":
    unittest.main()
