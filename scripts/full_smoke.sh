#!/usr/bin/env bash
# file: scripts/full_smoke.sh
# Purpose: End-to-end smoke test for awsctl.
# - Creates an isolated virtualenv
# - Installs the package (editable) so the awsctl console script exists
# - Runs linting (ruff, black) and unit tests (pytest)
# - Exercises key CLI commands in a temporary HOME
#
# Compatible: macOS, Linux, WSL
#
# Exit codes:
#  0  success
#  1  general failure
#  2  dependency missing or install failed
#  3  test failure
#  4  CLI smoke failure
#
# Summary:
#  What changed and why:
#   - Added `mkdir -p "${HOME}/.awsctl"` before `awsctl init-config > ...`.
#     The redirection operator `>` requires the target directory to exist first.
#  How to verify correctness:
#   - Run this script from repo root. It should now complete successfully.
#  How to run tests/validation:
#   - ./scripts/full_smoke.sh

set -euo pipefail

# -----------------------------
# Config
# -----------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv_smoke"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_BIN=""
WITH_SSO=0   # set to 1 with --with-sso
QUIET_PYTEST=${QUIET_PYTEST:-1}

# -----------------------------
# Logging helpers
# -----------------------------
log()  { printf "\n[full_smoke] %s\n" "$*"; }
die()  { printf "\n[full_smoke][ERROR] %s\n" "$*" >&2; exit 1; }
run()  { log "➤ $*"; "$@"; }
step() { log "=== $* ==="; }

usage() {
  cat <<'USAGE'
Usage: scripts/full_smoke.sh [--with-sso] [--keep-venv]

Options:
  --with-sso    Attempt to run 'awsctl accounts' and 'awsctl roles' if an SSO cache exists.
  --keep-venv   Do not delete the .venv_smoke virtualenv after completion.

Environment:
  PYTHON_BIN    Python executable to use (default: python3)
  QUIET_PYTEST  If set to 1, run pytest -q (default: 1)
USAGE
}

KEEP_VENV=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-sso) WITH_SSO=1; shift ;;
    --keep-venv) KEEP_VENV=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown arg: $1" ;;
  esac
done

# -----------------------------
# Sanity checks
# -----------------------------
command -v "${PYTHON_BIN}" >/dev/null 2>&1 || die "python not found: ${PYTHON_BIN}"
command -v git >/dev/null 2>&1 || die "git is required"

# -----------------------------
# Virtualenv setup
# -----------------------------
step "Create virtualenv"
if [[ -d "${VENV_DIR}" ]]; then
  log "Reusing existing venv at ${VENV_DIR}"
else
  run "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
PIP_BIN="pip"
run "${PYTHON_BIN}" -m pip install --upgrade pip wheel setuptools

# -----------------------------
# Install dependencies
# -----------------------------
step "Install dev tools (ruff, black, pytest) if missing"
# Install minimally to keep this fast. Projects with richer dev deps can add requirements-dev.txt.
run "${PIP_BIN}" install "ruff>=0.5" "black>=24.0" "pytest>=7.0"

step "Install awsctl (editable) so console script exists"
pushd "${REPO_ROOT}" >/dev/null
run "${PIP_BIN}" install -e .

# -----------------------------
# Lint + tests
# -----------------------------
step "Run ruff"
run ruff check awsctl tests


step "Run black --check"
# Check first to fail fast
run black --check awsctl tests
# Run formatters for dev convenience if check fails, but still check after
black awsctl tests >/dev/null 2>&1 || true
run black --check awsctl tests # Final check

step "Run pytest"
if [[ "${QUIET_PYTEST}" == "1" ]]; then
  run pytest -q
else
  run pytest
fi

# -----------------------------
# CLI smoke in isolated HOME
# -----------------------------
step "CLI smoke in temp HOME"
TMP_HOME="$(mktemp -d)"
export HOME="${TMP_HOME}"
export SHELL="/bin/bash"   # stable path for setup to pick ~/.bashrc
log "Temporary HOME: ${HOME}"

