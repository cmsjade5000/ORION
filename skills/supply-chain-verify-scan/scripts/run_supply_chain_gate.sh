#!/usr/bin/env bash
set -euo pipefail

TARGET=""
FAIL_ON="high"
SKIP_COSIGN=0
SKIP_GRYPE=0
COSIGN_KEY=""
CERTIFICATE_IDENTITY=""
CERTIFICATE_OIDC_ISSUER=""
GRYPE_OUTPUT="table"
GRYPE_OUTPUT_FILE=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: run_supply_chain_gate.sh --target <ref> [options]

Verify signatures with Cosign and gate vulnerabilities with Grype.

Options:
  --target <ref>                         Required target (image ref, filesystem path, or sbom:...)
  --fail-on <negligible|low|medium|high|critical>
                                         Grype fail threshold (default: high)
  --skip-cosign                          Skip Cosign verification stage
  --skip-grype                           Skip Grype vulnerability scan stage
  --cosign-key <path>                    Cosign public key path for key-based verification
  --certificate-identity <value>         Expected certificate identity for keyless Cosign verify
  --certificate-oidc-issuer <value>      Expected certificate OIDC issuer for keyless Cosign verify
  --grype-output <table|json>            Grype output format (default: table)
  --grype-output-file <path>             Write Grype output to file
  --dry-run                              Print resolved commands without executing
  -h, --help                             Show this help
USAGE
}

die() {
  echo "error: $*" >&2
  exit 2
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi

  "$@"
}

while (($# > 0)); do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || die "missing value for --target"
      TARGET="$2"
      shift 2
      ;;
    --fail-on)
      [[ $# -ge 2 ]] || die "missing value for --fail-on"
      FAIL_ON="$2"
      shift 2
      ;;
    --skip-cosign)
      SKIP_COSIGN=1
      shift
      ;;
    --skip-grype)
      SKIP_GRYPE=1
      shift
      ;;
    --cosign-key)
      [[ $# -ge 2 ]] || die "missing value for --cosign-key"
      COSIGN_KEY="$2"
      shift 2
      ;;
    --certificate-identity)
      [[ $# -ge 2 ]] || die "missing value for --certificate-identity"
      CERTIFICATE_IDENTITY="$2"
      shift 2
      ;;
    --certificate-oidc-issuer)
      [[ $# -ge 2 ]] || die "missing value for --certificate-oidc-issuer"
      CERTIFICATE_OIDC_ISSUER="$2"
      shift 2
      ;;
    --grype-output)
      [[ $# -ge 2 ]] || die "missing value for --grype-output"
      GRYPE_OUTPUT="$2"
      shift 2
      ;;
    --grype-output-file)
      [[ $# -ge 2 ]] || die "missing value for --grype-output-file"
      GRYPE_OUTPUT_FILE="$2"
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
      die "unknown option: $1"
      ;;
  esac
done

[[ -n "$TARGET" ]] || die "--target is required"

case "$FAIL_ON" in
  negligible|low|medium|high|critical) ;;
  *)
    die "invalid --fail-on '$FAIL_ON' (expected negligible|low|medium|high|critical)"
    ;;
esac

case "$GRYPE_OUTPUT" in
  table|json) ;;
  *)
    die "invalid --grype-output '$GRYPE_OUTPUT' (expected table|json)"
    ;;
esac

if [[ "$SKIP_COSIGN" -eq 0 ]]; then
  if ! command -v cosign >/dev/null 2>&1; then
    cat >&2 <<'ERR'
error: cosign is required for signature verification but was not found in PATH.
Install Cosign or rerun with --skip-cosign.
ERR
    exit 127
  fi
fi

if [[ "$SKIP_GRYPE" -eq 0 ]]; then
  if ! command -v grype >/dev/null 2>&1; then
    cat >&2 <<'ERR'
error: grype is required for vulnerability scanning but was not found in PATH.
Install Grype or rerun with --skip-grype.
ERR
    exit 127
  fi
fi

if [[ "$SKIP_COSIGN" -eq 0 ]]; then
  if [[ -n "$COSIGN_KEY" ]]; then
    run_cmd cosign verify --key "$COSIGN_KEY" "$TARGET"
  elif [[ -n "$CERTIFICATE_IDENTITY" || -n "$CERTIFICATE_OIDC_ISSUER" ]]; then
    [[ -n "$CERTIFICATE_IDENTITY" && -n "$CERTIFICATE_OIDC_ISSUER" ]] || die "keyless verification requires both --certificate-identity and --certificate-oidc-issuer"
    run_cmd cosign verify \
      --certificate-identity "$CERTIFICATE_IDENTITY" \
      --certificate-oidc-issuer "$CERTIFICATE_OIDC_ISSUER" \
      "$TARGET"
  else
    die "cosign verification requires --cosign-key or both --certificate-identity and --certificate-oidc-issuer (or use --skip-cosign)"
  fi
fi

if [[ "$SKIP_GRYPE" -eq 0 ]]; then
  grype_cmd=(grype "$TARGET" --fail-on "$FAIL_ON" -o "$GRYPE_OUTPUT")

  if [[ -n "$GRYPE_OUTPUT_FILE" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      printf '+ '
      printf '%q ' "${grype_cmd[@]}"
      printf '> %q\n' "$GRYPE_OUTPUT_FILE"
    else
      "${grype_cmd[@]}" >"$GRYPE_OUTPUT_FILE"
    fi
  else
    run_cmd "${grype_cmd[@]}"
  fi
fi
