#!/usr/bin/env bash
# file: tools/comprehensive_smoke.sh
# End-to-end smoke test using Hydration Model & Mock AWS CLI.
set -Eeuo pipefail

# --------------------------
# 0. Platform Normalization
# --------------------------
IS_WINDOWS=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    IS_WINDOWS=1
    if ! command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python"
    fi
fi

export PYTHONUTF8=1
REPO_ROOT="$(pwd)"
VENV_DIR="${REPO_ROOT}/.venv_smoke"
TS_UTC="$(date -u +"%Y%m%dT%H%M%SZ")"

SHELL_ART_DIR="./tools/smoke_artifacts/${TS_UTC}"
mkdir -p "${SHELL_ART_DIR}"
SUMMARY="${SHELL_ART_DIR}/summary.txt"
SETUP_LOG="${SHELL_ART_DIR}/setup.log"

export AWSCTL_TEST_MODE=1
export BROWSER="echo"

# [VANILLA] Use generic org details for smoke testing. No secrets required.
MOCK_ORG_NAME="smoke-org"
MOCK_START_URL="https://mock.awsapps.com/start"
MOCK_REGION="us-east-1"

FAILURES=0

exec 3>&1
echo "--- Starting comprehensive_smoke.sh log ---" > "${SETUP_LOG}"
echo "Log file initialized at ${SETUP_LOG}" >&3

trap 'if [ $? -ne 0 ]; then echo -e "\n\033[0;31m💥 SCRIPT CRASHED. TAIL OF LOG:\033[0m"; tail -n 20 "$SETUP_LOG" >&3; fi' EXIT

