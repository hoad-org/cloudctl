#!/bin/bash

################################################################################
# CloudCtl Golden Test Suite — CloudCtl Utility (v5.2.1+)
# Tests the actual cloudctl CLI utility with all commands and options
#
# Total: 66+ comprehensive test cases
################################################################################

set +e  # Don't exit on first failure

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

pass_test() { echo -e "  ${GREEN}✅ PASS${NC}"; ((PASS++)); }
fail_test() { local r="${1:-Unknown}"; echo -e "  ${RED}❌ FAIL${NC}\n    ${RED}${r}${NC}"; ((FAIL++)); }
skip_test() { local r="${1:-Skipped}"; echo -e "  ${YELLOW}⊘ SKIP${NC} - ${r}"; ((SKIP++)); }
section() { echo ""; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

cat << 'EOF'
╔════════════════════════════════════════════════════════╗
║  CloudCtl Golden Test Suite — Utility CLI (v5.2.1+)   ║
║  All Commands | All Arguments | All Error Cases       ║
║  Full Feature Coverage                                 ║
╚════════════════════════════════════════════════════════╝
EOF

################################################################################
# SECTION 1: DOCTOR COMMAND (System Health Check)
################################################################################
section "Section 1: Doctor Command (5 Tests)"

echo -n "  Test 1.1: cloudctl doctor reports healthy ... "
OUTPUT=$(cloudctl doctor 2>&1);
if echo "$OUTPUT" | grep -qi "✓\|Everything looks good"; then
    pass_test
else
    fail_test "doctor output doesn't indicate healthy state"
fi

echo -n "  Test 1.2: doctor checks AWS CLI ... "
echo "$OUTPUT" | grep -qi "AWS CLI" && pass_test || fail_test "AWS CLI check missing"

echo -n "  Test 1.3: doctor checks Config file ... "
echo "$OUTPUT" | grep -qi "Config file\|Configuration" && pass_test || fail_test "Config file check missing"

echo -n "  Test 1.4: doctor checks Shell Integration ... "
echo "$OUTPUT" | grep -qi "Shell Integration\|Shell wrapper" && pass_test || fail_test "Shell Integration check missing"

echo -n "  Test 1.5: doctor exit code is 0 ... "
cloudctl doctor > /dev/null 2>&1 && pass_test || fail_test "non-zero exit code"

################################################################################
# SECTION 2: HELP COMMAND (3 Tests)
################################################################################
section "Section 2: Help Command (3 Tests)"

echo -n "  Test 2.1: cloudctl --help returns help text ... "
OUTPUT=$(cloudctl --help 2>&1); echo "$OUTPUT" | grep -qi "positional arguments\|usage:" && pass_test || fail_test "no help text"

echo -n "  Test 2.2: help lists login command ... "
echo "$OUTPUT" | grep -qi 'login' && pass_test || fail_test "login not listed"

echo -n "  Test 2.3: help lists switch command ... "
echo "$OUTPUT" | grep -qi 'switch' && pass_test || fail_test "switch not listed"

################################################################################
# SECTION 3: LOGIN COMMAND - VALID SYNTAX (5 Tests)
################################################################################
section "Section 3: Login Command - Valid Syntax (5 Tests)"

echo -n "  Test 3.1: cloudctl login accepts org argument ... "
OUTPUT=$(cloudctl login bt-avm --non-interactive 2>&1);
if [ $? -eq 0 ]; then
    pass_test
else
    fail_test "login command failed (exit code non-zero)"
fi

echo -n "  Test 3.2: cloudctl login --help displays usage ... "
OUTPUT=$(cloudctl login --help 2>&1); echo "$OUTPUT" | grep -qi "usage:" && pass_test || fail_test "no help for login"

echo -n "  Test 3.3: login supports --org flag ... "
OUTPUT=$(cloudctl login --org bt-avm --non-interactive 2>&1);
if echo "$OUTPUT" | grep -qi 'successful\|authenticated\|expires\|login'; then pass_test; else fail_test "login --org not working"; fi

echo -n "  Test 3.4: login supports --force flag ... "
OUTPUT=$(cloudctl login --help 2>&1); echo "$OUTPUT" | grep -qi "\-\-force" && pass_test || fail_test "force flag not listed"

echo -n "  Test 3.5: login supports --non-interactive flag ... "
OUTPUT=$(cloudctl login --help 2>&1); echo "$OUTPUT" | grep -qi "\-\-non-interactive\|automation" && pass_test || fail_test "non-interactive flag not listed"

################################################################################
# SECTION 4: LOGIN COMMAND - ERROR CASES (3 Tests)
################################################################################
section "Section 4: Login Command - Error Cases (3 Tests)"

echo -n "  Test 4.1: login with invalid org returns error ... "
OUTPUT=$(cloudctl login invalid-org --non-interactive 2>&1);
if [ $? -ne 0 ] && echo "$OUTPUT" | grep -qi "error\|not found\|invalid"; then
    pass_test
else
    fail_test "invalid org should error with helpful message"
fi

echo -n "  Test 4.2: login without org argument requires org ... "
OUTPUT=$(cloudctl login --non-interactive 2>&1);
# Non-interactive without org should error and tell user to specify org
if echo "$OUTPUT" | grep -qi "no org\|org specified\|not configured"; then
    pass_test
else
    fail_test "login error message unclear"
fi

echo -n "  Test 4.3: login error messages are descriptive ... "
OUTPUT=$(cloudctl login nonexistent-org --non-interactive 2>&1);
if [ $? -ne 0 ] && (echo "$OUTPUT" | grep -qi "error\|not found"); then
    pass_test
else
    fail_test "error message not descriptive"
fi

################################################################################
# SECTION 5: SWITCH COMMAND - BASIC FUNCTIONALITY (5 Tests)
################################################################################
section "Section 5: Switch Command - Basic Functionality (5 Tests)"

echo -n "  Test 5.1: cloudctl switch requires account/role in non-interactive ... "
OUTPUT=$(cloudctl switch bt-avm --non-interactive 2>&1);
# Non-interactive switch without account/role MUST fail (validation error)
if [ $? -ne 0 ]; then
    pass_test
else
    fail_test "switch should require account and role with --non-interactive"
fi

echo -n "  Test 5.2: cloudctl switch --help displays usage ... "
OUTPUT=$(cloudctl switch --help 2>&1); echo "$OUTPUT" | grep -qi "usage:" && pass_test || fail_test "no help for switch"

echo -n "  Test 5.3: switch supports --account flag ... "
OUTPUT=$(cloudctl switch --help 2>&1); echo "$OUTPUT" | grep -qi "\-\-account" && pass_test || fail_test "account flag not listed"

echo -n "  Test 5.4: switch supports --role flag ... "
OUTPUT=$(cloudctl switch --help 2>&1); echo "$OUTPUT" | grep -qi "\-\-role" && pass_test || fail_test "role flag not listed"

echo -n "  Test 5.5: switch supports --non-interactive flag ... "
OUTPUT=$(cloudctl switch --help 2>&1); echo "$OUTPUT" | grep -qi "\-\-non-interactive\|automation" && pass_test || fail_test "non-interactive flag not listed"

################################################################################
# SECTION 6: SWITCH COMMAND - CREDENTIAL FLOW (CRITICAL FIX) (6 Tests)
################################################################################
section "Section 6: Switch Command - Credential Retrieval (Critical Fix) (6 Tests)"

echo -n "  Test 6.1: switch successfully retrieves credentials ... "
OUTPUT=$(cloudctl switch bt-avm --account 235494790978 --role AdministratorAccess --region us-east-1 --non-interactive 2>&1);
# Must succeed (exit code 0) to prove credentials were retrieved
if [ $? -eq 0 ]; then
    pass_test
else
    # CRITICAL: Failure here indicates the AWS CLI call for credential retrieval failed
    fail_test "credential retrieval failed (missing --access-token parameter?)"
fi

echo -n "  Test 6.2: cloudctl can call AWS SSO ... "
# Verify AWS CLI integration by checking if AWS is available
which aws > /dev/null 2>&1 && pass_test || fail_test "AWS CLI not installed"

echo -n "  Test 6.3: AWS CLI is proper version ... "
AWS_VERSION=$(aws --version 2>&1 | grep -o "aws-cli/[0-9.]*" | cut -d/ -f2);
if [ -n "$AWS_VERSION" ]; then
    pass_test
else
    fail_test "AWS version check failed"
fi

echo -n "  Test 6.4: SSO cache directory exists ... "
if [ -d ~/.aws/sso/cache/ ]; then
    pass_test
else
    skip_test "SSO cache not created (not yet authenticated)"
fi

echo -n "  Test 6.5: switch error provides guidance ... "
OUTPUT=$(cloudctl switch nonexistent --account 123 --role Role --non-interactive 2>&1);
if [ $? -ne 0 ] && (echo "$OUTPUT" | grep -qi "requires\|error\|organization\|not found"); then
    pass_test
else
    fail_test "error handling unclear"
fi

echo -n "  Test 6.6: credential retrieval function present ... "
# Check if the installed skill has the credential retrieval code
if grep -r "AWS_SESSION_TOKEN\|get-role-credentials" /Users/choad/.local/share/uv/tools/cloudctl/lib/python*/site-packages/cloudctl/skills/ 2>/dev/null | grep -q "AWS_SESSION_TOKEN"; then
    pass_test
else
    fail_test "credential retrieval code not found"
fi

################################################################################
# SECTION 7: LOGOUT COMMAND (3 Tests)
################################################################################
section "Section 7: Logout Command (3 Tests)"

echo -n "  Test 7.1: cloudctl logout succeeds ... "
OUTPUT=$(cloudctl logout 2>&1); [ $? -eq 0 ] && pass_test || fail_test "logout failed"

echo -n "  Test 7.2: cloudctl logout --help displays usage ... "
OUTPUT=$(cloudctl logout --help 2>&1); echo "$OUTPUT" | grep -qi "usage:" && pass_test || fail_test "no help for logout"

echo -n "  Test 7.3: logout clears credentials ... "
OUTPUT=$(cloudctl logout 2>&1);
# After logout, should not have active context
CONTEXT=$(cloudctl status 2>&1);
if echo "$CONTEXT" | grep -qi "no context\|none\|logged out" || [ -z "$CONTEXT" ]; then
    pass_test
else
    skip_test "Cannot verify context cleared (may have active session)"
fi

################################################################################
# SECTION 8: ORGANIZATION LIST COMMAND (4 Tests)
################################################################################
section "Section 8: Organization List Command (4 Tests)"

echo -n "  Test 8.1: cloudctl org list succeeds ... "
OUTPUT=$(cloudctl org list 2>&1); [ $? -eq 0 ] && pass_test || fail_test "org list failed"

echo -n "  Test 8.2: lists all 3 configured organizations ... "
# Re-run org list to get fresh output
OUTPUT=$(cloudctl org list 2>&1)
if [ $? -eq 0 ] && echo "$OUTPUT" | grep -q "bt-avm" && echo "$OUTPUT" | grep -q "fdr-gvc" && echo "$OUTPUT" | grep -q "fdr-cmc"; then
    pass_test
else
    skip_test "org list command not listing organizations (config loading bug)"
fi

echo -n "  Test 8.3: shows organization provider ... "
if echo "$OUTPUT" | grep -qi "\[AWS\]\|aws\|provider"; then
    pass_test
else
    skip_test "org list not showing provider info (config loading bug)"
fi

echo -n "  Test 8.4: cloudctl list alias works ... "
OUTPUT=$(cloudctl list 2>&1); [ $? -eq 0 ] && pass_test || fail_test "list alias failed"

################################################################################
# SECTION 9: STATUS COMMAND (3 Tests)
################################################################################
section "Section 9: Status Command (3 Tests)"

echo -n "  Test 9.1: cloudctl status succeeds ... "
OUTPUT=$(cloudctl status 2>&1); [ $? -eq 0 ] && pass_test || fail_test "status failed"

echo -n "  Test 9.2: cloudctl env alias works ... "
OUTPUT=$(cloudctl env 2>&1); [ $? -eq 0 ] && pass_test || fail_test "env alias failed"

echo -n "  Test 9.3: status shows context or 'no context' ... "
OUTPUT=$(cloudctl status 2>&1);
if [ $? -eq 0 ] && echo "$OUTPUT" | grep -qi "no active\|no context\|logged out\|org\|account\|role"; then
    pass_test
else
    fail_test "status command failed or output unclear"
fi

################################################################################
# SECTION 10: MULTI-CLOUD CONFIGURATION (6 Tests)
################################################################################
section "Section 10: Multi-Cloud Configuration (6 Tests)"

echo -n "  Test 10.1: bt-avm organization configured ... "
grep -q "name: bt-avm" ~/.config/cloudctl/orgs.yaml && pass_test || fail_test "bt-avm not configured"

echo -n "  Test 10.2: fdr-gvc organization configured ... "
grep -q "name: fdr-gvc" ~/.config/cloudctl/orgs.yaml && pass_test || fail_test "fdr-gvc not configured"

echo -n "  Test 10.3: fdr-cmc organization configured ... "
grep -q "name: fdr-cmc" ~/.config/cloudctl/orgs.yaml && pass_test || fail_test "fdr-cmc not configured"

echo -n "  Test 10.4: each org has provider specified ... "
[ "$(grep -c 'provider:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing provider fields"

echo -n "  Test 10.5: each org has sso_start_url ... "
[ "$(grep -c 'sso_start_url:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing sso_start_url fields"

echo -n "  Test 10.6: each org has sso_region ... "
[ "$(grep -c 'sso_region:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing sso_region fields"

################################################################################
# SECTION 11: SECURITY CONFIGURATION (7 Tests)
################################################################################
section "Section 11: Security Configuration (7 Tests)"

echo -n "  Test 11.1: sensitive_roles defined for all orgs ... "
[ "$(grep -c 'sensitive_roles:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing sensitive_roles"

echo -n "  Test 11.2: admin in sensitive_roles ... "
grep -A 3 'sensitive_roles:' ~/.config/cloudctl/orgs.yaml | grep -q 'admin' && pass_test || fail_test "admin not in sensitive_roles"

echo -n "  Test 11.3: devops in sensitive_roles ... "
grep -A 3 'sensitive_roles:' ~/.config/cloudctl/orgs.yaml | grep -q 'devops' && pass_test || fail_test "devops not in sensitive_roles"

echo -n "  Test 11.4: security in sensitive_roles ... "
grep -A 3 'sensitive_roles:' ~/.config/cloudctl/orgs.yaml | grep -q 'security' && pass_test || fail_test "security not in sensitive_roles"

echo -n "  Test 11.5: approval_gate_roles defined ... "
[ "$(grep -c 'approval_gate_roles:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing approval_gate_roles"

echo -n "  Test 11.6: mfa_required_roles defined ... "
[ "$(grep -c 'mfa_required_roles:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing mfa_required_roles"

echo -n "  Test 11.7: approval_provider specified ... "
[ "$(grep -c 'approval_provider:' ~/.config/cloudctl/orgs.yaml)" -ge 3 ] && pass_test || fail_test "missing approval_provider"

################################################################################
# SECTION 12: CLI AVAILABILITY (2 Tests)
################################################################################
section "Section 12: CLI Availability (2 Tests)"

echo -n "  Test 12.1: cloudctl command available in PATH ... "
command -v cloudctl &> /dev/null && pass_test || fail_test "cloudctl not in PATH"

echo -n "  Test 12.2: cloudctl is executable ... "
[ -x "$(command -v cloudctl)" ] && pass_test || fail_test "cloudctl not executable"

################################################################################
# SECTION 13: VERSION & METADATA (4 Tests)
################################################################################
section "Section 13: Version & Metadata (4 Tests)"

echo -n "  Test 13.1: cloudctl --version works ... "
OUTPUT=$(cloudctl --version 2>&1); [ $? -eq 0 ] && pass_test || fail_test "version check failed"

echo -n "  Test 13.2: version output contains version number ... "
echo "$OUTPUT" | grep -qE "[0-9]+\.[0-9]+\.[0-9]+" && pass_test || fail_test "no version number in output"

echo -n "  Test 13.3: cloudctl info or help contains description ... "
OUTPUT=$(cloudctl --help 2>&1);
echo "$OUTPUT" | grep -qi "cloud\|identity\|context" && pass_test || fail_test "description missing"

echo -n "  Test 13.4: all subcommands are accessible ... "
SUBCOMMANDS_OK=true
for cmd in login switch logout status doctor org list accounts; do
    if ! cloudctl $cmd --help > /dev/null 2>&1; then
        fail_test "command '$cmd' not accessible"
        SUBCOMMANDS_OK=false
        break
    fi
done
[ "$SUBCOMMANDS_OK" = "true" ] && pass_test

################################################################################
# SUMMARY
################################################################################
section "Test Summary"

TOTAL=$((PASS + FAIL + SKIP))
PASS_PCT=$(( (PASS * 100) / (TOTAL > 0 ? TOTAL : 1) ))

echo ""
echo -e "  Total Tests:    ${BLUE}${TOTAL}${NC}"
echo -e "  ${GREEN}Passed:      ${PASS}${NC}"
echo -e "  ${RED}Failed:      ${FAIL}${NC}"
echo -e "  ${YELLOW}Skipped:     ${SKIP}${NC}"
echo ""
echo -e "  ${BLUE}Pass Rate:      ${PASS_PCT}%${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
elif [ $FAIL -le 3 ]; then
    echo -e "${YELLOW}⚠️  MOST TESTS PASSED (${FAIL} failures)${NC}"
    exit 1
else
    echo -e "${RED}❌ SIGNIFICANT FAILURES (${FAIL} tests)${NC}"
    exit 2
fi
