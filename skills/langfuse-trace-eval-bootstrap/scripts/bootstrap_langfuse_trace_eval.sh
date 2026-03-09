#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=".tmp/langfuse-bootstrap"
PYTHON_CMD="python3"
INSTALL=0
RUN_SMOKE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: bootstrap_langfuse_trace_eval.sh [options]

Bootstrap Langfuse trace/eval scaffolding for ORION workflows.

Options:
  --project-dir <path>  Output project directory (default: .tmp/langfuse-bootstrap)
  --python <cmd>        Python command (default: python3)
  --install             Create venv and install dependencies
  --run-smoke           Run smoke trace script after scaffolding
  --dry-run             Scaffold files, then skip install/smoke execution
  -h, --help            Show this help message

Notes:
  - This script always scaffolds:
      .env.example
      langfuse_smoke.py
      requirements.txt
  - --run-smoke requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.
  - LANGFUSE_BASE_URL defaults to https://cloud.langfuse.com when unset.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      [[ $# -ge 2 ]] || { echo "Error: --project-dir requires a value" >&2; usage; exit 2; }
      PROJECT_DIR="$2"
      shift 2
      ;;
    --python)
      [[ $# -ge 2 ]] || { echo "Error: --python requires a value" >&2; usage; exit 2; }
      PYTHON_CMD="$2"
      shift 2
      ;;
    --install)
      INSTALL=1
      shift
      ;;
    --run-smoke)
      RUN_SMOKE=1
      shift
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
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXAMPLES_DIR="$SKILL_DIR/examples"

mkdir -p "$PROJECT_DIR"

cp "$EXAMPLES_DIR/.env.example" "$PROJECT_DIR/.env.example"
cp "$EXAMPLES_DIR/langfuse_smoke.py" "$PROJECT_DIR/langfuse_smoke.py"
cat >"$PROJECT_DIR/requirements.txt" <<'REQ'
langfuse
openai
python-dotenv
REQ

echo "Scaffolded files in: $PROJECT_DIR"
echo "- $PROJECT_DIR/.env.example"
echo "- $PROJECT_DIR/langfuse_smoke.py"
echo "- $PROJECT_DIR/requirements.txt"

read -r -a PYTHON_ARR <<<"$PYTHON_CMD"
VENV_DIR="$PROJECT_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"

if [[ "$INSTALL" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %q ' "${PYTHON_ARR[@]}" -m venv "$VENV_DIR"
    printf '\n'
    printf '[dry-run] %q ' "$VENV_PY" -m pip install --upgrade pip
    printf '\n'
    printf '[dry-run] %q ' "$VENV_PY" -m pip install -r "$PROJECT_DIR/requirements.txt"
    printf '\n'
  else
    "${PYTHON_ARR[@]}" -m venv "$VENV_DIR"
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r "$PROJECT_DIR/requirements.txt"
    echo "Installed dependencies in: $VENV_DIR"
  fi
fi

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  if [[ -z "${LANGFUSE_PUBLIC_KEY:-}" ]]; then
    echo "Error: LANGFUSE_PUBLIC_KEY is required when using --run-smoke" >&2
    exit 2
  fi

  if [[ -z "${LANGFUSE_SECRET_KEY:-}" ]]; then
    echo "Error: LANGFUSE_SECRET_KEY is required when using --run-smoke" >&2
    exit 2
  fi

  export LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-https://cloud.langfuse.com}"

  SMOKE_PY=("${PYTHON_ARR[@]}")
  if [[ -x "$VENV_PY" ]]; then
    SMOKE_PY=("$VENV_PY")
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %q ' "${SMOKE_PY[@]}" "$PROJECT_DIR/langfuse_smoke.py"
    printf '\n'
  else
    "${SMOKE_PY[@]}" "$PROJECT_DIR/langfuse_smoke.py"
  fi
fi

echo
echo "Next steps:"
echo "1. Copy $PROJECT_DIR/.env.example to $PROJECT_DIR/.env and fill Langfuse credentials."
echo "2. Re-run with --install to create a local venv (optional if deps are already installed)."
echo "3. Run smoke: bash skills/langfuse-trace-eval-bootstrap/scripts/bootstrap_langfuse_trace_eval.sh --project-dir $PROJECT_DIR --run-smoke"
echo "4. Open printed trace URL in Langfuse to verify ingestion."
