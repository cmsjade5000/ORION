#!/usr/bin/env bash
set -euo pipefail

PYTHON_CMD="python3"
SCHEMA_VERSION="2025-11-25"
SCHEMA_URL_OVERRIDE=""
INSTALL=0
DRY_RUN=0
INPUTS=()

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_INPUT="${SKILL_DIR}/examples/ping_request.json"

usage() {
  cat <<'USAGE'
Usage: run_mcp_schema_check.sh [options]

Validate one or more MCP JSON files against the official MCP JSON schema.

Options:
      --input <path>           Input JSON file to validate (repeatable)
                               Default: skills/mcp-schema-compliance-check/examples/ping_request.json
      --schema-version <value> MCP schema version directory (default: 2025-11-25)
      --schema-url <url>       Override schema URL (default builds from --schema-version)
      --python <cmd>           Python command (default: python3)
      --install                Install jsonschema if missing
      --dry-run                Print resolved command/config and exit
  -h, --help                   Show this help
USAGE
}

while (($# > 0)); do
  case "$1" in
    --input)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      INPUTS+=("$2")
      shift 2
      ;;
    --schema-version)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      SCHEMA_VERSION="$2"
      shift 2
      ;;
    --schema-url)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      SCHEMA_URL_OVERRIDE="$2"
      shift 2
      ;;
    --python)
      [[ $# -ge 2 ]] || { echo "error: missing value for $1" >&2; usage; exit 2; }
      PYTHON_CMD="$2"
      shift 2
      ;;
    --install)
      INSTALL=1
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
      echo "error: unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ ${#INPUTS[@]} -eq 0 ]]; then
  INPUTS=("$DEFAULT_INPUT")
fi

if [[ -n "$SCHEMA_URL_OVERRIDE" ]]; then
  SCHEMA_URL="$SCHEMA_URL_OVERRIDE"
else
  SCHEMA_URL="https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/${SCHEMA_VERSION}/schema.json"
fi

read -r -a PYTHON_ARR <<<"$PYTHON_CMD"
PYTHON_BIN="${PYTHON_ARR[0]:-}"

if [[ -z "$PYTHON_BIN" ]] || ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: python command not found: $PYTHON_CMD" >&2
  exit 127
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] python: $PYTHON_CMD"
  echo "[dry-run] schema_url: $SCHEMA_URL"
  for input_file in "${INPUTS[@]}"; do
    echo "[dry-run] input: $input_file"
  done
  exit 0
fi

jsonschema_available() {
  "${PYTHON_ARR[@]}" -c "import jsonschema" >/dev/null 2>&1
}

if ! jsonschema_available; then
  if [[ "$INSTALL" -eq 1 ]]; then
    echo "jsonschema is missing. Installing via pip..."
    if ! "${PYTHON_ARR[@]}" -m pip install jsonschema; then
      echo "warning: automatic install failed for python command: $PYTHON_CMD" >&2
    fi
  fi
fi

if ! jsonschema_available; then
  cat >&2 <<'ERR'
error: missing Python dependency "jsonschema".
Install it with:
  python3 -m pip install jsonschema
or rerun this script with --install.
ERR
  exit 1
fi

"${PYTHON_ARR[@]}" - "$SCHEMA_URL" "${INPUTS[@]}" <<'PY'
import json
import sys
import urllib.request

import jsonschema

schema_url = sys.argv[1]
input_paths = sys.argv[2:]

if not input_paths:
    print("error: no input files provided", file=sys.stderr)
    sys.exit(2)

try:
    with urllib.request.urlopen(schema_url, timeout=30) as resp:
        schema = json.loads(resp.read().decode("utf-8"))
except Exception as exc:
    print(f"error: failed to load schema from {schema_url}: {exc}", file=sys.stderr)
    sys.exit(2)

try:
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
except Exception as exc:
    print(f"error: invalid schema from {schema_url}: {exc}", file=sys.stderr)
    sys.exit(2)

failures = 0

for path in input_paths:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        failures += 1
        print(f"FAIL {path} :: unable to read/parse JSON: {exc}")
        continue

    try:
        validator.validate(payload)
        print(f"PASS {path}")
    except jsonschema.exceptions.ValidationError as exc:
        failures += 1
        loc = "/".join(str(p) for p in exc.path) if exc.path else "<root>"
        print(f"FAIL {path} :: {exc.message} (at {loc})")

sys.exit(1 if failures else 0)
PY
