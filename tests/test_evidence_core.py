import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path


def _load_evidence_core():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "evidence_core.py"
    spec = importlib.util.spec_from_file_location("evidence_core", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestEvidenceCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = _load_evidence_core()

    def test_parse_rfc3339_date_only(self):
        d = self.e.parse_rfc3339("2026-02-17")
        self.assertEqual(d.tzinfo, dt.timezone.utc)
        self.assertEqual(d.hour, 0)

    def test_parse_rfc3339_requires_tz(self):
        with self.assertRaises(Exception):
            self.e.parse_rfc3339("2026-02-17T10:00:00")

    def test_validate_items_window(self):
        now = dt.datetime(2026, 2, 17, 12, 0, 0, tzinfo=dt.timezone.utc)
        ok = {
            "title": "T",
            "source": "S",
            "url": "https://example.com/x",
            "published_at": "2026-02-17T11:00:00Z",
            "claim": "C",
            "source_tier": "secondary",
            "confidence": "medium",
        }
        res = self.e.validate_items([ok], time_window_hours=2, now=now)
        self.assertTrue(res.ok, res.errors)

        stale = dict(ok)
        stale["published_at"] = "2026-02-17T01:00:00Z"
        res2 = self.e.validate_items([stale], time_window_hours=2, now=now)
        self.assertFalse(res2.ok)

    def test_validate_items_tier_minimum(self):
        now = dt.datetime(2026, 2, 17, 12, 0, 0, tzinfo=dt.timezone.utc)
        low = {
            "title": "T",
            "source": "S",
            "url": "https://example.com/x",
            "published_at": "2026-02-17T11:00:00Z",
            "claim": "C",
            "source_tier": "low",
            "confidence": "low",
        }
        res = self.e.validate_items([low], time_window_hours=24, now=now, min_source_tier="secondary")
        self.assertFalse(res.ok)

    def test_validate_items_multiclaim_traceability(self):
        now = dt.datetime(2026, 2, 17, 12, 0, 0, tzinfo=dt.timezone.utc)
        ok = {
            "title": "T",
            "source": "S",
            "published_at": "2026-02-17T11:00:00Z",
            "claims": [
                {"claim": "A", "url": "https://example.com/a"},
                {"claim": "B", "url": "https://example.com/b"},
            ],
            "source_tier": "secondary",
            "confidence": "medium",
        }
        res = self.e.validate_items([ok], time_window_hours=24, now=now, min_source_tier="low")
        self.assertTrue(res.ok, res.errors)

        bad = dict(ok)
        bad["claims"] = [{"claim": "A", "url": ""}]
        res2 = self.e.validate_items([bad], time_window_hours=24, now=now, min_source_tier="low")
        self.assertFalse(res2.ok)
