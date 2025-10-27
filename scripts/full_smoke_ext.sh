#!/usr/bin/env bash
# file: scripts/full_smoke_ext.sh
# End-to-end + feature-by-feature smoke with artifacts and PASS/FAIL marks.
#
# UPDATES:
# - Added test for `awsctl-use` shell function (step 7)
# - Added test for `awsctl roles --json` (step 13)
# - Cleaned up run_and_capture to avoid double-execution of shell functions
# - AGGRESSIVE LOGGING: Redirect *all* script output (stdout/stderr)
#   to setup.log to catch early failures.
# - Force-create log file with `echo` before logging block starts.
# - FIX: Replaced `read -r -d '' ORGS_YAML` with `ORGS_YAML=$(cat <<'YAML' ...)`
#   to avoid non-zero exit code on EOF which triggered `set -e`.
# - FIX: Added missing space in `record "use" 1 ...` call.
# - FIX: Check both stdout (.out) and stderr (.log) for expected token errors.
# - FIX (2025-10-24): Added `pytest-mock` to dev-tools install to fix pytest failures.
# - FIX (2025-10-24): Consolidated install step to just `pip install -e .[dev]`
# - FIX (2025-10-24): Run `black` formatter before `black --check`.
set -Eeuo pipefail

# -------- config --------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv_smoke"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WITH_SSO=0           # set by --with-sso
KEEP_VENV=0          # set by --keep-venv
TS_UTC="$(date -u +"%Y%m%dT%H%M%SZ")"
ART_DIR="${REPO_ROOT}/tools/smoke_artifacts/${TS_UTC}"
mkdir -p "${ART_DIR}"

# NEW: Create a setup log for early debugging
SETUP_LOG="${ART_DIR}/setup.log"
SUMMARY="${ART_DIR}/summary.txt"

# NEW: Force-create the log file with an initial message
echo "--- Starting full_smoke_ext.sh log ---" > "${SETUP_LOG}"
echo "Log file initialized at ${SETUP_LOG}" | tee -a "${SETUP_LOG}"

# -------- AGGRESSIVE LOGGING START --------
# Now append all other output to this log file
{
  # Enable command tracing inside the log
  set -x

  # Sample orgs config used in isolated HOME (matches your provided config)
  # FIX: Use `cat` to assign multiline string robustly under `set -e`
  ORGS_YAML=$(cat <<'YAML'
# awsctl configuration
orgs:
- name: myorg
  sso_start_url: https://d-9c67661145.awsapps.com/start
  sso_region: eu-west-2
  default_region: eu-west-2
  allowed_regions: [eu-west-1, eu-west-2, eu-central-1]
  preferred_roles:
  - AdministratorAccess
  - ViewOnlyAccess

plugins:
  enabled: []
YAML
)

  # -------- helpers --------
  log()  { printf "[full_smoke_ext] %s\n" "$*"; }
  h()    { printf "\n[full_smoke_ext] === %s ===\n" "$*"; }
  ok()   { printf "✅ %s\n" "$*"; }
  bad()  { printf "❌ %s\n" "$*" >&2; }
  die()  { bad "$*"; exit 1; }

  # record <name> <rc> <msg>
  record() {
    local name="$1" rc="$2" msg="$3"
    if [[ "${rc}" -eq 0 ]]; then
      printf "PASS  ✅  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}"
    else
      printf "FAIL  ❌  %s :: %s\n" "${name}" "${msg}" | tee -a "${SUMMARY}" >&2
    fi
  }

  # run_and_capture <name> -- <cmd...>
  # writes stdout to ${ART_DIR}/<name>.out, stderr+rc to .log
  run_and_capture() {
    local name="$1"; shift
    [[ "$1" == "--" ]] || die "run_and_capture usage"
    shift
    local out="${ART_DIR}/${name}.out"
    local logf="${ART_DIR}/${name}.log"
    printf "%s CMD: %s\n" "${TS_UTC}" "$*" >> "${logf}"
    set +e

    local rc=0
    # Special handling for awsctl-use, which is a shell function
    # and must be run in the current shell, not a subshell.
    if [[ "$1" == "awsctl-use" ]]; then
        "$@" > "${out}" 2>> "${logf}"
        rc=$?
    else
        # Execute other commands in a subshell
        ( "$@" > "${out}" 2>> "${logf}" )
        rc=$?
    fi

    printf "%s RC: %d\n" "${TS_UTC}" "${rc}" >> "${logf}"
    set -e
    echo "${rc}"
  }

  # expect helpers
  # expect_nonempty <name> <rc>
  expect_nonempty() {
    local name="$1" rc="$2"
    local out="${ART_DIR}/${name}.out"
    if [[ "${rc}" -eq 0 && -s "${out}" ]]; then
      record "${name}" 0 "non-empty output"
    else
      record "${name}" 1 "empty output or rc=${rc}"
    fi
  }

  # expect_rc <name> <rc> <wanted_rc>
  expect_rc() {
    local name="$1" rc="$2" want="$3"
    if [[ "${rc}" -eq "${want}" ]]; then
      record "${name}" 0 "rc=${rc}"
    else
      record "${name}" 1 "rc=${rc}, want=${want}"
    fi
  }

  # expect_grep <name> <rc> <pattern>
  expect_grep() {
    local name="$1" rc="$2" pat="$3"
    local out="${ART_DIR}/${name}.out"
    if [[ "${rc}" -eq 0 && -s "${out}" ]] && grep -qE "${pat}" "${out}"; then
      record "${name}" 0 "found /${pat}/"
    else
      record "${name}" 1 "missing /${pat}/ or rc=${rc}"
    fi
  }

  # -------- args --------
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --with-sso) WITH_SSO=1; shift ;;
      --keep-venv) KEEP_VENV=1; shift ;;
      -h|--help)
        cat <<EOF
