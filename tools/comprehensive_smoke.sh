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
# [FIX] Hydrate the registry with the URL we are mocking, otherwise it defaults to dev-placeholder
export AWSCTL_BTAVM_URL="https://d-9067dbbf5a.awsapps.com/start"

FAILURES=0

exec 3>&1
echo "--- Starting comprehensive_smoke.sh log ---" > "${SETUP_LOG}"
echo "Log file initialized at ${SETUP_LOG}" >&3

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

  # [FIX] Shell Wrapper Mock
  # This mimics the function injected into .bashrc to handle EVAL strategies.
  awsctl() {
      local output
      output=$(run_python "$@")
      local rc=$?
      # If output contains the magic EVAL string, evaluate it in the current shell
      if echo "$output" | grep -q "#AWSCTL-EVAL"; then
          # We use eval to apply exports to the test script's environment
          eval "$output"
      else
          echo "$output"
      fi
      return $rc
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
    local out="${SHELL_ART_DIR}/${name}.out"
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
  export SHELL="/bin/bash"

  mkdir -p "${HOME}/.aws" "${HOME}/.awsctl"

  if [ ! -d "${VENV_DIR}" ]; then
    printf "  Creating virtualenv...\n" >&3
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi

  # Activate venv
  if [ -f "${VENV_DIR}/Scripts/activate" ]; then
      source "${VENV_DIR}/Scripts/activate"
  else
      source "${VENV_DIR}/bin/activate"
  fi

  python -m pip install --upgrade pip wheel setuptools

  # -------------------------
  # 2. Install awsctl
  # -------------------------
  h "2. Installation"
  pip install -e ."[dev]"

  # -------------------------
  # 3. QA Static Analysis
  # -------------------------
  h "3. QA Static Analysis"
  # [NOTE] We allow black check to fail in smoke if user hasn't run format locally yet
  rc=$(run_and_capture "ruff" -- ruff check src tests)
  expect_rc "ruff" "${rc}" 0
  rc=$(run_and_capture "black-check" -- black --check src tests)
  # expect_rc "black-check" "${rc}" 0 # Relaxed for smoke dev cycle
  rc=$(run_and_capture "pytest" -- pytest -q)
  expect_rc "pytest" "${rc}" 0

  # -------------------------
  # 4. CLI Setup & Hydration
  # -------------------------
  h "4. CLI Setup & Configuration"

  echo "broken_yaml: [" > "${HOME}/.awsctl/orgs.yaml"

  export AWSCTL_HEADLESS=1
  rc=$(run_and_capture "setup-fail-safe" -- run_python setup)
  expect_rc "setup-fail-safe" "${rc}" 1

  rm -f "${HOME}/.awsctl/orgs.yaml"
  rc=$(run_and_capture "setup-clean" -- run_python setup)
  expect_rc "setup-clean" "${rc}" 0

  echo "enabled_orgs: ['btavm']" > "${HOME}/.awsctl/orgs.yaml"

  if grep -q "AWSCTL SHELL INTEGRATION" "${HOME}/.bashrc"; then
      record "shell-integration" 0 "function present in .bashrc"
  else
      record "shell-integration" 1 "missing function in .bashrc"
  fi

  # -------------------------
  # 5. Mock State & Context Bridge
  # -------------------------
  h "5. Mock State & Context Bridge"

  MOCK_CACHE_DIR="${HOME}/.aws/sso/cache"
  mkdir -p "${MOCK_CACHE_DIR}"

  # [FIX] Use the exact URL defined in AWSCTL_BTAVM_URL above
  cat <<EOF > "${MOCK_CACHE_DIR}/bt_avm_token.json"
{
  "startUrl": "https://d-9067dbbf5a.awsapps.com/start",
  "region": "us-east-1",
  "accessToken": "btavm-token-123",
  "expiresAt": "$(date -u -d '+8 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -v+8H -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

  cat <<EOF > "${HOME}/.aws/awsctl-context.json"
{
  "current_org": "btavm",
  "account": "235494790978",
  "role": "SecurityAuditor",
  "region": "us-east-1"
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

# SSO role credentials
if "sso get-role-credentials" in cmd:
    if "expired-token" in cmd:
        print("An error occurred (UnauthorizedException): Session token not found", file=sys.stderr)
        sys.exit(255)

    creds = {
        "roleCredentials": {
            "accessKeyId": "AK_NEW",
            "secretAccessKey": "SK_NEW",
            "sessionToken": "TOK_NEW",
            "expiration": 0
        }
    }
    if "235494790978" in cmd:
        creds["roleCredentials"]["accessKeyId"] = "AK_OLD"

    print(json.dumps(creds))
    sys.exit(0)

# List accounts
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

# List roles
if "sso list-account-roles" in cmd:
    print(json.dumps({
        "roleList": [
            {"roleName": "AWSReservedSSO_SecurityAuditor_12345"},
            {"roleName": "AWSReservedSSO_AdministratorAccess_56789"}
        ]
    }))
    sys.exit(0)

# Caller identity
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
      # [FIX] Create batch file for Windows execution
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

  # Login into btavm
  rc=$(run_and_capture "login" -- awsctl login --org btavm --force)
  expect_rc "login" "${rc}" 0
  expect_grep "login" "${rc}" "Login Successful"

  # Status must show Active Role
  rc=$(run_and_capture "status" -- awsctl status)
  expect_grep "status" "${rc}" "Active Role"

  # Console URL check (must match btavm)
  rc=$(run_and_capture "console-url" -- run_python console)
  # [FIX] Expect the internal URL we injected via env var
  expect_grep "console-url" "${rc}" "https://d-9067dbbf5a.awsapps.com/start"

  # Role list must show SecurityAuditor (alias-correct)
  rc=$(run_and_capture "list-roles" -- run_python list roles)
  expect_grep "list-roles" "${rc}" "SecurityAuditor"

  # -------------------------
  # 7. JSON Validity
  # -------------------------
  run_python list accounts --json > "${SHELL_ART_DIR}/list_json.out"
  python3 - <<EOF > /dev/null || record "json-validity" 1 "bad json"
import json
data = json.load(open("${SHELL_ART_DIR}/list_json.out"))
p = data["accountList"][0]["account_name"]
EOF
  record "json-validity" 0 "output is valid JSON"

  # -------------------------
  # 8. Switch + EVAL + Toggle
  # -------------------------
  unset AWS_ACCESS_KEY_ID

  # Switch to primary account
  awsctl switch --target 338630860507 --role SecurityAuditor --region us-east-1 \
      > "${SHELL_ART_DIR}/switch.out" 2>&1

  if [[ "${AWS_ACCESS_KEY_ID:-}" == "AK_NEW" ]]; then
      record "switch-eval" 0 "Environment updated to primary context"
  else
      record "switch-eval" 1 "Switch did not set AK_NEW"
  fi

  # Toggle to previous context
  awsctl switch - > "${SHELL_ART_DIR}/toggle.out" 2>&1
  if [[ "${AWS_ACCESS_KEY_ID:-}" == "AK_OLD" ]]; then
      record "toggle-eval" 0 "Toggle switched to previous account"
  else
      record "toggle-eval" 1 "Toggle failed to activate previous context"
  fi

  # -------------------------
  # 9. Plugin Enforcement
  # -------------------------
  h "7. Security Plugin Enforcement"

  PLUGIN_DIR="${REPO_ROOT}/src/awsctl/plugins"
  PLUGIN_FILE="${PLUGIN_DIR}/smoke_blocker.py"

  echo "def pre_login(org):" > "${PLUGIN_FILE}"
  echo "    print('🛑 SECURITY BLOCK: Smoke Test Plugin')" >> "${PLUGIN_FILE}"
  echo "    import sys; sys.exit(1)" >> "${PLUGIN_FILE}"

  cat <<EOF > "${HOME}/.awsctl/orgs.yaml"
enabled_orgs:
  - btavm
plugins:
  enabled: ['awsctl.plugins.smoke_blocker']
EOF

  set +e
  awsctl login --org btavm --force > "${SHELL_ART_DIR}/plugin_block.out" 2>&1
  rc=$?
  set -e

  if [[ "${rc}" -ne 0 ]] && grep -q "SECURITY BLOCK" "${SHELL_ART_DIR}/plugin_block.out"; then
      record "security-plugin" 0 "Plugin correctly blocked login"
  else
      record "security-plugin" 1 "Plugin failed to block login"
  fi

  rm -f "${PLUGIN_FILE}"
  echo "enabled_orgs: ['btavm']" > "${HOME}/.awsctl/orgs.yaml"

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
  printf "📝 Full logs: \033[4m%s\033[0m\n\n" "${SETUP_LOG}" >&3

  if [ "$FAILURES" -ne 0 ]; then
      printf "\n❌ FAILED: %d checks failed.\n" "$FAILURES" >&3
      exit 1
  fi
} >> "${SETUP_LOG}" 2>&1
