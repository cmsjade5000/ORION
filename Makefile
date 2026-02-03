# Top-level workflow runner
.PHONY: soul restart routingsim avatar audio-check lint dev

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
	@echo "Testing audio output..."
	@echo "This is a test of the audio system"
	@# Replace this with your preferred TTS or audio test command

## Run lint checks (pre-commit hooks)
lint:
	pre-commit run --all-files

## Start the OpenClaw gateway in development mode
dev:
	openclaw gateway start
