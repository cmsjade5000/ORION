# Top-level workflow runner
.PHONY: soul restart routingsim routing-regression-live routing-regression-live-tools routing-regression-live-dry-run eval-routing eval-routing-tools eval-compare eval-run eval-reliability eval-reliability-daily monthly-scorecard route-hygiene lane-hotspots stop-gate-enforce canary-health-check canary-stage skill-discovery assistant-skill-refresh firecrawl-wire-pilot acpx-pilot acpx-smoke github-workflow-pilot assistant-agenda-refresh incident-bundle error-review session-maintenance dreaming-preview dreaming-status dreaming-help dreaming-on dreaming-off operator-health-bundle party-batch-once inbox-cycle task-loop task-loop-heartbeat task-loop-weekly looptest avatar audio-check lint dev config-validate openclaw-compat toolset-audit task-packets plan-graph test shellcheck redteam-validate redteam-gate mcp-harness-smoke policy-gate-check orion-policy-check policy-scorecard secure-preflight-check supply-chain-check llm-vuln-probe-check langfuse-bootstrap-check mcp-schema-check llm-provider-bench llm-provider-bench-dry llm-provider-configure-dry skill-guards-smoke ci

PROMPTFOO_CONFIG ?= config/promptfoo/orion-safety-gate.yaml
THINKING ?= high

## Regenerate all agent SOUL.md files
soul:
	./scripts/soul_factory.sh --all

## Restart the OpenClaw gateway service
restart:
	openclaw gateway restart

## Run the routing simulation scoring exercise
routingsim:
	@$(MAKE) eval-run

## Opt-in live routing regression gate (requires local OpenClaw runtime)
routing-regression-live:
	@python3 scripts/run_routing_regression_gate.py --repo-root .

## Opt-in live routing regression gate including tools prompts 11+
routing-regression-live-tools:
	@python3 scripts/run_routing_regression_gate.py --repo-root . --tools-prompts-md docs/routing_sim_tools.md

## Show live routing regression preflight + planned commands without running them
routing-regression-live-dry-run:
	@python3 scripts/run_routing_regression_gate.py --repo-root . --dry-run

## Run routing eval and persist timestamped history + latest report
eval-routing:
	@ORION_SUPPRESS_TELEGRAM=1 TELEGRAM_SUPPRESS=1 ORION_SUPPRESS_DISCORD=1 DISCORD_SUPPRESS=1 NOTIFY_DRY_RUN=1 \
		python3 scripts/loop_test_routing_sim.py \
		--repo-root . \
		--thinking "$(THINKING)" \
		--out-dir eval/history \
		--latest-path eval/latest_report.json

## Run routing eval with Codex tools extension prompts (11+)
eval-routing-tools:
	@ORION_SUPPRESS_TELEGRAM=1 TELEGRAM_SUPPRESS=1 ORION_SUPPRESS_DISCORD=1 DISCORD_SUPPRESS=1 NOTIFY_DRY_RUN=1 \
		python3 scripts/loop_test_routing_sim.py \
		--repo-root . \
		--thinking "$(THINKING)" \
		--out-dir eval/history \
		--latest-path eval/latest_report_tools.json \
		--tools-prompts-md docs/routing_sim_tools.md

## Alias for compatibility with docs
eval-run:
	@$(MAKE) eval-routing
	@$(MAKE) eval-compare

## Compare baseline vs latest eval and enforce regression gate
eval-compare:
	@python3 scripts/eval_compare.py \
		--baseline "$${BASE:-eval/history/baseline-2026-03.json}" \
		--current "$${AFTER:-eval/latest_report.json}" \
		--output-json eval/latest_compare.json \
		--output-md eval/scorecard.md

## Collect 24h runtime reliability snapshot artifacts
eval-reliability:
	@python3 scripts/collect_reliability_snapshot.py --hours 24

## Collect reliability snapshot and append daily row to monthly scorecard
eval-reliability-daily:
	@$(MAKE) eval-reliability
	@python3 scripts/reliability_daily_update.py \
		--scorecard eval/monthly-scorecard-2026-03.md \
		--history-dir eval/history

