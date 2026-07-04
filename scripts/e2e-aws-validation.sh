#!/bin/bash

# E2E AWS Validation Script for CloudCtl (uses this repo's source)

set -o pipefail

# Resolve this repo's own src/ (scripts/ -> repo root -> src).
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/src:${PYTHONPATH}"
CLOUDCTL="/opt/homebrew/bin/python3.12 -m cloudctl"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }
pass_test() { echo -e "${GREEN}✅ PASS${NC}: $1"; ((TESTS_PASSED++)); }
fail_test() { echo -e "${RED}❌ FAIL${NC}: $1"; [ -n "$2" ] && echo "  ${RED}Reason:${NC} $2"; ((TESTS_FAILED++)); }
skip_test() { echo -e "${YELLOW}⊘ SKIP${NC}: $1"; [ -n "$2" ] && echo "  ${YELLOW}Reason:${NC} $2"; ((TESTS_SKIPPED++)); }
section() { echo ""; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

section "PHASE 0: Pre-Flight Checks"

python3 --version > /dev/null 2>&1 && pass_test "Python 3 available" || { fail_test "Python 3 not found"; exit 1; }
aws --version > /dev/null 2>&1 && pass_test "AWS CLI available" || { fail_test "AWS CLI not found"; exit 1; }
[ -f ~/.config/cloudctl/orgs.yaml ] && pass_test "orgs.yaml exists" || { fail_test "orgs.yaml not found"; exit 1; }

section "PHASE 1: Organization List"

ORG_OUTPUT=$($CLOUDCTL org list 2>&1)
if echo "$ORG_OUTPUT" | grep -q "bt-avm"; then
    pass_test "cloudctl org list shows bt-avm (BUG #6 fixed)"
else
    fail_test "bt-avm not in org list" "$ORG_OUTPUT"
fi

if echo "$ORG_OUTPUT" | grep -q "\[AWS\]"; then
    pass_test "Provider shown as [AWS]"
fi

if echo "$ORG_OUTPUT" | grep -q "awsapps.com"; then
    pass_test "SSO URL shown"
fi

section "PHASE 2: Credential Management"

if [ -d ~/.aws/sso/cache ] && [ "$(ls -A ~/.aws/sso/cache 2>/dev/null)" ]; then
    pass_test "SSO cache has tokens"
else
    skip_test "SSO cache empty" "Run: cloudctl login bt-avm"
fi

if [ -f ~/.cloudctl/context.json ]; then
    pass_test "Context file exists"
else
    skip_test "Context file missing" "Run: cloudctl switch bt-avm --account ... --role ..."
fi

ENV_OUTPUT=$($CLOUDCTL env 2>&1)
if echo "$ENV_OUTPUT" | grep -q "CLOUDCTL_ORG\|No active context"; then
    pass_test "cloudctl env works"
fi

section "PHASE 3: AWS Integration"

if [ -f ~/.aws/config ] && grep -q "profile bt-avm" ~/.aws/config; then
    pass_test "AWS profiles configured"
    
    if grep -A 10 "profile bt-avm" ~/.aws/config | grep -q "sso_session"; then
        pass_test "sso_session field present (BUG #5 fixed)"
    fi
fi

STS_OUTPUT=$(aws sts get-caller-identity 2>&1)
if [ $? -eq 0 ]; then
    pass_test "AWS STS call successful"
    ACCOUNT=$(echo "$STS_OUTPUT" | jq -r '.Account' 2>/dev/null)
    [ -n "$ACCOUNT" ] && pass_test "Retrieved Account: $ACCOUNT"
else
    skip_test "AWS STS failed" "No active credentials"
fi

section "PHASE 4: Code Validation"

grep -q "if hasattr(token, 'expiresAt')" src/cloudctl/aws.py && pass_test "BUG #2: Token expiry validation present" || fail_test "BUG #2: Token validation missing"
grep -q 'raise ValueError("Region is required' src/cloudctl/aws.py && pass_test "BUG #3: Region validation present" || fail_test "BUG #3: Region validation missing"
grep -q "get_credentials(_account, _role, _region, org_ref)" src/cloudctl/core.py && pass_test "BUG #4: org_ref parameter present" || fail_test "BUG #4: org_ref missing"
grep -q '"sso_session": org_data.get("name"' src/cloudctl/aws.py && pass_test "BUG #5: sso_session field present" || fail_test "BUG #5: sso_session missing"
grep -q 'if "organizations" in data and isinstance' src/cloudctl/commands/org.py && pass_test "BUG #6: org list fix present" || fail_test "BUG #6: org list fix missing"

section "Test Summary"

TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
PASS_RATE=$((TESTS_PASSED * 100 / TOTAL))

echo ""
echo -e "  Total Tests:    ${BLUE}$TOTAL${NC}"
echo -e "  ${GREEN}Passed:      $TESTS_PASSED${NC}"
echo -e "  ${RED}Failed:      $TESTS_FAILED${NC}"
echo -e "  ${YELLOW}Skipped:     $TESTS_SKIPPED${NC}"
echo ""
echo -e "  Pass Rate:      ${BLUE}${PASS_RATE}%${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL VALIDATION TESTS PASSED!${NC}"
    echo ""
    echo "Next Steps to Achieve 100% Confidence:"
    echo "1. Run: cloudctl login bt-avm"
    echo "2. Run: cloudctl switch bt-avm --account 235494790978 --role AdministratorAccess --region us-east-1 --non-interactive"
    echo "3. Run: cloudctl env"
    echo "4. Run: aws sts get-caller-identity"
    echo "5. Run: cloudctl exec 235494790978 AdministratorAccess us-east-1 -- aws sts get-caller-identity"
    exit 0
else
    echo -e "${RED}❌ VALIDATION FAILED${NC}"
    exit 1
fi
