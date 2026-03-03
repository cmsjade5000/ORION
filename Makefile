# Top-level workflow runner
.PHONY: soul restart routingsim eval-routing eval-compare eval-run eval-reliability eval-reliability-daily monthly-scorecard route-hygiene lane-hotspots stop-gate-enforce canary-health-check canary-stage skill-discovery party-batch-once looptest avatar audio-check lint dev task-packets plan-graph test shellcheck ci

## Regenerate all agent SOUL.md files
soul:
	./scripts/soul_factory.sh --all

## Restart the OpenClaw gateway service
restart:
	openclaw gateway restart

## Run the routing simulation scoring exercise
routingsim:
	@$(MAKE) eval-run

## Run routing eval and persist timestamped history + latest report
eval-routing:
	@ORION_SUPPRESS_TELEGRAM=1 TELEGRAM_SUPPRESS=1 ORION_SUPPRESS_DISCORD=1 DISCORD_SUPPRESS=1 NOTIFY_DRY_RUN=1 \
		python3 scripts/loop_test_routing_sim.py \
		--repo-root . \
		--out-dir eval/history \
		--latest-path eval/latest_report.json

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

## One-shot coding-party batch (eval + reliability + canary health)
party-batch-once:
	@python3 scripts/party_batch_once.py --repo-root .

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

## Must-pass CI gate (lint + tests + plan + task packet validation)
ci: shellcheck test plan-graph task-packets