{
  set -x

  # Helpers
  log()  { printf "[smoke] %s\n" "$*"; }
  h()    { printf "\n[smoke] === %s ===\n" "$*"; printf "\n\033[1;34m📂 %s\033[0m\n" "$*" >&3; }

  record() {
    local name="$1" rc="$2" msg="$3"
    if [ "${rc}" -eq 0 ]; then
      printf "PASS  ✅  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}"
      printf "  ✅ \033[0;32m%s\033[0m\n" "${name}" >&3
    else
      printf "FAIL  ❌  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}" >&2
      printf "  ❌ \033[0;31m%s\033[0m\n" "${name}" >&3

      printf "\n\033[0;31m>>> FAILURE DETECTED: %s <<<\033[0m\n" "${name}" >&3
      if [ -f "${SHELL_ART_DIR}/${name}.out" ]; then
          # [FIX] Use safe format string for cross-platform compatibility (macOS/BSD)
          printf '--- OUTPUT START (%s.out) ---\n' "${name}" >&3
          cat "${SHELL_ART_DIR}/${name}.out" >&3
          printf '--- OUTPUT END ---\n' >&3
      fi

      FAILURES=$((FAILURES + 1))
    fi
  }

  run_python() {
      if [ "$IS_WINDOWS" -eq 1 ]; then
          env HOME="$PYTHON_HOME" USERPROFILE="$PYTHON_HOME" "${PYTHON_BIN}" -m awsctl "$@"
      else
          "${PYTHON_BIN}" -m awsctl "$@"
      fi
  }

  awsctl() {
      local strategy_out
      strategy_out=$(run_python --check-strategy "$@" 2>/dev/null)
      local strategy
      strategy=$(echo "$strategy_out" | tail -n 1 | tr -d '[:space:]')

      if [[ "$strategy" == "EVAL" ]]; then
          local output
          output=$(run_python "$@")
          local rc=$?
          if [[ $rc -eq 0 ]]; then
              eval "$output"
          else
              echo "$output"
          fi
          return $rc
      else
          run_python "$@"
      fi
  }

  run_and_capture() {
    local name="$1"; shift
    [ "$1" == "--" ] && shift
    local out="${SHELL_ART_DIR}/${name}.out"
    local logf="${SHELL_ART_DIR}/${name}.log"
    printf "%s CMD: %s\n" "${TS_UTC}" "$*" >> "${logf}"

    set +e
    "$@" > "${out}" 2>&1
    local rc=$?
    set -e
    echo "${rc}"
  }

  expect_rc() {
    local name="$1" rc="$2" want="$3"
    if [ "${rc}" -eq "${want}" ]; then
      record "${name}" 0 "rc=${rc}"
    else
      record "${name}" 1 "rc=${rc}, want=${want}"
    fi
  }

  expect_grep() {
    local name="$1" rc="$2" pat="$3"
    local out="${SHELL_ART_DIR}/${name}.out"
    if [ "${rc}" -eq 0 -a -s "${out}" ] && grep -qiE "${pat}" "${out}"; then
      record "grep-${name}" 0 "found pattern /${pat}/"
    else
      record "grep-${name}" 1 "missing pattern /${pat}/"
    fi
  }

  # -------------------------
  # 1. Environment Setup
  # -------------------------
  h "1. Environment Setup"

  SHELL_HOME="$(mktemp -d)"
  export HOME="${SHELL_HOME}"

  if [ "$IS_WINDOWS" -eq 1 ]; then
      PYTHON_HOME="$(cygpath -w "${SHELL_HOME}")"
  else
      PYTHON_HOME="${SHELL_HOME}"
  fi

  export SHELL="${TEST_SHELL:-/bin/bash}"

  mkdir -p "${HOME}/.aws" "${HOME}/.awsctl"

  if [ ! -d "${VENV_DIR}" ]; then
    printf "  Creating virtualenv...\n" >&3
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi

  if [ -f "${VENV_DIR}/Scripts/activate" ]; then
      source "${VENV_DIR}/Scripts/activate"
  else
      source "${VENV_DIR}/bin/activate"
  fi

  python -m pip install --upgrade pip wheel setuptools

  h "2. Installation"
  pip install -e ."[dev]"

  h "3. QA Static Analysis"
  rc=$(run_and_capture "ruff" -- ruff check src tests)
  expect_rc "ruff" "${rc}" 0

  rc=$(run_and_capture "black-check" -- black --check src tests)
  rc=$(run_and_capture "pytest" -- pytest -q)
  expect_rc "pytest" "${rc}" 0

  # -------------------------
  # 4. CLI Setup & Hydration (Manual Mode Simulation)
  # -------------------------
  h "4. CLI Setup & Configuration"

  export AWSCTL_HEADLESS=1
  # Initial setup (creates default orgs.yaml with placeholder).
  # [FIX] Allow rc=1 here because the initial config is empty/invalid until we inject content below.
  rc=$(run_and_capture "setup-init" -- run_python setup) || true
  # We don't enforce expect_rc 0 here.

  # [VANILLA] Inject the Manual Config. This simulates the user copying from Confluence.
  cat <<EOF > "${HOME}/.awsctl/orgs.yaml"
enabled_orgs:
  - ${MOCK_ORG_NAME}
orgs:
  - name: ${MOCK_ORG_NAME}
    sso_start_url: ${MOCK_START_URL}
    sso_region: ${MOCK_REGION}
    default_region: ${MOCK_REGION}
    allowed_regions: ["*"]
    preferred_roles: ["SecurityAuditor"]
    sensitive_roles: ["Admin"]
    min_client_version: "0.0.0"
    plugins: []
    # [FIX] Add alias regex so 'list roles' grep passes
    role_aliases:
      "^AWSReservedSSO_(.+)_[0-9a-f]+$": "\\\\1"
EOF

  # Run setup again to sync the new config (should pass now)
  rc=$(run_and_capture "setup-sync" -- run_python setup)
  expect_rc "setup-sync" "${rc}" 0

  if [[ "$SHELL" == *"fish"* ]]; then
      record "shell-integration" 0 "skipped for fish"
  elif grep -q "AWSCTL SHELL INTEGRATION" "${HOME}/.bashrc" || grep -q "AWSCTL SHELL INTEGRATION" "${HOME}/.zshrc" || grep -q "AWSCTL SHELL INTEGRATION" "${HOME}/.profile"; then
      record "shell-integration" 0 "function present"
  else
      record "shell-integration" 1 "missing function"
  fi

  # -------------------------
  # 5. Mock State & Context Bridge
  # -------------------------
  h "5. Mock State & Context Bridge"

  MOCK_CACHE_DIR="${HOME}/.aws/sso/cache"
  mkdir -p "${MOCK_CACHE_DIR}"

  cat <<EOF > "${MOCK_CACHE_DIR}/mock_token.json"
{
  "startUrl": "${MOCK_START_URL}",
  "region": "${MOCK_REGION}",
  "accessToken": "mock-token-123",
  "expiresAt": "$(date -u -d '+8 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -v+8H -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  # -------------------------
  # Mock AWS CLI
  # -------------------------
  MOCK_BIN="${HOME}/bin"
  mkdir -p "${MOCK_BIN}"

  cat <<'EOF' > "${MOCK_BIN}/aws.py"
import sys, json

args = sys.argv[1:]
cmd = " ".join(args)

if "--version" in args:
    print("aws-cli/2.15.30 Python/3.11.6 Linux/5.15.0-1053-aws exe/x86_64.ubuntu.22")
    sys.exit(0)

if "sso get-role-credentials" in cmd:
    creds = {
        "roleCredentials": {
            "accessKeyId": "AK_NEW",
            "secretAccessKey": "SK_NEW",
            "sessionToken": "TOK_NEW",
            "expiration": 0
        }
    }
    # [FIX] Return different creds for the "Previous" account to verify toggle
    if "235494790978" in cmd:
        creds["roleCredentials"]["accessKeyId"] = "AK_OLD"
    print(json.dumps(creds))
    sys.exit(0)

if "sso list-accounts" in cmd:
    print(json.dumps({
        "accountList": [
            {
                "accountId": "338630860507",
                "accountName": "PrimaryAccount",
                "emailAddress": "primary@example.com"
            },
            {
                "accountId": "235494790978",
                "accountName": "PreviousAccount",
                "emailAddress": "previous@example.com"
            }
        ]
    }))
    sys.exit(0)

if "sso list-account-roles" in cmd:
    print(json.dumps({
        "roleList": [
            {"roleName": "AWSReservedSSO_SecurityAuditor_12345"},
            {"roleName": "AWSReservedSSO_AdministratorAccess_56789"}
        ]
    }))
    sys.exit(0)

if "sts get-caller-identity" in cmd:
    print(json.dumps({
        "Account": "338630860507",
        "Arn": "arn:aws:iam::338630860507:role/SecurityAuditor",
        "UserId": "EXAMPLE:SecurityAuditor"
    }))
    sys.exit(0)

if "sso login" in cmd or "sso logout" in cmd:
    sys.exit(0)

if "mock-verify" in cmd:
    print("{}")
    sys.exit(0)

sys.exit(0)
EOF

  if [ "$IS_WINDOWS" -eq 1 ]; then
      WIN_MOCK_SCRIPT="$(cygpath -w "${MOCK_BIN}/aws.py")"
      cat <<EOF > "${MOCK_BIN}/aws.bat"
@echo off
"${PYTHON_BIN}" "${WIN_MOCK_SCRIPT}" %*
EOF
      cat <<EOF > "${MOCK_BIN}/aws"
#!/bin/sh
"${PYTHON_BIN}" "${WIN_MOCK_SCRIPT}" "\$@"
EOF
  else
      cat <<EOF > "${MOCK_BIN}/aws"
#!/bin/sh
"${PYTHON_BIN}" "${MOCK_BIN}/aws.py" "\$@"
EOF
  fi
  chmod +x "${MOCK_BIN}/aws"

  export PATH="${MOCK_BIN}:${PATH}"

  if aws mock-verify >/dev/null; then
      record "mock-aws" 0 "Mock AWS CLI is active"
  else
      record "mock-aws" 1 "Mock AWS CLI failed setup"
  fi

  # -------------------------
  # 6. Core Features
  # -------------------------
  h "6. Core Features (Happy Path)"

  rc=$(run_and_capture "version" -- awsctl --version)
  expect_rc "version" "${rc}" 0

  rc=$(run_and_capture "doctor" -- awsctl doctor)
  expect_grep "doctor" "${rc}" "Everything looks good"

  # Login using generic mock org
  rc=$(run_and_capture "login" -- awsctl login --org "${MOCK_ORG_NAME}" --force)
  expect_rc "login" "${rc}" 0
  expect_grep "login" "${rc}" "Login Successful"

  # -------------------------
  # 8. Switch + EVAL + Toggle
  # -------------------------
  unset AWS_ACCESS_KEY_ID

  # [FIX] Step 1: Switch to "PreviousAccount" (235494790978) to seed history.
  set +e
  awsctl switch 235494790978 --role SecurityAuditor --region us-east-1 > /dev/null 2>&1
  set -e

  # [FIX] Step 2: Switch to "PrimaryAccount" (338630860507).
  set +e
  awsctl switch 338630860507 --role SecurityAuditor --region us-east-1 \
      > "${SHELL_ART_DIR}/switch.out" 2>&1
  switch_rc=$?
  set -e

  if [[ $switch_rc -eq 0 ]] && [[ "${AWS_ACCESS_KEY_ID:-}" == "AK_NEW" ]]; then
      record "switch-eval" 0 "Environment updated to primary context"
  else
      record "switch-eval" 1 "Switch failed (rc=$switch_rc) or did not set AK_NEW"
      echo "--- SWITCH FAILURE LOG ---" >&3
      cat "${SHELL_ART_DIR}/switch.out" >&3
  fi

  # [FIX] Move 'list roles' check here, AFTER we have an active context.
  # 'awsctl list roles' requires an active account to function.
  rc=$(run_and_capture "list-roles" -- run_python list roles)
  expect_grep "list-roles" "${rc}" "SecurityAuditor"

  # Toggle Back (-)
  set +e
  awsctl switch - > "${SHELL_ART_DIR}/toggle.out" 2>&1
  toggle_rc=$?
  set -e

  # Expect AK_OLD (from PreviousAccount)
  if [[ $toggle_rc -eq 0 ]] && [[ "${AWS_ACCESS_KEY_ID:-}" == "AK_OLD" ]]; then
      record "toggle-eval" 0 "Toggle switched to previous account"
  else
      record "toggle-eval" 1 "Toggle failed (rc=$toggle_rc) or did not activate previous context"
      echo "--- TOGGLE FAILURE LOG ---" >&3
      cat "${SHELL_ART_DIR}/toggle.out" >&3
  fi

  # -------------------------
  # 10. Cleanup
  # -------------------------
  h "10. Cleanup"

  rc=$(run_and_capture "cache-clear" -- awsctl cache-clear)
  expect_grep "cache-clear" "${rc}" "Cache cleared"

  awsctl logout

  if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
     record "logout-unset" 0 "Variables cleared"
  else
     record "logout-unset" 1 "Variables still set"
  fi

  rm -rf "${SHELL_HOME}"

  printf "\n\033[1;32m✨ Smoke Test Complete.\033[0m\n" >&3
  if [ "$FAILURES" -ne 0 ]; then
      printf "\n❌ FAILED: %d checks failed.\n" "$FAILURES" >&3
      exit 1
  fi
} >> "${SETUP_LOG}" 2>&1
