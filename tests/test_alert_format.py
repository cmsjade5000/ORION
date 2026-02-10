import subprocess
import unittest
from pathlib import Path


class TestAlertFormat(unittest.TestCase):
    def test_format_alert_full(self):
        repo_root = Path(__file__).resolve().parents[1]
        lib = repo_root / "scripts" / "aegis_remote" / "lib_alert_format.sh"
        cmd = (
            f"source '{lib}'; "
            "format_alert "
            "'AEGIS (System Watch): ORION gateway restarted' "
            "'ORION health check failed.' "
            "'Restarted ORION gateway once; health is OK now.' "
            "'No action needed.' "
            "'INC-AEGIS-OPS-20260208T132500Z'"
        )
        r = subprocess.run(
            ["bash", "-lc", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            r.stdout.splitlines(),
            [
                "AEGIS (System Watch): ORION gateway restarted",
                "",
                "What I saw: ORION health check failed.",
                "What I did: Restarted ORION gateway once; health is OK now.",
                "Next: No action needed.",
                "Incident: INC-AEGIS-OPS-20260208T132500Z",
            ],
        )
