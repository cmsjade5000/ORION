# Voice / TTS (ElevenLabs)

This repo supports generating **Telegram DM audio attachments** for ORION using ElevenLabs TTS.

## Primary Pieces

- Skill: `skills/elevenlabs-tts/`
  - Creates an MP3 under `tmp/elevenlabs-tts/`
  - Prints a `MEDIA:/absolute/path.mp3` line (OpenClaw Telegram attachment contract)
- ORION guidance: `src/agents/ORION.md`
- Supportive audio routing: `src/core/shared/ROUTING.md`
- Supportive script generation: `src/agents/EMBER.md`

## Secrets (Do Not Commit)

Store the API key locally (recommended):
- `~/.openclaw/secrets/elevenlabs.api_key` (chmod 600)

Or via env var:
- `ELEVENLABS_API_KEY`

Do not paste keys into chat, tasks, or commit history. Rotate immediately if exposed.

## Quick Tests

Verify the key works (should return HTTP 200):

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "xi-api-key: $(tr -d '\r\n' < ~/.openclaw/secrets/elevenlabs.api_key)" \
  -H 'Accept: application/json' \
  https://api.elevenlabs.io/v1/voices
```

Generate a short audio clip (prints a `MEDIA:` line on success):

```bash
make audio-check
```

List voices:

```bash
node skills/elevenlabs-tts/cli.js list-voices
```

## Default Voice (Recommended)

To avoid specifying a voice every time, set one of:
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `ELEVENLABS_DEFAULT_VOICE_NAME`

If no default is configured and no voice is specified, the skill falls back to the first available voice on the account.

### Persist Defaults For The Gateway Service (Recommended)

Because the gateway runs as a LaunchAgent, your shell env vars may not carry over reliably. The most reliable way to persist non-secret defaults is `~/.openclaw/openclaw.json`:

- `env.vars.ELEVENLABS_DEFAULT_VOICE_ID`
- `env.vars.ELEVENLABS_DEFAULT_PRESET` (optional)

Helper script:

```bash
./scripts/elevenlabs_set_default_voice.sh --voice-name "River" --preset narration
openclaw gateway restart
```

## Speaking Presets

The `--preset` flag maps to conservative voice settings:
- `calm`
- `narration`
- `energetic`
- `urgent`

Example:

```bash
node skills/elevenlabs-tts/cli.js speak --text "Take one slow breath." --preset calm
```

## Optional Control Tags (Inline Directives)

If you want to control the voice memo style without CLI flags, you can:
- Put a single directive on the **first non-empty line**, or
- Use **multiple directives throughout** the script to change style by section (each directive starts a new segment).

Shorthand preset:

```text
#urgent
AEGIS alert. Simulated. Please check status.
```

Extra shorthand aliases (mapped onto the same 4 presets):
- `#normal` / `#default` -> defer to configured defaults
- `#narrative` / `#story` -> `narration`
- `#warm`, `#supportive`, `#soothe` -> `calm`
- `#brief`, `#update`, `#focus` -> `narration`
- `#hype`, `#excited` -> `energetic`
- `#alert`, `#critical` -> `urgent`

Multi-part example (single MP3 output):

```text
#normal
Good morning Cory. Quick update.

#urgent
Weather: severe winds expected this afternoon. Please be cautious.

#narrative
Top news: ...
```

Bracket shorthand:

```text
[calm]
Let’s take one slow breath, then pick one next step.
```

Key/value form:

```text
[tts preset=urgent]
AEGIS alert. Simulated. Please check status.
```

Supported keys: `preset`, `voice_id`, `voice_name` (also accepts `voice` as alias for `voice_name`).

## Supportive / Calming Audio: Intended Flow

When Cory asks to *hear ORION speak* in a calming/supportive/grounding way:

1. **EMBER** produces a short spoken-friendly script + a suggested `TTS_PRESET`.
2. **ORION** runs TTS via `skills/elevenlabs-tts` and attaches the resulting MP3 in Telegram.

Safety gate:
- If crisis/self-harm intent is present, prioritize safety guidance. Do not treat “soothing audio” as a substitute for safety steps.

## Morning Brief Voice

Daily voice recap via Telegram:
- `docs/MORNING_DEBRIEF_VOICE.md`
