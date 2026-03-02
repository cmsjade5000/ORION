import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestPogoExtract(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]
        self.script = self.repo / "scripts" / "pogo_extract.mjs"

    def _run(self, news_html: str, events_html: str, now_iso: str = "2026-02-25T12:00:00Z") -> dict:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            news_path = td_path / "news.html"
            events_path = td_path / "events.html"
            news_path.write_text(news_html, encoding="utf-8")
            events_path.write_text(events_html, encoding="utf-8")

            proc = subprocess.run(
                [
                    "node",
                    str(self.script),
                    "--news-html",
                    str(news_path),
                    "--events-html",
                    str(events_path),
                    "--tz",
                    "America/New_York",
                    "--now",
                    now_iso,
                    "--stale-hours",
                    "120",
                ],
                cwd=str(self.repo),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            return json.loads(proc.stdout)

    def test_extracts_news_events_and_shiny_signals(self):
        news_html = """
        <div>
          <a href="/news/communityday-march-2026-scorbunny" class="_newsCard_abc">
            <div class="_newsCardContent_abc">
              <pg-date-format timestamp="1771956000000"></pg-date-format>
              <div class="_size:heading_sfz9t_19">March Community Day: Scorbunny</div>
            </div>
          </a>
        </div>
        """
        events_html = """
        <div>
          <a href="https://pokemongo.com/gotour/global" class="_eventsCard_xyz">
            <div class="_eventsCardContent_xyz">
              <pg-date-format startDate="2026-02-24" endDate="2026-02-26"></pg-date-format>
              <div class="_size:heading_sfz9t_19">Pokémon GO Tour: Kalos – Global</div>
            </div>
          </a>
        </div>
        """
        data = self._run(news_html, events_html)

        self.assertEqual(len(data["news"]), 1)
        self.assertEqual(data["news"][0]["title"], "March Community Day: Scorbunny")

        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["events"][0]["status"], "active")

        self.assertGreaterEqual(len(data["shinySignals"]), 1)
        self.assertTrue(
            any("Community Day" in sig.get("title", "") for sig in data["shinySignals"]),
            msg=f"shinySignals did not include Community Day: {data['shinySignals']}",
        )
        self.assertIn(data["freshness"]["confidence"], {"high", "medium", "low"})

    def test_marks_stale_when_news_is_old(self):
        # 2017-01-01 UTC in milliseconds.
        old_ts_ms = "1483228800000"
        news_html = f"""
        <div>
          <a href="/news/old-news" class="_newsCard_stale">
            <div class="_newsCardContent_stale">
              <pg-date-format timestamp="{old_ts_ms}"></pg-date-format>
              <div class="_size:heading_sfz9t_19">Old Patch Notes</div>
            </div>
          </a>
        </div>
        """
        events_html = """
        <div>
          <a href="https://pokemongo.com/events/test" class="_eventsCard_test">
            <div class="_eventsCardContent_test">
              <pg-date-format startDate="2026-02-25" endDate="2026-02-25"></pg-date-format>
              <div class="_size:heading_sfz9t_19">Spotlight Hour</div>
            </div>
          </a>
        </div>
        """
        data = self._run(news_html, events_html)

        self.assertTrue(data["freshness"]["stale"])
        self.assertEqual(data["freshness"]["confidence"], "low")


if __name__ == "__main__":
    unittest.main()