## Regenerate monthly scorecard from eval/canary artifacts
monthly-scorecard:
	@python3 scripts/monthly_scorecard_refresh.py --month "$${MONTH:-2026-03}"

## Run route hygiene guard with safe autofix enabled
route-hygiene:
	@python3 scripts/route_hygiene_guard.py --apply

## Detect lane-wait hot windows and correlate nearby cron jobs
lane-hotspots:
	@python3 scripts/lane_wait_hot_windows.py \
		--hours "$${HOURS:-24}" \
		--top "$${TOP:-10}" \
		--bucket-minutes "$${BUCKET_MINUTES:-1}" \
		--correlation-window-seconds "$${CORR_WINDOW_SECONDS:-90}"

## Enforce stop gate: disable canary/promotion jobs after consecutive R1/R2 failures
stop-gate-enforce:
	@python3 scripts/stop_gate_enforcer.py \
		--history-dir eval/history \
		--consecutive-days "$${MIN_FAIL_DAYS:-2}" \
		--max-lane-wait-count "$${MAX_LANE_WAIT_COUNT:-6}" \
		--max-lane-wait-p95-ms "$${MAX_LANE_WAIT_P95_MS:-10000}" \
		--include-name-patterns "$${STOP_GATE_INCLUDE:-party-batch,canary-rollout,canary-promote,canary-promotion}" \
		--exclude-name-patterns "$${STOP_GATE_EXCLUDE:-route-hygiene,lane-hotspots,reliability,scorecard,skill-discovery}" \
		--apply

## Append automated canary health signal row
canary-health-check:
	@python3 scripts/canary_health_check.py \
		--candidate openprose-workflow-2026-03 \
		--scorecard docs/skills/canary-results-2026-03.md \
		--history-dir eval/history \
		--compare eval/latest_compare.json

## One-shot staged canary harness (pre/post eval + stage + side-effect checks)
canary-stage:
	@if [ -z "$(strip $(CANDIDATE))" ]; then echo "CANDIDATE is required"; exit 2; fi
	@if [ -z "$(strip $(STAGE_CMD))" ]; then echo "STAGE_CMD is required"; exit 2; fi
	@python3 scripts/canary_stage_harness.py \
		--candidate "$(CANDIDATE)" \
		--repo-root . \
		--stage-cmd "$(STAGE_CMD)" \
		$(if $(strip $(ROLLBACK_CMD)),--rollback-cmd "$(ROLLBACK_CMD)",) \
		$(HARNESS_ARGS)

## Run online skill discovery scan and update weekly shortlist generated section
skill-discovery:
	@python3 scripts/skill_discovery_scan.py \
		--limit "$${LIMIT:-8}" \
		--update-shortlist

## Build the monthly ClawHub skill review artifact and print the update command
assistant-skill-refresh:
	@bash scripts/assistant_skill_refresh.sh

## Build the read-only Firecrawl pilot artifact for WIRE
firecrawl-wire-pilot:
	@python3 scripts/firecrawl_wire_pilot.py \
		--output-json tmp/firecrawl_wire_pilot_latest.json \
		--output-md tmp/firecrawl_wire_pilot_latest.md

## Build the read-only ACPX pilot artifact for ATLAS
acpx-pilot:
	@python3 scripts/acpx_pilot_check.py \
		--output-json tmp/acpx_pilot_latest.json \
		--output-md tmp/acpx_pilot_latest.md

## Verify the bounded ACPX live path without mutating runtime state
acpx-smoke:
	@python3 scripts/acpx_runtime_smoke.py \
		--output-json tmp/acpx_runtime_smoke_latest.json \
		--output-md tmp/acpx_runtime_smoke_latest.md

## Build the read-only GitHub structured workflow pilot artifact
github-workflow-pilot:
	@python3 scripts/github_structured_workflow_pilot.py \
		--output-json tmp/github_structured_workflow_pilot_latest.json \
		--output-md tmp/github_structured_workflow_pilot_latest.md

