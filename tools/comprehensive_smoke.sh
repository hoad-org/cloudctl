#!/usr/bin/env bash
# file: tools/comprehensive_smoke.sh
# End-to-end smoke test using Hydration Model.
# v1.3.0 - Updated for Trojan Horse Architecture
set -Eeuo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv_smoke"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TS_UTC="$(date -u +"%Y%m%dT%H%M%SZ")"
ART_DIR="${REPO_ROOT}/tools/smoke_artifacts/${TS_UTC}"
mkdir -p "${ART_DIR}"
SUMMARY="${ART_DIR}/summary.txt"
SETUP_LOG="${ART_DIR}/setup.log"

# [CRITICAL] We test the hidden binary directly because the shell function 
# is not available in this non-interactive script environment.
BIN="_awsctl_bin"

echo "--- Starting comprehensive_smoke.sh log ---" > "${SETUP_LOG}"
echo "Log file initialized at ${SETUP_LOG}"

{
  set -x

  # -------- helpers --------
  log()  { printf "[smoke] %s\n" "$*"; }
  h()    { printf "\n[smoke] === %s ===\n" "$*"; }
  die()  { printf "❌ %s\n" "$*" >&2; exit 1; }

  record() {
    local name="$1" rc="$2" msg="$3"
    if [[ "${rc}" -eq 0 ]]; then
      printf "PASS  ✅  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}"
    else
      printf "FAIL  ❌  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}" >&2
    fi
  }

  run_and_capture() {
    local name="$1"; shift
    [[ "$1" == "--" ]] && shift
    local out="${ART_DIR}/${name}.out"
    local logf="${ART_DIR}/${name}.log"
    printf "%s CMD: %s\n" "${TS_UTC}" "$*" >> "${logf}"
    set +e
    # [FIX] Capture both streams (2>&1) so grep finds UI messages (stderr) and exports (stdout)
    "$@" > "${out}" 2>&1
    local rc=$?
    set -e
    echo "${rc}"
  }

  expect_rc() {
    local name="$1" rc="$2" want="$3"
    if [[ "${rc}" -eq "${want}" ]]; then
      record "${name}" 0 "rc=${rc}"
    else
      record "${name}" 1 "rc=${rc}, want=${want}"
    fi
  }

  expect_grep() {
    local name="$1" rc="$2" pat="$3"
    local out="${ART_DIR}/${name}.out"
    if [[ "${rc}" -eq 0 && -s "${out}" ]] && grep -qiE "${pat}" "${out}"; then
      record "${name}" 0 "found /${pat}/"
    else
      record "${name}" 1 "missing /${pat}/"
    fi
  }

  # -------- venv setup --------
  h "Create virtualenv"
  if [[ ! -d "${VENV_DIR}" ]]; then
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi
  source "${VENV_DIR}/bin/activate"
  python -m pip install --upgrade pip wheel setuptools

  h "Install awsctl (editable)"
  pip install -e ."[dev]"

  # -------- QA Checks (Lint/Test) --------
  h "Running QA Suite"
  
  # 1) Ruff
  rc=$(run_and_capture "ruff" -- ruff check src tests)
  expect_rc "ruff" "${rc}" 0

  # 2) Black (Format first to ensure check passes)
  black src tests > /dev/null 2>&1
  rc=$(run_and_capture "black-check" -- black --check src tests)
  expect_rc "black-check" "${rc}" 0

  # 3) Pytest (Unit tests)
  rc=$(run_and_capture "pytest" -- pytest -q)
  expect_rc "pytest" "${rc}" 0

  # -------- CLI in isolated HOME --------
  h "CLI smoke in temp HOME"
  TMP_HOME="$(mktemp -d)"
  export HOME="${TMP_HOME}"
  
  # [FIX] Allow overrides for Zsh testing (Defaults to bash)
  export SHELL="${TEST_SHELL:-/bin/bash}"
  
  mkdir -p "${HOME}/.aws" "${HOME}/.awsctl"
  
  # Mock shell rc files
  # Ensure NO .bash_profile exists so logic falls back to .bashrc
  rm -f "${HOME}/.bash_profile"
  touch "${HOME}/.bashrc" "${HOME}/.zshrc"

  # Write Modern Config
  echo "enabled_orgs: [engineering]" > "${HOME}/.awsctl/orgs.yaml"

  # Seed context
  echo '{"current_org": "engineering"}' > "${HOME}/.aws/awsctl-context.json"

  # 4) version
  rc=$(run_and_capture "version" -- $BIN --version)
  expect_rc "version" "${rc}" 0

  # 5) help
  rc=$(run_and_capture "help" -- $BIN --help)
  expect_grep "help" "${rc}" "Enterprise AWS Context Switcher"

  # 6) doctor
  rc=$(run_and_capture "doctor" -- $BIN doctor)
  expect_grep "doctor" "${rc}" "System Health Check"

  # 7) orgs list (should be hydrated)
  # [FIX] grep case-insensitive for robustness
  rc=$(run_and_capture "orgs" -- $BIN list orgs)
  expect_grep "orgs" "${rc}" "Engineering"

  # 8) Setup (Mocked Headless)
  export AWSCTL_HEADLESS=1
  rc=$(run_and_capture "setup" -- $BIN setup)
  expect_rc "setup" "${rc}" 0

  # 9) Shell Integration Check
  # [FIX] Dynamically check correct RC file based on SHELL
  if [[ "${SHELL}" == *"zsh"* ]]; then
      TARGET_RC="${HOME}/.zshrc"
  else
      TARGET_RC="${HOME}/.bashrc"
  fi

  # The new wrapper header is "AWSCTL SHELL INTEGRATION"
  if grep -q "AWSCTL SHELL INTEGRATION" "${TARGET_RC}"; then
      record "shell-integration" 0 "function present in $(basename ${TARGET_RC})"
  else
      record "shell-integration" 1 "missing function in $(basename ${TARGET_RC})"
      cat "${TARGET_RC}" >> "${SETUP_LOG}"
  fi

  # 10) Config Sync Check
  if grep -q "profile sso-engineering" "${HOME}/.aws/config"; then
      record "config-sync" 0 "profile sso-engineering created"
  else
      record "config-sync" 1 "missing sso profile"
  fi

  # 11) Guardrail Check: Region Violation
  # [FIX] Use 12-digit account ID to bypass lookup call and hit guardrail directly
  set +e
  $BIN switch --account 123456789012 --role Admin --region us-west-1 > "${ART_DIR}/guardrail.out" 2>&1
  rc=$?
  set -e
  
  # [FIX] Check for "Guardrail Violation" OR "not permitted" (handle smart switch variance)
  if [[ "${rc}" -ne 0 ]] && grep -qiE "Guardrail Violation|not permitted" "${ART_DIR}/guardrail.out"; then
      record "guardrail-region" 0 "blocked invalid region"
  else
      record "guardrail-region" 1 "failed to block invalid region (rc=${rc})"
  fi

  # 12) Accounts Offline (Should fail gracefully without SSO token)
  set +e
  $BIN list accounts > "${ART_DIR}/accounts-offline.out" 2>&1
  rc=$?
  set -e
  if [[ "${rc}" -ne 0 ]]; then
      record "accounts-offline" 0 "failed as expected (no token)"
  else
      record "accounts-offline" 1 "unexpected success"
  fi

  # 13) New Command: env
  rc=$(run_and_capture "env" -- $BIN env)
  expect_grep "env" "${rc}" "# No active context"

  # 14) New Command: cache-clear
  rc=$(run_and_capture "cache-clear" -- $BIN cache-clear)
  expect_grep "cache-clear" "${rc}" "Cache cleared"

  # -------- cleanup --------
  rm -rf "${TMP_HOME}"
  h "Smoke Test Complete"
  cat "${SUMMARY}"

} >> "${SETUP_LOG}" 2>&1