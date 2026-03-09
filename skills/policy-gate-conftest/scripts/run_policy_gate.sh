#!/usr/bin/env bash
set -euo pipefail

POLICY_DIR="skills/policy-gate-conftest/policies"
NAMESPACE="main"
OUTPUT_FORMAT="table"
ALL_NAMESPACES=0
DEFAULT_INPUT="skills/policy-gate-conftest/examples/task_packet.pass.json"
INPUTS=()

usage() {
  cat <<'USAGE'
Usage: run_policy_gate.sh [options] [input ...]

Run Conftest policy checks against one or more input files.

Options:
  --policy-dir <path>    Policy directory (default: skills/policy-gate-conftest/policies)
  --namespace <name>     Policy namespace (default: main)
  --output <format>      Output format: table|json|junit (default: table)
  --all-namespaces       Evaluate all policy namespaces
  -h, --help             Show this help message

If no input files are provided, defaults to:
  skills/policy-gate-conftest/examples/task_packet.pass.json
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --policy-dir)
      if [[ $# -lt 2 ]]; then
        echo "Error: --policy-dir requires a value." >&2
        exit 2
      fi
      POLICY_DIR="$2"
      shift 2
      ;;
    --namespace)
      if [[ $# -lt 2 ]]; then
        echo "Error: --namespace requires a value." >&2
        exit 2
      fi
      NAMESPACE="$2"
      shift 2
      ;;
    --output)
      if [[ $# -lt 2 ]]; then
        echo "Error: --output requires a value." >&2
        exit 2
      fi
      OUTPUT_FORMAT="$2"
      case "$OUTPUT_FORMAT" in
        table|json|junit) ;;
        *)
          echo "Error: --output must be one of: table, json, junit." >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    --all-namespaces)
      ALL_NAMESPACES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        INPUTS+=("$1")
        shift
      done
      ;;
    -*)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      INPUTS+=("$1")
      shift
      ;;
  esac
done

if ! command -v conftest >/dev/null 2>&1; then
  echo "Error: conftest command not found. Install Conftest and retry." >&2
  exit 127
fi

if [[ ${#INPUTS[@]} -eq 0 ]]; then
  INPUTS=("$DEFAULT_INPUT")
fi

CMD=(conftest test --policy "$POLICY_DIR" --output "$OUTPUT_FORMAT")

if [[ "$ALL_NAMESPACES" -eq 1 ]]; then
  CMD+=(--all-namespaces)
else
  CMD+=(--namespace "$NAMESPACE")
fi

CMD+=("${INPUTS[@]}")

"${CMD[@]}"
