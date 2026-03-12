import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import orion_policy_scorecard as scorecard


class TestOrionPolicyScorecard(unittest.TestCase):
    @staticmethod
    def _utc_now() -> str:
        return scorecard.dt.datetime.now(scorecard.dt.timezone.utc).isoformat()

    def _write_report(self, path: Path, *, timestamp: str, violations: list[dict], blocking: int = 0) -> None:
        payload = {
            "kind": "orion_policy_gate",
            "timestamp": timestamp,
            "summary": {
                "violations": len(violations),
                "blocking_violations": blocking,
            },
            "violations": violations,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _run_main(
        self,
        *,
        history_dir: Path,
        output_json: Path,
        output_md: Path,
        window_days: int,
        min_clean_days: int,
        max_false_positives: int,
    ) -> int:
        argv = [
            "orion_policy_scorecard.py",
            "--history-dir",
            str(history_dir),
            "--window-days",
            str(window_days),
            "--min-clean-days",
            str(min_clean_days),
            "--max-false-positives",
            str(max_false_positives),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
        with patch.object(sys, "argv", argv):
            return scorecard.main()

    def test_reads_history_and_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            history = root / "history"
            history.mkdir(parents=True, exist_ok=True)
            out_json = root / "out" / "scorecard.json"
            out_md = root / "out" / "scorecard.md"

            now = scorecard.dt.datetime.now(scorecard.dt.timezone.utc)
            yesterday = now - scorecard.dt.timedelta(days=1)

            self._write_report(history / "policy-gate-a.json", timestamp=now.isoformat(), violations=[])
            self._write_report(
                history / "policy-gate-b.json",
                timestamp=yesterday.isoformat(),
                violations=[{"rule_id": "R6_ANNOUNCE_SKIP", "blocking": True}],
                blocking=1,
            )
            # Ignored because wrong kind.
            (history / "policy-gate-ignore.json").write_text(
                json.dumps({"kind": "other", "summary": {"violations": 99, "blocking_violations": 99}}),
                encoding="utf-8",
            )

            rc = self._run_main(
                history_dir=history,
                output_json=out_json,
                output_md=out_md,
                window_days=7,
                min_clean_days=1,
                max_false_positives=10,
            )

            self.assertEqual(rc, 0)
            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())

            result = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(result["kind"], "orion_policy_scorecard")
            self.assertEqual(result["reports_scanned"], 2)
            self.assertEqual(result["totals"]["violations"], 1)
            self.assertEqual(result["totals"]["blocking_violations"], 1)

            md = out_md.read_text(encoding="utf-8")
            self.assertIn("# ORION Policy Gate Scorecard", md)
            self.assertIn("## Promotion Gate", md)

    def test_promotion_stage1_eligible_after_clean_window(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            history = root / "history"
            history.mkdir(parents=True, exist_ok=True)
            out_json = root / "scorecard.json"
            out_md = root / "scorecard.md"

            now = scorecard.dt.datetime.now(scorecard.dt.timezone.utc)
            d1 = now
            d2 = now - scorecard.dt.timedelta(days=1)

            self._write_report(history / "policy-gate-1.json", timestamp=d1.isoformat(), violations=[])
            self._write_report(history / "policy-gate-2.json", timestamp=d2.isoformat(), violations=[])

            rc = self._run_main(
                history_dir=history,
                output_json=out_json,
                output_md=out_md,
                window_days=2,
                min_clean_days=2,
                max_false_positives=0,
            )

            self.assertEqual(rc, 0)
            result = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(result["promotion"]["stage1"]["eligible_for_block"])

    def test_promotion_stage1_not_eligible_when_violations_exceed_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            history = root / "history"
            history.mkdir(parents=True, exist_ok=True)
            out_json = root / "scorecard.json"
            out_md = root / "scorecard.md"

            now = scorecard.dt.datetime.now(scorecard.dt.timezone.utc)
            clean_day = now
            violating_day = now - scorecard.dt.timedelta(days=1)

            self._write_report(history / "policy-gate-1.json", timestamp=clean_day.isoformat(), violations=[])
            self._write_report(
                history / "policy-gate-2.json",
                timestamp=violating_day.isoformat(),
                violations=[{"rule_id": "R6_ANNOUNCE_SKIP", "blocking": False}],
            )

            rc = self._run_main(
                history_dir=history,
                output_json=out_json,
                output_md=out_md,
                window_days=2,
                min_clean_days=1,
                max_false_positives=0,
            )

            self.assertEqual(rc, 0)
            result = json.loads(out_json.read_text(encoding="utf-8"))
            promo = result["promotion"]["stage1"]
            self.assertEqual(promo["stage_violations"], 1)
            self.assertFalse(promo["eligible_for_block"])


if __name__ == "__main__":
    unittest.main()
