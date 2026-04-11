#!/usr/bin/env bash
set -euo pipefail

INCLUDE_KIMI_FALLBACK=1
LOCAL_BASE_URL="${LOCAL_LLM_BASE_URL:-http://127.0.0.1:1234/v1}"
LOCAL_MODEL="${LOCAL_LLM_MODEL:-qwen3.5-4b-mlx}"
CURATED_FREE_MODEL="${OPENROUTER_CURATED_FREE_MODEL:-openai/gpt-oss-20b:free}"
OPENAI_PRIMARY_MODEL="${OPENAI_PRIMARY_MODEL:-openai/gpt-5.4}"
DRY_RUN=0
OPENROUTER_MODEL_LIST=""

usage() {
  cat <<'USAGE'
Usage: scripts/openclaw_configure_llm_providers.sh [options]

Configure OpenClaw runtime for ORION's provider matrix.

Options:
  --openai-primary-model <id> Set OpenAI primary model id (default: openai/gpt-5.4)
  --include-kimi-fallback   Keep NVIDIA Build Kimi K2.5 as tertiary model fallback (default)
  --no-kimi-fallback        Disable NVIDIA Build fallback
  --curated-free-model <id> Set curated OpenRouter :free fallback model id
  --local-base-url <url>    Register/update LM Studio local provider base URL
  --local-model <model>     Register/update local model id
  --dry-run                 Print intended commands without applying
  -h, --help                Show help

Notes:
- OpenAI is the default primary lane for ORION runtime routing.
- OpenRouter stays configured only as an explicit fallback path.
- This script modifies ~/.openclaw/openclaw.json via `openclaw config set`.
USAGE
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %q' "$1"
    shift
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
  else
    "$@"
  fi
}

load_openrouter_model_list() {
  if [[ -n "$OPENROUTER_MODEL_LIST" ]]; then
    return
  fi
  OPENROUTER_MODEL_LIST="$(openclaw models list --all --provider openrouter --plain 2>/dev/null || true)"
}

resolve_model_id() {
  local fallback="$1"
  shift || true

  load_openrouter_model_list

  local candidate
  for candidate in "$fallback" "$@"; do
    if [[ -n "$candidate" ]] && printf '%s\n' "$OPENROUTER_MODEL_LIST" | grep -Fxq "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf '%s\n' "$fallback"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-kimi-fallback)
      INCLUDE_KIMI_FALLBACK=1
      shift
      ;;
    --no-kimi-fallback)
      INCLUDE_KIMI_FALLBACK=0
      shift
      ;;
    --openai-primary-model)
      OPENAI_PRIMARY_MODEL="$2"
      shift 2
      ;;
    --curated-free-model)
      CURATED_FREE_MODEL="$2"
      shift 2
      ;;
    --local-base-url)
      LOCAL_BASE_URL="$2"
      shift 2
      ;;
    --local-model)
      LOCAL_MODEL="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

OPENROUTER_FREE_MODEL="$(resolve_model_id openrouter/free openrouter/openrouter/free)"
CURATED_FREE_RESOLVED="$(resolve_model_id "$CURATED_FREE_MODEL" "openrouter/${CURATED_FREE_MODEL}")"

run_cmd echo "Configured primary=${OPENAI_PRIMARY_MODEL} free=${OPENROUTER_FREE_MODEL} curated=${CURATED_FREE_RESOLVED}"

run_cmd openclaw config set tools.profile coding
run_cmd openclaw config set models.mode merge
run_cmd openclaw config set agents.defaults.model.primary "$OPENAI_PRIMARY_MODEL"
run_cmd openclaw models fallbacks clear
run_cmd openclaw models fallbacks add "$OPENROUTER_FREE_MODEL"
run_cmd openclaw models fallbacks add "$CURATED_FREE_RESOLVED"

run_cmd openclaw config set --json 'models.providers["nvidia-build"]' "{
  \"api\": \"openai-completions\",
  \"baseUrl\": \"https://integrate.api.nvidia.com/v1\",
  \"apiKey\": {\"source\": \"env\", \"provider\": \"default\", \"id\": \"NVIDIA_API_KEY\"},
  \"models\": [{\"id\": \"moonshotai/kimi-k2.5\", \"name\": \"Kimi K2.5 (NVIDIA Build)\"}]
}"

run_cmd openclaw config set --json 'models.providers["lmstudio"]' "{
  \"api\": \"openai-completions\",
  \"baseUrl\": \"${LOCAL_BASE_URL}\",
  \"apiKey\": \"\${LOCAL_LLM_API_KEY}\",
  \"models\": [{\"id\": \"${LOCAL_MODEL}\", \"name\": \"Local bounded runtime\"}]
}"

if [[ "$INCLUDE_KIMI_FALLBACK" -eq 1 ]]; then
  run_cmd openclaw models fallbacks add nvidia-build/moonshotai/kimi-k2.5
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  openclaw models status --probe
else
  echo "[dry-run] openclaw models status --probe"
fi