## Refresh the generated assistant agenda artifact
assistant-agenda-refresh:
	@python3 scripts/assistant_status.py --cmd refresh --json

## Build a read-only ORION ops incident bundle for review
incident-bundle:
	@python3 scripts/orion_incident_bundle.py --repo-root . --write-latest --json

## Review recurring ORION errors and refresh the nightly report
error-review:
	@python3 scripts/orion_error_db.py --repo-root . review --window-hours "$${WINDOW_HOURS:-24}" --json

## Preview deliberate session-store maintenance and write a report
session-maintenance:
	@python3 scripts/session_maintenance.py --repo-root . --agent "$${AGENT_ID:-main}" --fix-missing --json

## Non-destructive OpenClaw memory/dreaming readiness preview
dreaming-preview:
	@python3 scripts/openclaw_memory_dreaming_preview.py \
		--limit "$${LIMIT:-10}" \
		--output-json tmp/openclaw_memory_dreaming_preview_latest.json \
		--output-md tmp/openclaw_memory_dreaming_preview_latest.md

## Deterministic direct-turn dreaming status via guarded wrapper
dreaming-status:
	@python3 scripts/openclaw_guarded_turn.py \
		--repo-root . \
		--agent "$${AGENT_ID:-main}" \
		--runtime-channel "$${RUNTIME_CHANNEL:-local}" \
		--message "/dreaming status" \
		--policy-mode "$${POLICY_MODE:-audit}" \
		--rules "$${POLICY_RULES:-config/orion_policy_rules.json}"

## Deterministic direct-turn dreaming help via guarded wrapper
dreaming-help:
	@python3 scripts/openclaw_guarded_turn.py \
		--repo-root . \
		--agent "$${AGENT_ID:-main}" \
		--runtime-channel "$${RUNTIME_CHANNEL:-local}" \
		--message "/dreaming help" \
		--policy-mode "$${POLICY_MODE:-audit}" \
		--rules "$${POLICY_RULES:-config/orion_policy_rules.json}"

## Deterministic direct-turn dreaming enable via guarded wrapper
dreaming-on:
	@python3 scripts/openclaw_guarded_turn.py \
		--repo-root . \
		--agent "$${AGENT_ID:-main}" \
		--runtime-channel "$${RUNTIME_CHANNEL:-local}" \
		--message "/dreaming on" \
		--policy-mode "$${POLICY_MODE:-audit}" \
		--rules "$${POLICY_RULES:-config/orion_policy_rules.json}"

## Deterministic direct-turn dreaming disable via guarded wrapper
dreaming-off:
	@python3 scripts/openclaw_guarded_turn.py \
		--repo-root . \
		--agent "$${AGENT_ID:-main}" \
		--runtime-channel "$${RUNTIME_CHANNEL:-local}" \
		--message "/dreaming off" \
		--policy-mode "$${POLICY_MODE:-audit}" \
		--rules "$${POLICY_RULES:-config/orion_policy_rules.json}"

## Standard operator health bundle for gateway, models, memory, REM, and smoke checks
operator-health-bundle:
	@python3 scripts/openclaw_operator_health_bundle.py \
		--probe-max-tokens "$${PROBE_MAX_TOKENS:-16}" \
		--thinking "$${THINKING:-low}" \
		--timeout "$${TIMEOUT:-120}" \
		--output-json tmp/openclaw_operator_health_bundle_latest.json \
		--output-md tmp/openclaw_operator_health_bundle_latest.md \
		--json

## One-shot coding-party batch (eval + reliability + canary health)
party-batch-once:
	@python3 scripts/party_batch_once.py --repo-root .

## Canonical inbox execution/reconcile/notify loop
inbox-cycle:
	@python3 scripts/inbox_cycle.py --repo-root . --runner-max-packets "$${RUNNER_MAX_PACKETS:-4}" --stale-hours "$${STALE_HOURS:-24}" --notify-max-per-run "$${NOTIFY_MAX_PER_RUN:-8}"

