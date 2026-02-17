import importlib.util
import sys
import unittest
from pathlib import Path


def _load_mod():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "aegis_incident_score.py"
    spec = importlib.util.spec_from_file_location("aegis_incident_score", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestAegisIncidentScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_mod()

    def test_s1_on_gateway_down(self):
        sc = self.m.score_signals({"gateway_health_ok": False})  # type: ignore[attr-defined]
        self.assertEqual(sc.severity, "S1")

    def test_s1_on_config_integrity_fail(self):
        sc = self.m.score_signals({"config_integrity_ok": False})  # type: ignore[attr-defined]
        self.assertEqual(sc.severity, "S1")

    def test_s2_on_flapping(self):
        sc = self.m.score_signals({"gateway_health_ok": True, "restarts_15m": 3})  # type: ignore[attr-defined]
        self.assertEqual(sc.severity, "S2")

    def test_s3_on_minor_signal(self):
        sc = self.m.score_signals({"ssh_auth_failures_15m": 1})  # type: ignore[attr-defined]
        self.assertEqual(sc.severity, "S3")

