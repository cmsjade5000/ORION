import unittest
from pathlib import Path


class TestInstallOrionLocalJobBundleLaunchAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.script = (
            repo / "scripts" / "install_orion_local_job_bundle_launchagent.sh"
        ).read_text(encoding="utf-8")
        cls.readme = (repo / "scripts" / "README.md").read_text(encoding="utf-8")

    def test_installer_is_compatibility_wrapper_to_canonical_maintenance_bundle(self):
        git_idx = self.script.index('repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"')
        fallback_idx = self.script.index('repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"')
        self.assertLess(git_idx, fallback_idx)
        self.assertIn('legacy_plist="${launch_agents_dir}/com.openclaw.orion.local_job_bundle.plist"', self.script)
        self.assertIn('rm -f "${legacy_plist}"', self.script)
        self.assertIn('maintenance_installer="${repo_root}/scripts/install_orion_local_maintenance_launchagents.sh"', self.script)
        self.assertIn('exec "${maintenance_installer}" "${repo_root}"', self.script)

    def test_readme_documents_canonical_maintenance_installer(self):
        self.assertIn("install_orion_local_job_bundle_launchagent.sh", self.readme)
        self.assertIn("install_orion_local_maintenance_launchagents.sh", self.readme)
        self.assertIn("compatibility wrapper", self.readme.lower())
        self.assertIn("canonical installer", self.readme.lower())


if __name__ == "__main__":
    unittest.main()
