#!/usr/bin/env bash
set -euo pipefail

CONFIG="promptfooconfig.yaml"
MAX_EVAL_FAILS=0
MAX_REDTEAM_FAILS=2
SKIP_GENERATE=0
PROMPTFOO_CMD_STR="npx -y promptfoo@latest"

usage() {
  cat <<'EOF'
Usage: run_redteam_gate.sh [options]

Run Promptfoo eval + red-team checks and enforce failure thresholds.

Options:
  -c, --config <path>         Config path (default: promptfooconfig.yaml)
      --max-eval-fails <int>  Max allowed eval failures+errors (default: 0)
      --max-redteam-fails <int>
                              Max allowed redteam failures+errors (default: 2)
      --skip-generate         Skip "redteam run" generation step
      --promptfoo <cmd>       Promptfoo command (default: npx -y promptfoo@latest)
  -h, --help                  Show this help
EOF
}

is_nonneg_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

while (($# > 0)); do
  case "$1" in
    -c|--config)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      CONFIG="$2"
      shift 2
      ;;
    --max-eval-fails)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      MAX_EVAL_FAILS="$2"
      shift 2
      ;;
    --max-redteam-fails)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      MAX_REDTEAM_FAILS="$2"
      shift 2
      ;;
    --skip-generate)
      SKIP_GENERATE=1
      shift
      ;;
    --promptfoo)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      PROMPTFOO_CMD_STR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if ! is_nonneg_int "$MAX_EVAL_FAILS"; then
  echo "error: --max-eval-fails must be a non-negative integer" >&2
  exit 2
fi

if ! is_nonneg_int "$MAX_REDTEAM_FAILS"; then
  echo "error: --max-redteam-fails must be a non-negative integer" >&2
  exit 2
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "error: config not found: $CONFIG" >&2
  exit 2
fi

read -r -a PROMPTFOO_CMD <<<"$PROMPTFOO_CMD_STR"

run_promptfoo() {
  "${PROMPTFOO_CMD[@]}" "$@"
}

sum_failures_and_errors() {
  local file="$1"
  jq -r '((.results.stats.failures // .stats.failures // 0) + (.results.stats.errors // .stats.errors // 0))' "$file"
}

mkdir -p .promptfoo

echo "[1/4] Validate config: $CONFIG"
run_promptfoo validate config -c "$CONFIG"

echo "[2/4] Run eval -> .promptfoo/eval-results.json"
run_promptfoo eval -c "$CONFIG" -o .promptfoo/eval-results.json --no-progress-bar

if [[ "$SKIP_GENERATE" -eq 0 ]]; then
  echo "[3/4] Run redteam generate -> .promptfoo/redteam.yaml"
  run_promptfoo redteam run -c "$CONFIG" --output .promptfoo/redteam.yaml --no-progress-bar
else
  echo "[3/4] Skip redteam generate (--skip-generate)"
fi

echo "[4/4] Run redteam eval -> .promptfoo/redteam-results.json"
run_promptfoo redteam eval -c "$CONFIG" -o .promptfoo/redteam-results.json --no-progress-bar

if command -v jq >/dev/null 2>&1; then
  eval_bad="$(sum_failures_and_errors .promptfoo/eval-results.json)"
  redteam_bad="$(sum_failures_and_errors .promptfoo/redteam-results.json)"

  echo "eval_bad=$eval_bad (max=$MAX_EVAL_FAILS)"
  echo "redteam_bad=$redteam_bad (max=$MAX_REDTEAM_FAILS)"

  if (( eval_bad > MAX_EVAL_FAILS )); then
    echo "FAILED: eval threshold exceeded"
    exit 1
  fi

  if (( redteam_bad > MAX_REDTEAM_FAILS )); then
    echo "FAILED: redteam threshold exceeded"
    exit 1
  fi

  echo "SUCCESS: thresholds satisfied"
else
  echo "WARNING: jq not found; skipping numeric threshold checks"
  echo "SUCCESS: command runs completed (threshold checks skipped)"
fi