## Diagnostic reconcile for packet/ticket lanes; scheduled core automation should use inbox-cycle
task-loop:
	@python3 scripts/task_execution_loop.py --repo-root . --apply --stale-hours "$${STALE_HOURS:-24}"

## Heartbeat-grade enforcement (non-zero exit when stale pending packets exist)
task-loop-heartbeat:
	@python3 scripts/task_execution_loop.py --repo-root . --apply --strict-stale --stale-hours "$${STALE_HOURS:-24}"

## Weekly hygiene reconcile (longer threshold by default)
task-loop-weekly:
	@python3 scripts/task_execution_loop.py --repo-root . --apply --stale-hours "$${STALE_HOURS:-72}"

## Internal loop testing (no Telegram delivery); writes report to tmp/looptests/
looptest:
	@ORION_SUPPRESS_TELEGRAM=1 TELEGRAM_SUPPRESS=1 ORION_SUPPRESS_DISCORD=1 DISCORD_SUPPRESS=1 NOTIFY_DRY_RUN=1 \
		python3 scripts/loop_test_routing_sim.py

## Preview your agent avatar (as specified in IDENTITY.md)
avatar:
	@echo "See IDENTITY.md for your Avatar setting"
	@echo "Open the avatar image file to preview your agent's avatar"

## Test audio output (TTS)
audio-check:
	@echo "Testing audio output (ElevenLabs)..."
	@node skills/elevenlabs-tts/cli.js audio-check

## Run lint checks (pre-commit hooks)
lint:
	@command -v pre-commit >/dev/null 2>&1 && pre-commit run --all-files || echo "pre-commit not installed, skipping lint"

## Start the OpenClaw gateway service (LaunchAgent)
dev:
	openclaw gateway start

## Validate the live OpenClaw runtime config when available
config-validate:
	@bash scripts/openclaw_config_validate.sh

## Validate required OpenClaw CLI surface with compatibility fallbacks
openclaw-compat:
	@bash scripts/openclaw_cli_compat_check.sh

## Audit local ORION runtime/tool adoption posture and write refreshable artifacts
toolset-audit:
	@python3 scripts/orion_toolset_audit.py \
		--output-json tmp/orion_toolset_audit_latest.json \
		--output-md tmp/orion_toolset_audit_latest.md

## Validate Task Packets in per-agent inbox files
task-packets:
	python3 scripts/validate_task_packets.py

## Validate markdown plan dependency graphs (T# + depends_on)
plan-graph:
	python3 scripts/validate_plan_graph.py

## Run unit tests + Task Packet validation
test:
	npm test

## Shell lint (bash scripts)
shellcheck:
	./scripts/ci_shellcheck.sh

## Validate promptfoo config only (no eval/model calls)
redteam-validate:
	@npx -y promptfoo@latest validate config -c "$(PROMPTFOO_CONFIG)"

## Run redteam gate harness (requires OPENAI_API_KEY)
redteam-gate:
	@if [ -z "$${OPENAI_API_KEY:-}" ]; then echo "OPENAI_API_KEY is required for redteam-gate"; exit 2; fi
	@bash skills/llm-redteam-gate/scripts/run_redteam_gate.sh -c "$(PROMPTFOO_CONFIG)"

## Install MCP package and run integration smoke harness
mcp-harness-smoke:
	@set -e; \
	PYTHON_BIN=python3; \
	if ! $$PYTHON_BIN -c "import mcp" >/dev/null 2>&1; then \
		if [ -x .venv/bin/python ]; then \
			PYTHON_BIN=.venv/bin/python; \
		fi; \
		$$PYTHON_BIN -m pip install --upgrade mcp; \
	fi; \
	bash skills/mcp-integration-harness/scripts/run_mcp_harness.sh --python "$$PYTHON_BIN"

## Run Conftest policy gate against the passing example packet (requires conftest)
policy-gate-check:
	@bash skills/policy-gate-conftest/scripts/run_policy_gate.sh \
		skills/policy-gate-conftest/examples/task_packet.pass.json

