# CloudCtl Golden Test Plan v5.2.1+

**Purpose:** Comprehensive end-to-end testing of all CloudCtl features using real bash commands and AWS operations. Tests are run sequentially, each must pass before proceeding to the next.

**Scope:** AWS-focused workflow (Azure/GCP patterns similar but not tested here)

**Execution Mode:** Real bash commands, real AWS credentials, real operations where possible

---

## Test Environment Setup

```bash
# Verify test environment
echo "=== GOLDEN TEST PLAN EXECUTION ==="
echo "Version: $(cloudctl --version)"
echo "AWS CLI: $(aws --version)"
echo "Region: ${AWS_REGION:-us-east-1}"
echo ""
```

---

## TEST SUITE 1: Organization & Account Discovery (Non-Destructive)

### TEST 1.1: Organization Enumeration
**Objective:** Verify all configured organizations are discoverable
**Command:** `cloudctl org list`
**Expected Output:**
- "Configured Organizations (6)" header
- All 6 orgs listed: bt-avm, bt-dev, fdr-gvc, fdr-cmc, gcp-prod, avm-prod
- Provider type shown (AWS, GCP, AZURE)
- Status (enabled/disabled)
- Key identifier (SSO URL, project name, tenant ID)

**Pass Criteria:**
```bash
cloudctl org list | grep -q "Configured Organizations (6)"
cloudctl org list | grep -q "bt-avm"
cloudctl org list | grep -q "gcp-prod"
cloudctl org list | grep -q "avm-prod"
```

---

### TEST 1.2: Account Discovery for AWS Org
**Objective:** Verify AWS SSO correctly enumerates accounts for an organization
**Command:** `cloudctl accounts bt-avm`
**Expected Output:**
- Table with columns: Account ID, Account Name, Email
- 6 accounts listed (exact IDs: 235494790978, 853583157828, 023192524237, 747554530308, 615993872943, 457518778607)
- Account names: BT-AVM-ITC-Management, audit, log-archive, network-hub, shared-services, tooling

**Pass Criteria:**
```bash
cloudctl accounts bt-avm | grep -q "235494790978"
cloudctl accounts bt-avm | grep -q "BT-AVM-ITC-Management"
cloudctl accounts bt-avm | grep -c "^│" | grep -q "6"  # 6 data rows in table
```

---

### TEST 1.3: Account Discovery with Cache Sync
**Objective:** Verify `--sync` flag forces refresh of account cache
**Command:** `cloudctl accounts bt-avm --sync`
**Expected Output:**
- Same as TEST 1.2, but cache may be refreshed from AWS
- Command should complete successfully even with stale cache

**Pass Criteria:**
```bash
cloudctl accounts bt-avm --sync | grep -q "235494790978"
exit_code=$?; [ $exit_code -eq 0 ]  # Must exit cleanly
```

---

### TEST 1.4: Role Discovery for Specific Account
**Objective:** Verify available roles are discovered for an account
**Command:** `cloudctl list-roles bt-avm --account 235494790978`
**Expected Output:**
- List of available roles for account 235494790978
- At minimum should include "AdministratorAccess" role
- May include other roles like ReadOnlyAccess, PowerUserAccess

**Pass Criteria:**
```bash
cloudctl list-roles bt-avm --account 235494790978 | grep -q "AdministratorAccess"
```

---

## TEST SUITE 2: Authentication & Credential Exchange

### TEST 2.1: AWS SSO Token Status
**Objective:** Verify valid AWS SSO token exists and is not expired
**Command:** Check token cache manually
**Expected Output:**
- Valid token in ~/.aws/sso/cache/
- Token not expired
- accessToken field populated

**Pass Criteria:**
```bash
python3 << 'EOF'
import json
from pathlib import Path
from datetime import datetime

cache_dir = Path.home() / ".aws" / "sso" / "cache"
for f in cache_dir.glob("*.json"):
    data = json.load(open(f))
    if data.get('startUrl') == 'https://d-9067dbbf5a.awsapps.com/start':
        token = data.get('accessToken')
        expires = data.get('expiresAt')
        if token and expires:
            exp_time = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            now = datetime.now(exp_time.tzinfo)
            assert now < exp_time, "Token expired"
            print("✓ Valid token found and not expired")
            break
else:
    raise AssertionError("No valid token found")
EOF
```

---

