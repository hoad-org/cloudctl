#!/bin/bash
# -----------------------------------------------------------------------------
# awsctl Enterprise Acceptance Suite
# Verifies: v1.9.x Features, Shell Integration, JSON/Text Outputs, Exec modes
# -----------------------------------------------------------------------------
set -e

# --- Styling ---
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✔ PASS:${NC} $1"; }
fail() { echo -e "${RED}✘ FAIL:${NC} $1"; exit 1; }
info() { echo -e "\n${CYAN}${BOLD}>>> [Phase $1] $2${NC}"; }

# -----------------------------------------------------------------------------
# 0. Bootstrap & Wrapper Definition
# -----------------------------------------------------------------------------
info "0" "Bootstrapping Test Environment"

if ! command -v _awsctl_bin &> /dev/null; then
    fail "_awsctl_bin not found. Install via: pipx install ."
fi

# Define the Trojan Horse wrapper locally to simulate the user shell
awsctl() {
    local outcome
    outcome=$(_awsctl_bin "$@" --check-strategy 2>/dev/null)
    local check_rc=$?

    # Fallback / Error
    if [[ $check_rc -ne 0 ]] || [[ -z "$outcome" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    # Strategy: EXEC
    if [[ "$outcome" == "EXEC" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    # Strategy: EVAL
    if [[ "$outcome" == "EVAL" ]]; then
        local output
        output=$(_awsctl_bin "$@")
        local rc=$?
        if [[ $rc -eq 0 ]]; then
            eval "$output"
        else
            echo "$output"
        fi
        return $rc
    fi
    _awsctl_bin "$@"
}

# [FIX] Run setup in HEADLESS mode to generate config without prompting
AWSCTL_HEADLESS=1 awsctl setup > /dev/null
pass "Wrapper defined and config loaded"

# -----------------------------------------------------------------------------
# 1. Data Gathering (Interactive)
# -----------------------------------------------------------------------------
info "1" "Test Configuration"

# [FIX] Improved awk logic to handle '- name: myorg' correctly (print $3)
DEFAULT_ORG=$(grep -m1 "name:" ~/.awsctl/orgs.yaml | awk '{print $3}')
echo "Please provide details for a valid target to run tests against."
read -p "Target Org [${DEFAULT_ORG}]: " TARGET_ORG
TARGET_ORG=${TARGET_ORG:-$DEFAULT_ORG}

echo -e "${YELLOW}Priming cache to list accounts...${NC}"
# Allow failure if not logged in
awsctl login --org "$TARGET_ORG" > /dev/null 2>&1 || true

read -p "Target Account ID: " TARGET_ACCT
read -p "Target Role [AdministratorAccess]: " TARGET_ROLE
TARGET_ROLE=${TARGET_ROLE:-AdministratorAccess}
read -p "Target Region [eu-west-2]: " TARGET_REGION
TARGET_REGION=${TARGET_REGION:-eu-west-2}

# -----------------------------------------------------------------------------
# 2. Discovery & Formats
# -----------------------------------------------------------------------------
info "2" "Discovery Features"

# [FIX] Redirect stderr to stdout (2>&1) because tables are printed to stderr
if awsctl list orgs 2>&1 | grep -q "$TARGET_ORG"; then
    pass "list orgs (Text Table)"
else
    fail "list orgs failed to find $TARGET_ORG"
fi

# Test Account List (JSON goes to stdout, so no redirect needed)
if awsctl list accounts --json | grep -q "$TARGET_ACCT"; then
    pass "list accounts --json (Structured Output)"
else
    fail "list accounts --json failed"
fi

# [FIX] Redirect stderr to stdout
if awsctl list roles 2>&1 | grep -q "$TARGET_ROLE"; then
    pass "list roles (Text Table)"
else
    fail "list roles failed"
fi

# -----------------------------------------------------------------------------
# 3. Authentication Workflows
# -----------------------------------------------------------------------------
info "3" "Authentication Workflows"

# Test A: Explicit Switch
echo "Testing explicit switch..."
awsctl switch "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION"
if [[ "$AWS_ACCESS_KEY_ID" == "ASIA"* ]]; then
    pass "Explicit Switch (Shell Env Updated)"
else
    fail "Explicit Switch failed to export variables"
fi

# Test B: Smart Login Chain
echo "Testing 'Smart Login' chain (Login + Switch)..."
# Unset first to prove it works
unset AWS_ACCESS_KEY_ID
awsctl login --org "$TARGET_ORG" --account "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION"
if [[ "$AWS_ACCESS_KEY_ID" == "ASIA"* ]]; then
    pass "Smart Login Chain (Shell Env Updated)"
else
    fail "Smart Login Chain failed"
fi

# -----------------------------------------------------------------------------
# 4. Context & Toggling
# -----------------------------------------------------------------------------
info "4" "Context Management"

# [FIX] Redirect stderr to stdout for status checks
if awsctl status 2>&1 | grep -q "Active Role"; then
    pass "Status Dashboard (Flight Deck)"
else
    fail "Status command failed"
fi

# Verify Env Dump (goes to stdout)
if awsctl env | grep -q "export AWS_SESSION_TOKEN"; then
    pass "Env Dump (Dotfile generation)"
else
    fail "Env command failed"
fi

# Test Toggle (-)
# We define a "previous" by running a switch, then switching "back"
awsctl switch "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION" > /dev/null
awsctl switch -
if [[ "$AWS_ACCESS_KEY_ID" == "ASIA"* ]]; then
    pass "Context Toggling (-)"
else
    fail "Context toggle failed"
fi

# -----------------------------------------------------------------------------
# 5. Execution (One-Shot)
# -----------------------------------------------------------------------------
info "5" "Remote Execution (exec)"

# Test A: Context-Aware Exec (Uses currently switched credentials)
echo "Testing Context-Aware Exec (Implicit)..."
# exec prints command output to stdout
IDENTITY=$(awsctl exec -- aws sts get-caller-identity --query Account --output text)
if [[ "$IDENTITY" == "$TARGET_ACCT" ]]; then
    pass "Exec (Implicit Context)"
else
    fail "Exec (Implicit) failed. Expected $TARGET_ACCT, got $IDENTITY"
fi

# Test B: Explicit Flag Exec (Overrides context)
echo "Testing Explicit Flag Exec..."
IDENTITY=$(awsctl exec --account "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION" -- aws sts get-caller-identity --query Account --output text)
if [[ "$IDENTITY" == "$TARGET_ACCT" ]]; then
    pass "Exec (Explicit Flags)"
else
    fail "Exec (Explicit) failed."
fi

# -----------------------------------------------------------------------------
# 6. Operations & Cleanup
# -----------------------------------------------------------------------------
info "6" "Operations & Cleanup"

# Diagnostics (stderr)
if awsctl doctor 2>&1 | grep -q "Everything looks good"; then
    pass "Doctor (Diagnostics)"
else
    echo -e "${YELLOW}⚠ Doctor found issues (check output above), but proceeding.${NC}"
fi

# Cache Clearing
awsctl cache-clear
pass "Cache Clear"

# Logout
awsctl logout
if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
    pass "Logout (Variable Cleanup)"
else
    fail "Logout failed to clear variables"
fi

echo -e "\n${GREEN}${BOLD}✨ ENTERPRISE ACCEPTANCE TEST COMPLETE. v1.9.x IS READY. ✨${NC}"