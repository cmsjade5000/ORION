#!/usr/bin/env bash
set -euo pipefail

# Set persistent ElevenLabs TTS defaults for the OpenClaw LaunchAgent gateway by
# writing non-secret env vars into ~/.openclaw/openclaw.json (env.vars).
#
# Usage:
#   ./scripts/elevenlabs_set_default_voice.sh --persona orion
#   ./scripts/elevenlabs_set_default_voice.sh --voice-name "River"
#   ./scripts/elevenlabs_set_default_voice.sh --voice-id "SAz9YHcvj6GT2YYXdXww"
#   ./scripts/elevenlabs_set_default_voice.sh --voice-name "River" --preset narration
#
# Notes:
# - This does NOT store the ElevenLabs API key (that stays in ~/.openclaw/secrets/elevenlabs.api_key).
# - Requires: jq, node, and a valid ElevenLabs API key already configured.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

PERSONA=""
VOICE_NAME=""
VOICE_ID=""
PRESET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --persona)
      PERSONA="${2:-}"; shift 2 ;;
    --voice-name)
      VOICE_NAME="${2:-}"; shift 2 ;;
    --voice-id)
      VOICE_ID="${2:-}"; shift 2 ;;
    --preset)
      PRESET="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--persona <name> | --voice-name <name> | --voice-id <id>] [--preset calm|narration|energetic|urgent]" >&2
      exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

if [[ -z "$PERSONA" && -z "$VOICE_ID" && -z "$VOICE_NAME" ]]; then
  echo "Missing --persona, --voice-name, or --voice-id." >&2
  exit 2
fi

if [[ ! -f "$CFG" ]]; then
  echo "OpenClaw config not found: $CFG" >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing dependency: jq" >&2
  exit 2
fi

if [[ -n "$PRESET" ]]; then
  case "$(echo "$PRESET" | tr '[:upper:]' '[:lower:]')" in
    calm|narration|energetic|urgent) ;;
    *)
      echo "Invalid --preset: $PRESET (expected calm|narration|energetic|urgent)" >&2
      exit 2 ;;
  esac
fi

if [[ -n "$PERSONA" ]]; then
  if ! node -e "const m=require('${ROOT_DIR}/skills/elevenlabs-tts/manifest'); m.getVoicePersona(process.argv[1]);" "$PERSONA" >/dev/null 2>&1; then
    echo "Unknown --persona: $PERSONA" >&2
    echo "Available personas:" >&2
    node "$ROOT_DIR/skills/elevenlabs-tts/cli.js" list-personas >&2
    exit 2
  fi
fi

resolve_voice_id() {
  local voice_id="$1"
  local voice_name="$2"
  if [[ -n "$voice_id" ]]; then
    echo "$voice_id"
    return 0
  fi
  node -e "require('${ROOT_DIR}/skills/elevenlabs-tts/manifest').findVoiceIdByName(process.argv[1]).then((id)=>{ if(!id){ process.exit(3);} console.log(id); }).catch((e)=>{ console.error(String(e&&e.message||e)); process.exit(4); });" "$voice_name"
}

VID=""
if [[ -z "$PERSONA" ]]; then
  VID="$(resolve_voice_id "$VOICE_ID" "$VOICE_NAME" || true)"
  if [[ -z "$VID" ]]; then
    echo "Could not resolve voice id for: ${VOICE_NAME:-$VOICE_ID}" >&2
    echo "Try: node skills/elevenlabs-tts/cli.js list-voices" >&2
    exit 2
  fi
fi

TMP="$(mktemp)"
cp -p "$CFG" "${CFG}.bak"

if [[ -n "$PERSONA" && -n "$PRESET" ]]; then
  jq --arg persona "$PERSONA" --arg preset "$PRESET" '
    .env.vars = ((.env.vars // {}) + {ELEVENLABS_DEFAULT_PERSONA: $persona, ELEVENLABS_DEFAULT_PRESET: $preset})
  ' "$CFG" > "$TMP"
elif [[ -n "$PERSONA" ]]; then
  jq --arg persona "$PERSONA" '
    .env.vars = ((.env.vars // {}) + {ELEVENLABS_DEFAULT_PERSONA: $persona})
    | del(.env.vars.ELEVENLABS_DEFAULT_PRESET)
  ' "$CFG" > "$TMP"
elif [[ -n "$PRESET" ]]; then
  jq --arg vid "$VID" --arg preset "$PRESET" '
    .env.vars = ((.env.vars // {}) + {ELEVENLABS_DEFAULT_VOICE_ID: $vid, ELEVENLABS_DEFAULT_PRESET: $preset})
  ' "$CFG" > "$TMP"
else
  jq --arg vid "$VID" '
    .env.vars = ((.env.vars // {}) + {ELEVENLABS_DEFAULT_VOICE_ID: $vid})
  ' "$CFG" > "$TMP"
fi

mv "$TMP" "$CFG"

echo "Updated ${CFG} env.vars:"
jq -r '.env.vars' "$CFG"
echo
echo "Restart required: openclaw gateway restart"
