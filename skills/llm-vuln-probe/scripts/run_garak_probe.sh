#!/usr/bin/env bash
set -euo pipefail

PYTHON_CMD="python3"
TARGET_TYPE="openai"
TARGET_NAME="gpt-5-nano"
PROBES="encoding,promptinject,dan"
LIST_PROBES=0
DRY_RUN=0
INSTALL=0

usage() {
  cat <<'EOF'
Usage: run_garak_probe.sh [options]

Run focused NVIDIA garak probes against a target model.

Options:
      --python <cmd>        Python command (default: python3)
      --target-type <value> Target type/provider (default: openai)
      --target-name <value> Target model name (default: gpt-5-nano)
      --probes <csv>        Probe modules CSV (default: encoding,promptinject,dan)
      --list-probes         List available probes via garak and exit
      --dry-run             Print resolved garak command and exit
      --install             Install/upgrade garak if missing
  -h, --help                Show this help
EOF
}

while (($# > 0)); do
  case "$1" in
    --python)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      PYTHON_CMD="$2"
      shift 2
      ;;
    --target-type)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      TARGET_TYPE="$2"
      shift 2
      ;;
    --target-name)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      TARGET_NAME="$2"
      shift 2
      ;;
    --probes)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      PROBES="$2"
      shift 2
      ;;
    --list-probes)
      LIST_PROBES=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --install)
      INSTALL=1
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

read -r -a PYTHON_ARR <<<"$PYTHON_CMD"

run_garak() {
  "${PYTHON_ARR[@]}" -m garak "$@"
}

ensure_garak_available() {
  if run_garak --help >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$INSTALL" -eq 1 ]]; then
    echo "garak is unavailable. Installing/upgrading via pip..."
    "${PYTHON_ARR[@]}" -m pip install -U garak
    if run_garak --help >/dev/null 2>&1; then
      return 0
    fi
  fi

  cat >&2 <<'EOF'
error: unable to run "python -m garak --help".
Install garak first or re-run with --install.
Example: python3 -m pip install -U garak
EOF
  return 1
}

CMD=( "${PYTHON_ARR[@]}" -m garak --target_type "$TARGET_TYPE" --target_name "$TARGET_NAME" --probes "$PROBES" )

if [[ "$DRY_RUN" -eq 1 ]]; then
  if [[ "$LIST_PROBES" -eq 1 ]]; then
    printf '[dry-run] '
    printf '%q ' "${PYTHON_ARR[@]}" -m garak --list_probes
    printf '\n'
  else
    printf '[dry-run] '
    printf '%q ' "${CMD[@]}"
    printf '\n'
  fi
  exit 0
fi

ensure_garak_available

if [[ "$LIST_PROBES" -eq 1 ]]; then
  run_garak --list_probes
  exit 0
fi

if [[ "$DRY_RUN" -eq 0 && "$TARGET_TYPE" == "openai" ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "error: OPENAI_API_KEY is required for --target-type openai" >&2
    exit 2
  fi
fi

"${CMD[@]}"
