#!/usr/bin/env bash
set -euo pipefail

TARGET="."
SEVERITY="ERROR"
JSON_OUTPUT=""
DRY_RUN=0
CONFIGS=(
  "p/security-audit"
  "skills/secure-code-preflight/rules/orion-shell-injection.yml"
)
SEMGREP_CMD=()

usage() {
  cat <<'EOF'
Usage: run_secure_code_preflight.sh [options]

Run Semgrep security preflight checks with ORION defaults.

Options:
  --target <path>                  Scan target path (default: .)
  --severity <INFO|WARNING|ERROR>  Minimum severity to fail on (default: ERROR)
  --config <value>                 Add semgrep config (repeatable; defaults are preloaded)
  --json-output <path>             Write Semgrep JSON output to file
  --dry-run                        Print resolved semgrep command and exit
  -h, --help                       Show this help
EOF
}

resolve_semgrep_command() {
  if command -v semgrep >/dev/null 2>&1; then
    SEMGREP_CMD=(semgrep)
    return 0
  fi

  if command -v python3 >/dev/null 2>&1 && python3 -c 'import semgrep' >/dev/null 2>&1; then
    SEMGREP_CMD=(python3 -m semgrep)
    return 0
  fi

  cat >&2 <<'EOF'
error: Semgrep is not installed.
Install Semgrep and retry. Examples:
  pipx install semgrep
  python3 -m pip install --user semgrep
  brew install semgrep
EOF
  return 127
}

while (($# > 0)); do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "error: missing value for --target" >&2; usage; exit 2; }
      TARGET="$2"
      shift 2
      ;;
    --severity)
      [[ $# -ge 2 ]] || { echo "error: missing value for --severity" >&2; usage; exit 2; }
      SEVERITY="$2"
      shift 2
      ;;
    --config)
      [[ $# -ge 2 ]] || { echo "error: missing value for --config" >&2; usage; exit 2; }
      CONFIGS+=("$2")
      shift 2
      ;;
    --json-output)
      [[ $# -ge 2 ]] || { echo "error: missing value for --json-output" >&2; usage; exit 2; }
      JSON_OUTPUT="$2"
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
      echo "error: unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

case "$SEVERITY" in
  INFO|WARNING|ERROR) ;;
  *)
    echo "error: invalid --severity '$SEVERITY' (expected INFO|WARNING|ERROR)" >&2
    exit 2
    ;;
esac

if [[ "$DRY_RUN" -eq 1 ]]; then
  if command -v semgrep >/dev/null 2>&1; then
    SEMGREP_CMD=(semgrep)
  elif command -v python3 >/dev/null 2>&1 && python3 -c 'import semgrep' >/dev/null 2>&1; then
    SEMGREP_CMD=(python3 -m semgrep)
  else
    SEMGREP_CMD=(semgrep)
    echo "warning: Semgrep not found; dry-run is printing a placeholder command." >&2
  fi
else
  resolve_semgrep_command
fi

cmd=("${SEMGREP_CMD[@]}" scan --error --severity "$SEVERITY" --target "$TARGET")
for cfg in "${CONFIGS[@]}"; do
  cmd+=(--config "$cfg")
done

if [[ -n "$JSON_OUTPUT" ]]; then
  cmd+=(--json --output "$JSON_OUTPUT")
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf 'Resolved command: '
  printf '%q ' "${cmd[@]}"
  printf '\n'
  exit 0
fi

"${cmd[@]}"
