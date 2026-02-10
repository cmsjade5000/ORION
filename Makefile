# Top-level workflow runner
.PHONY: soul restart routingsim avatar audio-check lint dev task-packets

## Regenerate all agent SOUL.md files
soul:
	./scripts/soul_factory.sh --all

## Restart the OpenClaw gateway service
restart:
	openclaw gateway restart

## Run the routing simulation scoring exercise
routingsim:
	@echo "See docs/routing_sim.md for routing simulation instructions"

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
