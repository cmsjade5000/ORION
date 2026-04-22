# Primeta Avatar Layer

Status: optional integration surface  
Scope: Primeta as an ORION presentation layer, not a core routing dependency

## Summary

Primeta gives ORION a browser-based avatar layer through a hosted MCP endpoint:

- endpoint: `https://primeta.ai/mcp`
- auth: OAuth 2.0 in browser
- role in ORION: voice/avatar presentation only

Keep the boundary sharp:

- ORION remains the only user-facing ingress.
- Telegram and current TTS flows remain first-class.
- Task Packets, routing, and specialist ownership do not move into Primeta.
- If Primeta is unavailable, ORION should still behave normally.

Reference docs:

- https://primeta.ai/docs/mcp
- https://primeta.ai/mcp

## Integration Shape

Dependency graph:

- `T1` depends_on: `[]`
  Define the boundary: Primeta is presentation-only.
- `T2` depends_on: `[T1]`
  Register Primeta in `config/mcporter.json`.
- `T3` depends_on: `[T2]`
  Add a small wrapper for auth, status, connect, persona, hook-config, and send.
- `T4` depends_on: `[T3]`
  Use it for optional ORION spoken summaries or coding-event reactions.

## Why This Shape

ORION already has working voice output through ElevenLabs and Telegram delivery flows. Primeta adds a different layer:

- animated avatar presence
- browser-hosted speech and reactions
- persona switching
- event hook configuration for coding reactions

That means Primeta should complement existing delivery, not replace it.

## Current Repo Surface

- `config/mcporter.json` includes the named MCP server entry `primeta`.
- `scripts/primeta_avatar.py` is the thin wrapper for common Primeta actions.
- existing voice fallback remains `skills/elevenlabs-tts/` and `scripts/morning_debrief_voice_send.sh`

## Setup

Authenticate once:

```bash
python3 scripts/primeta_avatar.py auth
```

This opens Primeta's OAuth flow through `mcporter`.

## Common Commands

Check connection state:

```bash
python3 scripts/primeta_avatar.py status --json
```

Connect a session:

```bash
python3 scripts/primeta_avatar.py connect --connection-name orion
```

List personas:

```bash
python3 scripts/primeta_avatar.py list-personas --json
```

Switch persona:

```bash
python3 scripts/primeta_avatar.py set-persona --persona-id 42
```

Send text to the avatar:

```bash
python3 scripts/primeta_avatar.py send --text "[friendly] ORION finished the pass and left the repo clean."
```

Get hook config:

```bash
python3 scripts/primeta_avatar.py hook-config --json
```

## Recommended Usage

Good fits:

- post-task spoken summaries
- explicit "say that through the avatar" flows
- operator-visible coding reactions in a browser tab

Bad fits:

- replacing Telegram as ORION's default delivery path
- hiding core status inside Primeta-only UX
- making auth to an external avatar service a requirement for routine ORION work

## Operator Notes

- `mcporter` defaults to `config/mcporter.json` in this repo.
- For ad-hoc use without the named server entry, pass `--server-ref https://primeta.ai/mcp`.
- Treat OAuth profiles and cached auth state as secrets per `KEEP.md`.
