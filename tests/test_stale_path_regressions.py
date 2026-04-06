import unittest
from pathlib import Path


class TestStalePathRegressions(unittest.TestCase):
    def test_legacy_duplicate_scripts_are_absent(self):
        repo = Path(__file__).resolve().parents[1]
        stale_paths = [
            repo / "freshness_check.py",
            repo / "kalshi_check.py",
            repo / "temp_check.py",
            repo / "scripts" / "loop_test_telegram_realworld.py",
            repo / "bot" / "orion-core-bot",
        ]
        present = [str(path.relative_to(repo)) for path in stale_paths if path.exists()]
        self.assertEqual(
            present,
            [],
            f"legacy duplicate or superseded scripts should stay removed: {present}",
        )

    def test_removed_miniapp_surfaces_stay_absent(self):
        repo = Path(__file__).resolve().parents[1]
        stale_paths = [
            repo / "app",
            repo / "apps" / "telegram-miniapp-dashboard",
            repo / "src" / "plugins" / "telegram" / "miniapp",
            repo / "scripts" / "miniapp_ingest.py",
            repo / "scripts" / "miniapp_command_relay.py",
            repo / "scripts" / "miniapp_upload_artifact.sh",
            repo / "scripts" / "telegram_open_miniapp.sh",
            repo / "scripts" / "telegram_send_miniapp_button.sh",
            repo / "fly.orion-core.toml",
        ]
        present = [str(path.relative_to(repo)) for path in stale_paths if path.exists()]
        self.assertEqual(present, [], f"miniapp surfaces should stay removed: {present}")


if __name__ == "__main__":
    unittest.main()
