import json
import unittest
from pathlib import Path


class TestOpenClawWorkspaceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.json_example = json.loads((cls.repo / "openclaw.json.example").read_text(encoding="utf-8"))
        cls.yaml_example = (cls.repo / "openclaw.yaml").read_text(encoding="utf-8")
        cls.readme = (cls.repo / "README.md").read_text(encoding="utf-8")
        cls.bootstrap = (cls.repo / "BOOTSTRAP.md").read_text(encoding="utf-8")
        cls.workflow = (cls.repo / "docs" / "WORKFLOW.md").read_text(encoding="utf-8")
        cls.recovery = (cls.repo / "docs" / "RECOVERY.md").read_text(encoding="utf-8")
        cls.migration = (cls.repo / "docs" / "OPENCLAW_CONFIG_MIGRATION.md").read_text(
            encoding="utf-8"
        )
        cls.pdf_workflow = (cls.repo / "docs" / "PDF_REVIEW_WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        cls.makefile = (cls.repo / "Makefile").read_text(encoding="utf-8")
        cls.discord_setup = (cls.repo / "docs" / "DISCORD_SETUP.md").read_text(encoding="utf-8")
        cls.nvim = (cls.repo / "docs" / "NVIDIA_BUILD_KIMI.md").read_text(encoding="utf-8")
        cls.fly_toml = (cls.repo / "fly.orion-core.toml").read_text(encoding="utf-8")
        cls.compat_0114 = (cls.repo / "docs" / "CODEX_0114_COMPATIBILITY_REPORT.md").read_text(
            encoding="utf-8"
        )
        cls.app_healthz = (cls.repo / "app" / "src" / "app" / "healthz" / "route.ts").read_text(
            encoding="utf-8"
        )
        cls.app_readyz = (cls.repo / "app" / "src" / "app" / "readyz" / "route.ts").read_text(
            encoding="utf-8"
        )
        cls.dashboard_server = (
            cls.repo / "apps" / "telegram-miniapp-dashboard" / "server" / "index.js"
        ).read_text(encoding="utf-8")

    def test_examples_pin_tools_profile(self):
        self.assertEqual(self.json_example["tools"]["profile"], "coding")
        self.assertIn("profile: coding", self.yaml_example)

    def test_examples_use_secretref_for_optional_credentials(self):
        discord_token = self.json_example["channels"]["discord"]["token"]
        self.assertEqual(
            discord_token,
            {"source": "env", "provider": "default", "id": "DISCORD_BOT_TOKEN"},
        )

        nvidia_key = self.json_example["models"]["providers"]["nvidia-build"]["apiKey"]
        self.assertEqual(
            nvidia_key,
            {"source": "env", "provider": "default", "id": "NVIDIA_API_KEY"},
        )

        self.assertIn("source: env", self.yaml_example)
        self.assertIn("id: DISCORD_BOT_TOKEN", self.yaml_example)
        self.assertIn("id: NVIDIA_API_KEY", self.yaml_example)

    def test_docs_add_config_validate_to_standard_checks(self):
        for text in (self.readme, self.bootstrap, self.workflow, self.recovery, self.migration):
            self.assertIn("openclaw config validate --json", text)

        self.assertIn("config-validate:", self.makefile)
        self.assertIn(
            "ci: config-validate openclaw-compat shellcheck test plan-graph task-packets",
            self.makefile,
        )

    def test_pdf_review_workflow_is_documented(self):
        self.assertIn("sessions_spawn", self.pdf_workflow)
        self.assertIn(".openclaw/attachments/", self.pdf_workflow)
        self.assertIn("pdf", self.pdf_workflow)
        self.assertIn("TASK_PACKET v1", self.pdf_workflow)

    def test_secretref_guidance_is_documented(self):
        self.assertIn("SecretRef", self.discord_setup)
        self.assertIn("SecretRef", self.nvim)
        self.assertIn("SecretRef", self.migration)

    def test_codex_0114_health_contract_is_implemented(self):
        self.assertIn('path = "/readyz"', self.fly_toml)
        self.assertIn('check: "healthz"', self.app_healthz)
        self.assertIn('check: "readyz"', self.app_readyz)
        self.assertIn('app.get("/healthz"', self.dashboard_server)
        self.assertIn('app.get("/readyz"', self.dashboard_server)
        self.assertIn('app.get("/api/health"', self.dashboard_server)

    def test_codex_0114_report_locks_permission_plugin_and_health_defaults(self):
        for needle in ("request_permissions", "@plugin", "/readyz", "/healthz", "workspace-write"):
            self.assertIn(needle, self.compat_0114)


if __name__ == "__main__":
    unittest.main()
