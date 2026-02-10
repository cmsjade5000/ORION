---
name: elevenlabs-tts
description: Generate Telegram-sendable TTS audio using ElevenLabs and return a MEDIA: path.
homepage: https://elevenlabs.io/docs/api-reference/introduction
metadata:
  invocation: user
  openclaw:
    emoji: "\U0001F3A4"
    # This skill supports file-backed secrets (recommended), so we do not
    # hard-require an env var. If no key is available at runtime, the skill
    # will error with a clear message.
---

# ElevenLabs TTS

Generate a speech audio file (default: MP3) from text using ElevenLabs, and print a `MEDIA:/absolute/path.mp3` line so ORION can attach it in Telegram DMs.

Reference: `docs/VOICE_TTS.md`

## Setup (Local Secrets Only)

Provide an API key via either:
- `ELEVENLABS_API_KEY` environment variable, or
- `~/.openclaw/secrets/elevenlabs.api_key` (recommended).

Optional (recommended) default voice selection:
- `ELEVENLABS_DEFAULT_VOICE_ID` or `ELEVENLABS_DEFAULT_VOICE_NAME`
- For persistent defaults in the LaunchAgent gateway, see: `docs/VOICE_TTS.md` (OpenClaw `env.vars`).

Permissions:

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
chmod 600 ~/.openclaw/secrets/elevenlabs.api_key
```

## Quick Test

List voices:

```bash
node skills/elevenlabs-tts/cli.js list-voices
```

Generate audio (prints a `MEDIA:` line):

```bash
node skills/elevenlabs-tts/cli.js speak --text "This is ORION speaking." --voice-name "Rachel"
```

## Speaking Presets

`--preset` maps to conservative voice settings (you can tune later):
- `calm`: steadier, gentler
- `narration`: balanced, clear
- `energetic`: more animated
- `urgent`: crisp and high-attention

Example:

```bash
node skills/elevenlabs-tts/cli.js speak --text "Take one slow breath." --voice-name "Rachel" --preset calm
```

Smoke check:

```bash
make audio-check
```
