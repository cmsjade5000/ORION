import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def _load_pir():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "pir_from_incident.py"
    spec = importlib.util.spec_from_file_location("pir_from_incident", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


INCIDENTS_SAMPLE = """\
# Incidents (Append-Only)

## Incidents

INCIDENT v1
Id: INC-20260217-1200-test
Opened: 2026-02-17T12:00:00Z
Opened By: ORION
Severity: P1
Trigger: ORION_UNREACHABLE
Summary: ORION was unreachable for 2 minutes.
Evidence:
- gateway health check failed
Actions:
- openclaw gateway restart
Follow-up Owner: ATLAS
Follow-up Tasks:
- Add alert suppression guard
Closed: open
"""


class TestPIRFromIncident(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_pir()

    def test_parse_and_render(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "INCIDENTS.md"
            p.write_text(INCIDENTS_SAMPLE, encoding="utf-8")
            incidents = self.m.load_incidents(p)  # type: ignore[attr-defined]
            inc = self.m.find_incident_by_id(incidents, "INC-20260217-1200-test")  # type: ignore[attr-defined]
            self.assertIsNotNone(inc)
            txt = self.m.render_pir(inc)  # type: ignore[arg-type,attr-defined]
            self.assertIn("PIR v1", txt)
            self.assertIn("INC-20260217-1200-test", txt)
            self.assertIn("Follow-up Task Packet", txt)

    def test_missing_incident(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "INCIDENTS.md"
            p.write_text(INCIDENTS_SAMPLE, encoding="utf-8")
            incidents = self.m.load_incidents(p)  # type: ignore[attr-defined]
            inc = self.m.find_incident_by_id(incidents, "INC-NOT-THERE")  # type: ignore[attr-defined]
            self.assertIsNone(inc)

