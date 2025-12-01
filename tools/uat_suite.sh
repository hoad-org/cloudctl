#!/bin/bash
# awsctl User Acceptance Test Suite (v1.6.5+)
# Tests the full lifecycle: Setup -> Login -> Switch -> Exec -> Logout

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# 0. Setup & Wrapper Definition
# -----------------------------------------------------------------------------
echo -e "${CYAN}--- [0/8] Initializing Test Environment ---${NC}"

# We must define the function locally to test the "Trojan Horse" logic
# within this script's scope.
if ! command -v _awsctl_bin &> /dev/null; then
    echo -e "${RED}Error: _awsctl_bin not found. Is awsctl installed via pipx?${NC}"
    exit 1
fi

# Define the wrapper exactly as installed
awsctl() {
    local outcome
    outcome=$(_awsctl_bin "$@" --check-strategy 2>/dev/null)
    local check_rc=$?

    if [[ $check_rc -ne 0 ]] || [[ -z "$outcome" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

    if [[ "$outcome" == "EXEC" ]]; then
        _awsctl_bin "$@"
        return $?
    fi

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

# Config Check
if [ ! -f ~/.awsctl/orgs.yaml ]; then
    echo -e "${YELLOW}Config missing. Running setup...${NC}"
    awsctl setup
fi

# -----------------------------------------------------------------------------
# 1. Configuration & Inputs
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [1/8] Test Configuration ---${NC}"
echo "We need a target to test switching and execution."

# Try to grep defaults from existing cache to save typing
DEFAULT_ORG=$(jq -r '.startUrl' ~/.aws/sso/cache/*.json 2>/dev/null | head -n1 | cut -d/ -f3 | cut -d- -f1)
read -p "Target Organization [${DEFAULT_ORG:-myorg}]: " TARGET_ORG
TARGET_ORG=${TARGET_ORG:-${DEFAULT_ORG:-myorg}}

echo -e "Fetching accounts for ${TARGET_ORG}..."

# [FIX] Soft-fail: Try to list accounts. If not logged in, suppress error and continue.
if _awsctl_bin list accounts > /tmp/awsctl_accts.txt 2>/dev/null; then
    head -n 5 /tmp/awsctl_accts.txt
else
    echo -e "${YELLOW}⚠  Not logged in yet. Skipping account list helper.${NC}"
    echo -e "${YELLOW}   (You will login automatically in Step 4)${NC}"
fi

read -p "Target Account ID/Name: " TARGET_ACCT
read -p "Target Role [AdministratorAccess]: " TARGET_ROLE
TARGET_ROLE=${TARGET_ROLE:-AdministratorAccess}
read -p "Target Region [eu-west-2]: " TARGET_REGION
TARGET_REGION=${TARGET_REGION:-eu-west-2}

# -----------------------------------------------------------------------------
# 2. System Health
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [2/8] System Diagnostics ---${NC}"
awsctl --version
awsctl doctor
echo -e "${GREEN}✔ Doctor passed${NC}"

# -----------------------------------------------------------------------------
# 3. Discovery Commands
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [3/8] Discovery Features ---${NC}"
echo "Listing Orgs:"
# [FIX] Redirect stderr to stdout for grep
awsctl list orgs 2>&1

echo "Listing Accounts (JSON Check):"
# We allow this to fail if not logged in, as we test real login in Step 4
if awsctl list accounts --json > /dev/null 2>&1; then
    awsctl list accounts --json | head -n 3
    echo -e "${GREEN}✔ Lists functioning${NC}"
else
    echo -e "${YELLOW}⚠ Skipping list check (Not logged in)${NC}"
fi

# -----------------------------------------------------------------------------
# 4. Authentication (Login + Switch Chain)
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [4/8] Smart Login (Chain) ---${NC}"
echo "Testing: awsctl login --org ... --account ... (The Dream Workflow)"

# This runs the EVAL strategy. If successful, variables are set in THIS script.
awsctl login --org "$TARGET_ORG" --account "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION"

if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
    echo -e "${RED}✘ Failed: Env vars not exported to shell!${NC}"
    exit 1
fi
echo -e "${GREEN}✔ Login Chain successful. Credentials active in memory.${NC}"

# -----------------------------------------------------------------------------
# 5. Status & Environment
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [5/8] Status & Context ---${NC}"
awsctl status
echo -e "\nChecking env command:"
awsctl env | grep "AWS_ACCESS_KEY_ID"
echo -e "${GREEN}✔ Context Verified${NC}"

# -----------------------------------------------------------------------------
# 6. Execution (One-Shot)
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [6/8] Remote Execution (exec) ---${NC}"
echo "Running 'aws sts get-caller-identity' inside target account..."
awsctl exec --account "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION" -- aws sts get-caller-identity --query Arn --output text
echo -e "${GREEN}✔ Exec successful${NC}"

# -----------------------------------------------------------------------------
# 7. Smart Toggling
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [7/8] Context Toggling ---${NC}"
echo "Switching to previous context (-)..."
# We need a history to toggle. Let's fake a switch first.
awsctl switch "$TARGET_ACCT" --role "$TARGET_ROLE" --region "$TARGET_REGION" > /dev/null
awsctl switch -
echo -e "${GREEN}✔ Toggle successful${NC}"

# -----------------------------------------------------------------------------
# 8. Cleanup
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}--- [8/8] Cleanup ---${NC}"
awsctl cache-clear
echo "Logging out (clearing vars)..."
awsctl logout

if [[ -n "$AWS_ACCESS_KEY_ID" ]]; then
    echo -e "${RED}✘ Logout failed to clear variables!${NC}"
    exit 1
fi

echo -e "\n${GREEN}✨ ALL SYSTEMS GO. Release v1.9.2+ is fully operational. ✨${NC}"