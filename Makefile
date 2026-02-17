# Top-level workflow runner
.PHONY: soul restart routingsim looptest avatar audio-check lint dev task-packets plan-graph test shellcheck ci

## Regenerate all agent SOUL.md files
soul:
	./scripts/soul_factory.sh --all

## Restart the OpenClaw gateway service
restart:
	openclaw gateway restart

## Run the routing simulation scoring exercise
routingsim:
	@echo "See docs/routing_sim.md for routing simulation instructions"

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

## Must-pass CI gate (lint + tests + plan validation)
ci: shellcheck test plan-graph