# Ensure ~/.aws exists for context file
mkdir -p "${HOME}/.aws"

# 1) Version must be non-empty
VER="$(awsctl --version || true)"
if [[ -z "${VER}" ]]; then
  die "awsctl --version returned empty output"
fi
log "awsctl version: ${VER}"

# 2) Help must mention awsctl-use shell helper
HELP_OUT="$(awsctl help || true)"
echo "${HELP_OUT}" | grep -q "awsctl-use --account" || die "help text missing shell helper example"

# 3) init-config should print a sample and setup should succeed
# FIX: Create the target directory *before* redirecting output to the file
mkdir -p "${HOME}/.awsctl"
awsctl init-config > "${HOME}/.awsctl/orgs.yaml"
[[ -s "${HOME}/.awsctl/orgs.yaml" ]] || die "init-config failed to write sample orgs.yaml"

# Setup should synchronize config and install shell function
awsctl setup

# Verify shell function installed into ~/.bashrc or ~/.zshrc in this temp HOME
RC_FILE_PATH=""
if [[ -f "${HOME}/.bashrc" ]]; then
  RC_FILE_PATH="${HOME}/.bashrc"
elif [[ -f "${HOME}/.zshrc" ]]; then
   RC_FILE_PATH="${HOME}/.zshrc"
fi

if [[ -n "$RC_FILE_PATH" ]]; then
    grep -q "AWSCTL SHELL INTEGRATION" "$RC_FILE_PATH" || die "shell function not injected into $RC_FILE_PATH"
else
    die "no shell rc file created by setup in ${HOME}"
fi


# 4) orgs should list at least one entry (using the sample config)
OUT_ORGS="$(awsctl orgs || true)"
echo "${OUT_ORGS}" | grep -q "name" || die "orgs did not print any data"

# 5) Optional SSO-backed checks if cache exists or when explicitly requested
SSO_CACHE_DIR_REAL="${HOME}/../.aws/sso/cache" # Check real home for cache
if [[ "${WITH_SSO}" -eq 1 && -d "${SSO_CACHE_DIR_REAL}" && -n "$(ls -A "${SSO_CACHE_DIR_REAL}" 2>/dev/null)" ]]; then
  step "Optional SSO-backed checks (cache found)"
  # Copy real cache to temp home so awsctl finds it
  cp -r "${SSO_CACHE_DIR_REAL}" "${HOME}/.aws/sso/"

  set +e
  awsctl accounts
  ACCT_RC=$?
  set -e
  if [[ "${ACCT_RC}" -ne 0 ]]; then
    log "accounts failed (likely no valid token). Skipping roles smoke."
  else
    # Pick first account ID from output if possible
    ACCT_ID="$(awsctl accounts | awk 'NR==1{print $1}' || true)" # Ensure first line only
    if [[ -n "${ACCT_ID}" && "${ACCT_ID}" != "No" ]]; then # Handle "No accounts found" case
      awsctl roles --account "${ACCT_ID}" || log "roles failed for ${ACCT_ID}"
    else
        log "Could not determine first account ID to test roles."
    fi
  fi
else
  log "Skipping accounts/roles smoke (no SSO cache found in real HOME or --with-sso not set)."
fi

# -----------------------------
# Cleanup
# -----------------------------
popd >/dev/null
# Clean up temp HOME only if KEEP_VENV is not set (implies dev mode)
if [[ "${KEEP_VENV}" -ne 1 ]]; then
    step "Cleanup temporary HOME"
    rm -rf "${TMP_HOME}"
    unset HOME # Unset HOME to avoid polluting subsequent commands in the same shell
fi

# Deactivate and clean venv unless told otherwise
if [[ "${KEEP_VENV}" -ne 1 ]]; then
  step "Cleanup virtualenv"
  deactivate || true
  rm -rf "${VENV_DIR}"
fi

step "All checks passed"
exit 0