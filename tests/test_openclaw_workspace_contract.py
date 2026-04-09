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
        bootstrap_path = cls.repo / "BOOTSTRAP.md"
        cls.bootstrap = (
            bootstrap_path.read_text(encoding="utf-8") if bootstrap_path.exists() else ""
        )
        cls.workflow = (cls.repo / "docs" / "WORKFLOW.md").read_text(encoding="utf-8")
        cls.recovery = (cls.repo / "docs" / "RECOVERY.md").read_text(encoding="utf-8")
        cls.migration = (cls.repo / "docs" / "OPENCLAW_CONFIG_MIGRATION.md").read_text(
            encoding="utf-8"
        )
        cls.assistant_workflows = (cls.repo / "docs" / "POLARIS_ADMIN_WORKFLOWS.md").read_text(
            encoding="utf-8"
        )
        cls.error_review = (cls.repo / "docs" / "ORION_ERROR_REVIEW.md").read_text(
            encoding="utf-8"
        )
        cls.upgrade_notes = (cls.repo / "docs" / "OPENCLAW_2026_3_13_UPGRADE_NOTES.md").read_text(
            encoding="utf-8"
        )
        cls.single_bot = (cls.repo / "docs" / "ORION_SINGLE_BOT_ORCHESTRATION.md").read_text(
            encoding="utf-8"
        )
        cls.follow_through = (cls.repo / "docs" / "FOLLOW_THROUGH.md").read_text(
            encoding="utf-8"
        )
        cls.pdf_workflow = (cls.repo / "docs" / "PDF_REVIEW_WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        cls.makefile = (cls.repo / "Makefile").read_text(encoding="utf-8")
        cls.discord_setup = (cls.repo / "docs" / "DISCORD_SETUP.md").read_text(encoding="utf-8")
        cls.nvim = (cls.repo / "docs" / "NVIDIA_BUILD_KIMI.md").read_text(encoding="utf-8")
        cls.provider_matrix = (cls.repo / "docs" / "LLM_PROVIDER_MATRIX.md").read_text(
            encoding="utf-8"
        )
        cls.scripts_readme = (cls.repo / "scripts" / "README.md").read_text(encoding="utf-8")
        cls.polaris_inbox = (cls.repo / "tasks" / "INBOX" / "POLARIS.md").read_text(encoding="utf-8")
        cls.compat_0114 = (cls.repo / "docs" / "CODEX_0114_COMPATIBILITY_REPORT.md").read_text(
            encoding="utf-8"
        )

    def test_examples_pin_tools_profile(self):
        self.assertEqual(self.json_example["tools"]["profile"], "coding")
        self.assertIn("profile: coding", self.yaml_example)

    def test_examples_enable_assistant_hooks_and_memory_slot(self):
        self.assertEqual(
            self.json_example["hooks"]["internal"]["enabled"],
            ["session-memory", "command-logger"],
        )
        self.assertEqual(self.json_example["plugins"]["slots"]["memory"], "memory-lancedb")
        self.assertTrue(self.json_example["plugins"]["entries"]["open-prose"]["enabled"])
        self.assertTrue(self.json_example["plugins"]["entries"]["memory-lancedb"]["enabled"])
        self.assertFalse(self.json_example["plugins"]["entries"]["memory-core"]["enabled"])
        dreaming = self.json_example["plugins"]["entries"]["memory-core"]["config"]["dreaming"]
        self.assertFalse(dreaming["enabled"])
        self.assertEqual(dreaming["frequency"], "0 3 * * *")
        self.assertEqual(
            self.json_example["agents"]["list"][0]["memorySearch"]["sources"],
            ["memory", "sessions"],
        )
        embedding = self.json_example["plugins"]["entries"]["memory-lancedb"]["config"]["embedding"]
        self.assertEqual(embedding["apiKey"], "${OPENROUTER_API_KEY}")
        self.assertEqual(embedding["baseUrl"], "https://openrouter.ai/api/v1")
        self.assertEqual(embedding["model"], "text-embedding-3-small")
        self.assertIn("session-memory", self.yaml_example)
        self.assertIn("command-logger", self.yaml_example)
        self.assertIn("memory: memory-lancedb", self.yaml_example)
        self.assertIn("memory-core:", self.yaml_example)
        self.assertIn('frequency: "0 3 * * *"', self.yaml_example)
        self.assertIn("sources:\n          - memory\n          - sessions", self.yaml_example)
        self.assertIn("apiKey: ${OPENROUTER_API_KEY}", self.yaml_example)
        self.assertIn("baseUrl: https://openrouter.ai/api/v1", self.yaml_example)
        self.assertIn("model: text-embedding-3-small", self.yaml_example)

    def test_examples_default_to_openai_gpt_54(self):
        model_defaults = self.json_example["agents"]["defaults"]["model"]
        self.assertEqual(model_defaults["primary"], "openai/gpt-5.4")
        self.assertIn("openrouter/openrouter/free", model_defaults["fallbacks"])
        self.assertIn("minimax/MiniMax-M2.7-highspeed", model_defaults["fallbacks"])
        self.assertIn("openai/gpt-5.4", self.readme)
        self.assertIn("primary: openai/gpt-5.4", self.yaml_example)

    def test_examples_include_cooldowns_codex_search_and_exec_approvals(self):
        cooldowns = self.json_example["auth"]["cooldowns"]
        self.assertEqual(cooldowns["failureWindowHours"], 12)
        self.assertEqual(cooldowns["overloadedProfileRotations"], 0)
        self.assertEqual(cooldowns["overloadedBackoffMs"], 45000)

        codex_search = self.json_example["tools"]["web"]["search"]["openaiCodex"]
        self.assertTrue(codex_search["enabled"])
        self.assertEqual(codex_search["mode"], "cached")
        self.assertEqual(codex_search["contextSize"], "high")
        self.assertEqual(codex_search["userLocation"]["timezone"], "America/New_York")

        self.assertTrue(self.json_example["channels"]["telegram"]["execApprovals"]["enabled"])
        self.assertTrue(self.json_example["channels"]["discord"]["execApprovals"]["enabled"])
        self.assertIn("overloadedBackoffMs: 45000", self.yaml_example)
        self.assertIn("openaiCodex:", self.yaml_example)
        self.assertIn("execApprovals:", self.yaml_example)

    def test_examples_show_targeted_cross_agent_memory(self):
        main_agent = self.json_example["agents"]["list"][0]
        collections = main_agent["memorySearch"]["qmd"]["extraCollections"]
        self.assertEqual([item["name"] for item in collections], ["ledger", "polaris"])
        ember_agent = next(agent for agent in self.json_example["agents"]["list"] if agent["id"] == "ember")
        self.assertEqual(ember_agent["model"]["primary"], "nvidia-build/moonshotai/kimi-k2.5")
        self.assertIn("extraCollections:", self.yaml_example)
        self.assertIn("name: ledger", self.yaml_example)
        self.assertIn("name: polaris", self.yaml_example)
        self.assertIn("- id: ember", self.yaml_example)

    def test_provider_matrix_keeps_kimi_specialized(self):
        self.assertIn("kimi-specialist", self.provider_matrix)
        self.assertIn("explicit specialist lane", self.provider_matrix)
        self.assertIn("Keep it out of hot-path production fallback chains", self.provider_matrix)

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
        for text in (self.readme, self.workflow, self.recovery, self.migration):
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
        self.assertIn("channels.discord.execApprovals.enabled true", self.discord_setup)
        self.assertIn("SecretRef", self.nvim)
        self.assertIn("SecretRef", self.migration)
        self.assertIn("${OPENROUTER_API_KEY}", self.migration)
        self.assertIn("openai/text-embedding-3-small", self.migration)

    def test_assistant_docs_are_wired(self):
        self.assertIn("/today", self.readme)
        self.assertIn("/capture", self.readme)
        self.assertIn("POLARIS", self.assistant_workflows)
        self.assertIn("assistant-agenda.md", self.workflow)
        self.assertIn("orion_error_db.py", self.error_review)
        self.assertIn("session_maintenance.py", self.error_review)
        self.assertIn("error-review.md", self.readme)
        self.assertIn("session-maintenance.md", self.readme)
        self.assertIn("OPENCLAW_MEMORY_DREAMING_PILOT.md", self.readme)
        self.assertIn("make operator-health-bundle", self.readme)
        self.assertIn("POLARIS", self.single_bot)
        self.assertIn("Notify: telegram", self.polaris_inbox)
        self.assertIn("OpenClaw 2026.4.5", self.readme)
        self.assertIn("ORION_RUNTIME_BASELINE_2026_04_07.md", self.readme)
        self.assertIn("sessions_yield", self.upgrade_notes)
        self.assertIn("isolated cron", self.upgrade_notes)
        self.assertIn("cross-agent workspace", self.upgrade_notes)

    def test_live_docs_use_src_workspace_path(self):
        live_texts = (
            self.readme,
            self.workflow,
            self.migration,
            self.error_review,
            self.upgrade_notes,
            self.single_bot,
            self.follow_through,
            self.polaris_inbox,
        )
        for text in live_texts:
            self.assertNotIn("/Users/corystoner/Desktop/ORION", text)

        self.assertEqual(self.json_example["agents"]["defaults"]["workspace"], "/Users/corystoner/src/ORION")
        self.assertIn("/Users/corystoner/src/ORION", self.migration)
        self.assertIn("/Users/corystoner/src/ORION", self.single_bot)
        self.assertIn("/Users/corystoner/src/ORION", self.follow_through)
        self.assertIn("/Users/corystoner/src/ORION", self.polaris_inbox)
        self.assertIn("/Users/corystoner/src/ORION", self.error_review)

    def test_miniapp_workspace_surfaces_are_removed(self):
        removed_paths = [
            self.repo / "app",
            self.repo / "apps" / "telegram-miniapp-dashboard",
            self.repo / "src" / "plugins" / "telegram" / "miniapp",
            self.repo / "fly.orion-core.toml",
        ]
        for path in removed_paths:
            self.assertFalse(path.exists(), f"miniapp surface should stay removed: {path}")

    def test_codex_0114_report_locks_permission_plugin_and_health_defaults(self):
        for needle in ("request_permissions", "@plugin", "/readyz", "/healthz", "workspace-write"):
            self.assertIn(needle, self.compat_0114)


if __name__ == "__main__":
    unittest.main()
