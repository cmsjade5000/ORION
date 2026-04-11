import subprocess
import unittest
from pathlib import Path


class TestInstallOrionAegisDefenseWatchLaunchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.script = repo / "scripts" / "aegis_defense_watch.sh"
        cls.plist = (repo / "scripts" / "orion_aegis_defense_watch_launchagent.plist").read_text(
            encoding="utf-8"
        )

    def test_watch_script_has_valid_bash_syntax(self):
        cp = subprocess.run(
            ["bash", "-n", str(self.script)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(cp.returncode, 0, cp.stderr)

    def test_launchagent_runs_script_directly(self):
        self.assertIn("<string>/bin/bash</string>", self.plist)
        self.assertIn("<string>__REPO_ROOT__/scripts/aegis_defense_watch.sh</string>", self.plist)
        self.assertIn("<string>__HOME__/Library/Logs/orion_aegis_defense_watch.log</string>", self.plist)
        self.assertNotIn('<string>-lc</string>', self.plist)
        self.assertNotIn('"/bin/bash -lc', self.plist)


if __name__ == "__main__":
    unittest.main()