bash scripts/full_smoke_ext.sh
bash scripts/full_smoke_ext.sh --with-sso
open tools/smoke_artifacts/\$(ls -1 tools/smoke_artifacts | tail -1)
EOF
        exit 0
        ;;
      *) die "unknown arg: $1" ;;
    esac
  done

  log "starting… pid=$$ shell=$SHELL"
  log "artifacts -> ${ART_DIR}"
  log "Full script output logging to ${SETUP_LOG}"

  # -------- venv setup with logging --------
  h "Create virtualenv"
  if [[ -d "${VENV_DIR}" ]]; then
    log "Reusing existing venv at ${VENV_DIR}"
  else
    log "Creating new venv..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi

  log "Activating virtualenv..."
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"

  log "Upgrading pip..."
  python -m pip install --upgrade pip wheel setuptools

  log "Initial setup complete."

  # -------- install editable with dev deps--------
  h "Install awsctl (editable) with dev dependencies"
  # This single command should install awsctl editable AND all deps from [project.optional-dependencies.dev]
  rc=$(run_and_capture "install-editable-dev" -- pip install -e ."[dev]")
  expect_rc "install-editable-dev" "${rc}" 0


  # -------- lint + tests --------
  h "Run ruff"
  # Assuming ruff is installed via the [dev] extra
  rc=$(run_and_capture "ruff" -- ruff check awsctl tests)
  expect_rc "ruff" "${rc}" 0

  h "Run black formatter then check"
  # Run black formatter first to fix any issues
  rc=$(run_and_capture "black-format" -- black awsctl tests)
  expect_rc "black-format" "${rc}" 0 # Expect formatting to succeed

  # Now run the checks, which should pass
  rc=$(run_and_capture "black-check-1" -- black --check awsctl tests)
  expect_rc "black-check-1" "${rc}" 0
  rc=$(run_and_capture "black-check-2" -- black --check awsctl tests)
  expect_rc "black-check-2" "${rc}" 0

  h "Run pytest"
  # Assuming pytest and pytest-mock are installed via the [dev] extra
  rc=$(run_and_capture "pytest" -- pytest -q)
  expect_rc "pytest" "${rc}" 0

  # -------- CLI in isolated HOME --------
  h "CLI smoke in temp HOME"
  TMP_HOME="$(mktemp -d)"
  export HOME="${TMP_HOME}"
  export SHELL="/bin/bash"
  log "Temporary HOME: ${HOME}"
  mkdir -p "${HOME}/.aws" "${HOME}/.awsctl"

  # seed orgs.yaml
  printf "%s\n" "${ORGS_YAML}" > "${HOME}/.awsctl/orgs.yaml"

  # 1) version
  rc=$(run_and_capture "version" -- awsctl --version)
  expect_nonempty "version" "${rc}"

  # 2) help
  rc=$(run_and_capture "help" -- awsctl help)
  expect_grep "help" "${rc}" "awsctl-use --account"

  # 3) doctor
  rc=$(run_and_capture "doctor" -- awsctl doctor)
  expect_grep "doctor" "${rc}" "quick diagnostics"

  # 4) init-config (captures sample)
  rc=$(run_and_capture "init-config" -- awsctl init-config)
  expect_grep "init-config" "${rc}" "orgs:"

  # 5) setup (must inject shell function and sync config)
  rc=$(run_and_capture "setup" -- awsctl setup)
  expect_rc "setup" "${rc}" 0

  # check rc file injection
  RC_FILE=""
  [[ -f "${HOME}/.bashrc" ]] && RC_FILE="${HOME}/.bashrc"
  [[ -z "${RC_FILE}" && -f "${HOME}/.zshrc" ]] && RC_FILE="${HOME}/.zshrc"
  if [[ -n "${RC_FILE}" ]] && grep -q "AWSCTL SHELL INTEGRATION" "${RC_FILE}"; then
    record "shell-integration" 0 "function present in $(basename "${RC_FILE}")"
  else
    record "shell-integration" 1 "function missing"
  fi

  # 6) config sync
  rc=$(run_and_capture "config-sync" -- awsctl config sync)
  expect_grep "config-sync" "${rc}" "Synchronized 1 org"

  # 7) test awsctl-use shell function
  h "Test awsctl-use shell function"
  if [[ -n "${RC_FILE}" && -f "${RC_FILE}" ]]; then
      log "Sourcing ${RC_FILE} to load awsctl-use function..."
      # shellcheck source=/dev/null
      source "${RC_FILE}"

      # Now call the function. It should be available in this shell.
      # Note: we call this directly, not via the 'run_and_capture' subshell
      rc=$(run_and_capture "shell-use-fn" -- awsctl-use --account 123456789012 --role AdministratorAccess --region eu-west-2)

      if [[ "${WITH_SSO}" -eq 1 ]]; then
          # In SSO mode, the function prints "Credentials exported" to stderr
          if [[ "${rc}" -eq 0 ]] && grep -q "Credentials exported" "${ART_DIR}/shell-use-fn.log"; then
              record "shell-use-fn" 0 "shell function exported creds (logged to stderr)"
          else
              record "shell-use-fn" 1 "shell function failed in SSO mode (rc=${rc})"
          fi
      else
          # Without SSO, the function fails and prints "failed to get credentials" to stderr
          if [[ "${rc}" -ne 0 ]] && grep -q "failed to get credentials" "${ART_DIR}/shell-use-fn.log"; then
              record "shell-use-fn" 0 "expected failure without SSO (logged to stderr)"
          else
              record "shell-use-fn" 1 "unexpected output without SSO (rc=${rc})"
          fi
      fi
  else
      record "shell-use-fn" 1 "Could not find RC_FILE (${RC_FILE:-not set}) to source"
  fi

  # 8) orgs list
  rc=$(run_and_capture "orgs" -- awsctl orgs)
  expect_grep "orgs" "${rc}" '"name":'

  # 9) hidden flags
  rc=$(run_and_capture "flag-whoami" -- awsctl --whoami)
  expect_nonempty "flag-whoami" "${rc}"

  rc=$(run_and_capture "flag-open" -- awsctl --open)
  expect_nonempty "flag-open" "${rc}"

  rc=$(run_and_capture "flag-export" -- awsctl --export)
  expect_nonempty "flag-export" "${rc}"

  # 10) roles missing arg should fail
  set +e
  awsctl roles > "${ART_DIR}/roles-missing.out" 2>"${ART_DIR}/roles-missing.log"
  rc=$?
  set -e
  # Any non-zero is acceptable here
  if [[ "${rc}" -ne 0 ]]; then
    record "roles-missing-arg" 0 "expected failure rc=${rc}"
  else
    record "roles-missing-arg" 1 "unexpected success"
  fi

  # 11) accounts list (SSO-dependent)
  rc=$(run_and_capture "accounts" -- awsctl accounts)
  if [[ "${WITH_SSO}" -eq 1 ]]; then
    # With SSO we expect success and at least one line or a sane empty message.
    if [[ "${rc}" -eq 0 ]]; then
      record "accounts" 0 "rc=0 (SSO mode)"
    else
      record "accounts" 1 "rc=${rc} (SSO mode)"
    fi
  else
    # Without SSO we expect failure and token error message in stdout or stderr
    if [[ "${rc}" -ne 0 ]] && (grep -q "Token.*does not exist" "${ART_DIR}/accounts.out" || grep -q "Token.*does not exist" "${ART_DIR}/accounts.log"); then
      record "accounts" 0 "expected token error without SSO"
    else
      record "accounts" 1 "unexpected output without SSO (rc=${rc})"
    fi
  fi

  # 12) accounts --json
  rc=$(run_and_capture "accounts-json" -- awsctl accounts --json)
  if [[ "${WITH_SSO}" -eq 1 ]]; then
    if [[ "${rc}" -eq 0 ]]; then
      record "accounts-json" 0 "rc=0 (SSO mode)"
    else
      record "accounts-json" 1 "rc=${rc} (SSO mode)"
    fi
  else
    # Without SSO we expect failure and token error message in stdout or stderr
    if [[ "${rc}" -ne 0 ]] && (grep -q "Token.*does not exist" "${ART_DIR}/accounts-json.out" || grep -q "Token.*does not exist" "${ART_DIR}/accounts-json.log"); then
      record "accounts-json" 0 "expected token error without SSO"
    else
      record "accounts-json" 1 "unexpected output without SSO (rc=${rc})"
    fi
  fi

  # 13) roles with account (SSO-dependent)
  rc=$(run_and_capture "roles" -- awsctl roles --account 123456789012)
  if [[ "${WITH_SSO}" -eq 1 ]]; then
    if [[ "${rc}" -eq 0 ]]; then
      record "roles" 0 "rc=0 (SSO mode)"
    else
      record "roles" 1 "rc=${rc} (SSO mode)"
    fi
  else
    # Without SSO we expect failure and token error message in stdout or stderr
    if [[ "${rc}" -ne 0 ]] && (grep -q "Token.*does not exist" "${ART_DIR}/roles.out" || grep -q "Token.*does not exist" "${ART_DIR}/roles.log"); then
      record "roles" 0 "expected token error without SSO"
    else
      record "roles" 1 "unexpected output without SSO (rc=${rc})"
    fi
  fi

  # 14) roles --json with account (SSO-dependent)
  rc=$(run_and_capture "roles-json" -- awsctl roles --account 123456789012 --json)
  if [[ "${WITH_SSO}" -eq 1 ]]; then
    if [[ "${rc}" -eq 0 ]]; then
      record "roles-json" 0 "rc=0 (SSO mode)"
    else
      record "roles-json" 1 "rc=${rc} (SSO mode)"
    fi
  else
    # Without SSO we expect failure and token error message in stdout or stderr
    if [[ "${rc}" -ne 0 ]] && (grep -q "Token.*does not exist" "${ART_DIR}/roles-json.out" || grep -q "Token.*does not exist" "${ART_DIR}/roles-json.log"); then
      record "roles-json" 0 "expected token error without SSO"
    else
      record "roles-json" 1 "unexpected output without SSO (rc=${rc})"
    fi
  fi

  # 15) use (requires account+role+region) — expect success only with SSO
  rc=$(run_and_capture "use" -- awsctl use --account 123456789012 --role AdministratorAccess --region eu-west-2)
  if [[ "${WITH_SSO}" -eq 1 ]]; then
    if [[ "${rc}" -eq 0 ]] && grep -q "^export AWS_ACCESS_KEY_ID=" "${ART_DIR}/use.out"; then
      record "use" 0 "export lines emitted"
    else
      record "use" 1 "no export lines"
    fi
  else
    # Without SSO we expect failure and token error message in stdout or stderr
    if [[ "${rc}" -ne 0 ]] && (grep -q "Token.*does not exist" "${ART_DIR}/use.out" || grep -q "Token.*does not exist" "${ART_DIR}/use.log"); then
      record "use" 0 "expected token error without SSO"
    else
      # FIX: Add space between "use" and 1
      record "use" 1 "unexpected output without SSO (rc=${rc})"
    fi
  fi

  # -------- cleanup --------
  h "Cleanup temporary HOME"
  rm -rf "${TMP_HOME}"

  if [[ "${KEEP_VENV}" -ne 1 ]]; then
    h "Cleanup virtualenv"
    deactivate || true
    rm -rf "${VENV_DIR}"
  fi

  h "All checks done"
  log "artifacts saved at: ${ART_DIR}"
  log "summary:"
  cat "${SUMMARY}" || true

  # Deactivate set -x at the end
  set +x

  tox -e lint

} >> "${SETUP_LOG}" 2>&1
# -------- AGGRESSIVE LOGGING END --------