## Run ORION runtime policy gate regression tests
orion-policy-check:
	@set -e; \
	PYTHON_BIN=python3; \
	if [ -x .venv/bin/python ]; then \
		PYTHON_BIN=.venv/bin/python; \
	fi; \
	$$PYTHON_BIN -m pytest -q tests/test_orion_policy_gate.py tests/test_orion_policy_scorecard.py tests/test_openclaw_guarded_turn.py tests/test_notify_inbox_results.py

## Build ORION runtime policy scorecard + staged promotion recommendations
policy-scorecard:
	@python3 scripts/orion_policy_scorecard.py --history-dir eval/history --window-days "$${WINDOW_DAYS:-7}" --min-clean-days "$${MIN_CLEAN_DAYS:-7}" --max-false-positives "$${MAX_FALSE_POSITIVES:-0}"

## Run Semgrep preflight check (requires semgrep)
secure-preflight-check:
	@bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh

## Run supply chain gate in dry-run mode (dependency-safe preview)
supply-chain-check:
	@bash skills/supply-chain-verify-scan/scripts/run_supply_chain_gate.sh \
		--dry-run \
		--target alpine:latest \
		--skip-cosign \
		--skip-grype

## Run garak probe in dry-run mode (dependency-safe preview)
llm-vuln-probe-check:
	@bash skills/llm-vuln-probe/scripts/run_garak_probe.sh --dry-run

## Scaffold Langfuse bootstrap artifacts in dry-run mode
langfuse-bootstrap-check:
	@bash skills/langfuse-trace-eval-bootstrap/scripts/bootstrap_langfuse_trace_eval.sh --dry-run

## Dry-run OpenClaw provider wiring for OpenAI-first Kimi/local fallback lanes
llm-provider-configure-dry:
	@bash scripts/openclaw_configure_llm_providers.sh --dry-run

## Dry-run provider benchmark matrix with tracing hooks
llm-provider-bench-dry:
	@python3 scripts/run_llm_provider_benchmarks.py --dry-run --trace

## Run provider benchmark matrix and emit report
llm-provider-bench:
	@python3 scripts/run_llm_provider_benchmarks.py --trace

## Check provider readiness before a live benchmark
llm-provider-readiness:
	@python3 scripts/run_llm_provider_benchmarks.py --check-readiness

## Fail-fast OpenAI control-lane readiness check
llm-provider-openai-ready:
	@python3 scripts/run_llm_provider_benchmarks.py --check-readiness --require-ready --providers openai-control-plane

## Run hosted live benchmark suite (OpenAI + OpenRouter + Kimi)
llm-provider-bench-full-live:
	@python3 scripts/run_llm_provider_benchmarks.py --providers openai-control-plane,openrouter-auto-primary,kimi-k2-5-nvidia-build --trace

## Run targeted OpenAI control-lane benchmarks
llm-provider-bench-openai:
	@python3 scripts/run_llm_provider_benchmarks.py --providers openai-control-plane --tasks structured_output_validation,evals_and_trace_grading --trace

## Validate MCP schema compliance using repo venv when available
mcp-schema-check:
	@set -e; \
	PYTHON_BIN=python3; \
	if [ -x .venv/bin/python ]; then \
		PYTHON_BIN=.venv/bin/python; \
	fi; \
	bash skills/mcp-schema-compliance-check/scripts/run_mcp_schema_check.sh --python "$$PYTHON_BIN"

## Dependency-safe smoke checks for all new skill wrappers
skill-guards-smoke:
	@bash skills/policy-gate-conftest/scripts/run_policy_gate.sh --help >/dev/null
	@$(MAKE) supply-chain-check
	@$(MAKE) llm-vuln-probe-check
	@$(MAKE) langfuse-bootstrap-check
	@bash skills/mcp-schema-compliance-check/scripts/run_mcp_schema_check.sh --dry-run >/dev/null
	@bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh --dry-run >/dev/null

## Must-pass CI gate (lint + tests + plan + task packet validation)
ci: config-validate openclaw-compat shellcheck test plan-graph task-packets orion-policy-check policy-gate-check