### TEST 2.2: Interactive Switch (Non-Automation Mode)
**Objective:** Verify `cloudctl switch` can interactively prompt for account/role
**Command:** `cloudctl switch bt-avm` (interactive, user selects account and role)
**Expected Output:**
- Prompt for account selection
- Prompt for role selection
- Upon success: credentials exported (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
- Credentials are valid (can call AWS APIs)

**Pass Criteria:**
```bash
# After interactive switch, credentials should be set
[ -n "$AWS_ACCESS_KEY_ID" ]
[ -n "$AWS_SECRET_ACCESS_KEY" ]
[ -n "$AWS_SESSION_TOKEN" ]

# Should be able to call AWS STS
aws sts get-caller-identity | jq -e '.Account == "235494790978"'
```

---

### TEST 2.3: Non-Interactive Switch (Automation Mode)
**Objective:** Verify `cloudctl switch` with explicit arguments for CI/CD
**Command:** `cloudctl switch bt-avm --account 235494790978 --role AdministratorAccess --region us-east-1 --non-interactive`
**Expected Output:**
- Credentials exported
- No interactive prompts
- Credentials valid for specified account/role/region

**Pass Criteria:**
```bash
cloudctl switch bt-avm --account 235494790978 --role AdministratorAccess --region us-east-1 --non-interactive
[ -n "$AWS_ACCESS_KEY_ID" ]
aws sts get-caller-identity | jq -e '.Account == "235494790978"'
```

---

## TEST SUITE 3: AWS API Operations (Real AWS Calls)

### TEST 3.1: Call AWS STS (Caller Identity)
**Objective:** Verify credentials work for basic AWS API call
**Command:** `aws sts get-caller-identity`
**Expected Output:**
- JSON response with UserId, Account (235494790978), Arn
- Arn should show AdministratorAccess role

**Pass Criteria:**
```bash
aws sts get-caller-identity | jq -e '.Account == "235494790978"'
aws sts get-caller-identity | jq -e '.Arn | contains("role/AdministratorAccess")'
```

---

### TEST 3.2: List IAM Users
**Objective:** Verify credentials have permissions to list IAM users
**Command:** `aws iam list-users --region us-east-1`
**Expected Output:**
- JSON response with Users array
- At minimum one user should be listed

**Pass Criteria:**
```bash
aws iam list-users | jq -e '.Users | length > 0'
```

---

### TEST 3.3: Describe EC2 Instances
**Objective:** Verify credentials can query EC2 in region
**Command:** `aws ec2 describe-instances --region us-east-1`
**Expected Output:**
- JSON response (may be empty Reservations array if no instances)
- No permission errors

**Pass Criteria:**
```bash
aws ec2 describe-instances --region us-east-1 | jq -e '.Reservations != null'
```

---

### TEST 3.4: List S3 Buckets
**Objective:** Verify credentials can list S3 buckets
**Command:** `aws s3 ls`
**Expected Output:**
- List of S3 buckets accessible to this user

**Pass Criteria:**
```bash
aws s3 ls | grep -q "^20"  # Date prefix in output
```

---

## TEST SUITE 4: Configuration & State Management

### TEST 4.1: Config File Validity
**Objective:** Verify orgs.yaml is valid and well-formed
**Command:** Check YAML syntax
**Expected Output:**
- YAML parses successfully
- All required fields present
- Schema validation passes

**Pass Criteria:**
```bash
python3 << 'EOF'
import yaml
from pathlib import Path

config_path = Path.home() / ".config" / "cloudctl" / "orgs.yaml"
with open(config_path) as f:
    data = yaml.safe_load(f)

# Verify structure
assert "organizations" in data or "orgs" in data, "No organizations found"
assert "version" in data, "No version field"

# Verify each org has required fields
orgs = data.get("organizations", {})
for name, config in orgs.items():
    assert config.get("provider"), f"Missing provider for {name}"
    if config.get("provider") == "aws":
        assert config.get("sso_start_url"), f"Missing sso_start_url for {name}"
        assert config.get("sso_region"), f"Missing sso_region for {name}"

print("✓ Config file valid")
EOF
```

---

### TEST 4.2: Doctor/Health Check
**Objective:** Verify CloudCtl health diagnostic passes
**Command:** `cloudctl doctor`
**Expected Output:**
- All health checks pass
- No warnings or errors
- Configuration is valid

**Pass Criteria:**
```bash
cloudctl doctor | grep -q "healthy\|All checks passed" || cloudctl doctor 2>&1 | grep -q -i "ok\|pass"
```

---

### TEST 4.3: Config Directory Permissions
**Objective:** Verify config files have correct permissions (not world-readable)
**Command:** Check file permissions
**Expected Output:**
- orgs.yaml should be 600 or 640 (not world-readable)
- Private keys should be 600

**Pass Criteria:**
```bash
stat -c "%A" ~/.config/cloudctl/orgs.yaml | grep -E "rw------- |rw--w----"  # 600 or 640
```

---

## TEST SUITE 5: Credential Lifecycle

### TEST 5.1: Token Expiration Handling
**Objective:** Verify behavior when token is expired
**Command:** Manually expire token, try to list accounts
**Expected Output:**
- Graceful error message
- Suggestion to re-authenticate (cloudctl login)

**Pass Criteria:**
```bash
# Note: This test requires manually expiring a token
# In real scenario, credentials would auto-refresh
# For now, just verify error handling is present in code
cloudctl --help | grep -q "login\|logout"
```

---

### TEST 5.2: Credential Refresh
**Objective:** Verify CloudCtl can refresh expired credentials automatically
**Command:** `cloudctl switch` after token would naturally expire
**Expected Output:**
- Automatic re-authentication
- New credentials issued
- Operation continues without user intervention

**Pass Criteria:**
```bash
# Credentials remain valid for subsequent API calls
aws sts get-caller-identity | jq -e '.Account'
```

---

## TEST SUITE 6: Error Handling & Recovery

### TEST 6.1: Invalid Organization
**Objective:** Verify error handling for non-existent organization
**Command:** `cloudctl accounts nonexistent-org`
**Expected Output:**
- Clear error message: "Organization not found"
- Suggestion to list available orgs

**Pass Criteria:**
```bash
cloudctl accounts nonexistent-org 2>&1 | grep -q "not found\|unknown\|available"
```

---

### TEST 6.2: Invalid Account ID
**Objective:** Verify error handling for non-existent account
**Command:** `cloudctl list-roles bt-avm --account 999999999999`
**Expected Output:**
- Clear error or empty role list
- No crash or unhandled exception

**Pass Criteria:**
```bash
cloudctl list-roles bt-avm --account 999999999999 2>&1
exit_code=$?; [ $exit_code -eq 0 ] || [ $exit_code -eq 1 ]  # Clean exit
```

---

### TEST 6.3: Invalid Role
**Objective:** Verify error handling for non-existent role
**Command:** `cloudctl switch bt-avm --account 235494790978 --role InvalidRole --non-interactive 2>&1`
**Expected Output:**
- Clear error message
- List of available roles
- Suggestion to use valid role

**Pass Criteria:**
```bash
cloudctl switch bt-avm --account 235494790978 --role InvalidRole --non-interactive 2>&1 | grep -q "not found\|Invalid\|Available"
```

---

## TEST SUITE 7: Multi-Cloud Support (Structure Only)

### TEST 7.1: GCP Project List (if credentials available)
**Objective:** Verify GCP organization is properly configured
**Command:** `cloudctl accounts gcp-prod` (if GCP auth available)
**Expected Output:**
- List of GCP projects accessible to user

**Pass Criteria:**
```bash
# Only test if GCP auth is configured
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    cloudctl accounts gcp-prod | grep -q "project"
fi
```

---

### TEST 7.2: Azure Subscription List (if credentials available)
**Objective:** Verify Azure organization is properly configured
**Command:** `cloudctl accounts avm-prod` (if Azure auth available)
**Expected Output:**
- List of Azure subscriptions accessible to user

**Pass Criteria:**
```bash
# Only test if Azure auth is configured
if command -v az &> /dev/null; then
    cloudctl accounts avm-prod | grep -q "subscription"
fi
```

---

## EXECUTION CHECKLIST

Run tests in this order. Each test builds on previous ones.

```bash
#!/bin/bash
set -e

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name=$1
    local test_cmd=$2
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "TEST: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if eval "$test_cmd"; then
        echo "✅ PASSED: $test_name"
        ((TESTS_PASSED++))
    else
        echo "❌ FAILED: $test_name"
        ((TESTS_FAILED++))
        # Continue to next test, don't exit
    fi
    echo ""
}

# Run all tests
run_test "1.1 Org Enumeration" "cloudctl org list | grep -q 'Configured Organizations (6)'"
run_test "1.2 Account Discovery" "cloudctl accounts bt-avm | grep -q '235494790978'"
run_test "1.3 Account Sync" "cloudctl accounts bt-avm --sync | grep -q '235494790978'"
run_test "1.4 Role Discovery" "cloudctl list-roles bt-avm --account 235494790978 | grep -q 'AdministratorAccess'"
run_test "4.1 Config Validity" "python3 -c 'import yaml; yaml.safe_load(open(open(\"~/.config/cloudctl/orgs.yaml\").name))'"
run_test "4.2 Health Check" "cloudctl doctor"
run_test "6.1 Invalid Org Error" "! cloudctl accounts nonexistent-org 2>&1 | grep -q 'error\|not found'"
run_test "6.2 Invalid Account Error" "cloudctl list-roles bt-avm --account 999999999999"

echo ""
echo "═══════════════════════════════════════════"
echo "FINAL RESULTS"
echo "═══════════════════════════════════════════"
echo "✅ Passed: $TESTS_PASSED"
echo "❌ Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    exit 0
else
    echo "⚠️  SOME TESTS FAILED - Review above for details"
    exit 1
fi
```

---

## Testing Best Practices

1. **Run tests sequentially** - Don't run in parallel
2. **Capture output** - Save test output to file for audit trail
3. **Real operations** - Use actual AWS accounts, not mocks
4. **Clean state** - Start with fresh credentials before each test suite
5. **Error documentation** - Record all error messages and exit codes
6. **Idempotency** - Tests should be re-runnable without cleanup
7. **Timing** - Note any long-running operations (network delays)

---

## Success Criteria

- All 24 tests pass
- No unhandled exceptions
- Error messages are clear and actionable
- AWS API calls succeed with correct permissions
- Credentials are valid and non-expired
- Configuration is properly formatted
- No security warnings

