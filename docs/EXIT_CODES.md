# CloudCtl Exit Codes

All CloudCtl commands return standard exit codes. Agents can use these codes to detect success/failure and determine the appropriate action (continue, retry, re-authenticate, etc.).

## Exit Code Table

| Code | Meaning | Use Case | Agent Action |
|------|---------|----------|--------------|
| **0** | Success | Command executed successfully | Continue to next step |
| **1** | General Error | Unrecognized command, unexpected exception | Stop, check stderr for details |
| **2** | Auth Required | Credentials expired, MFA required | Call `cloudctl login <org>` to re-authenticate |
| **3** | Not Found | Org/account/role doesn't exist | Verify org/account/role names, check available with `cloudctl switch <org>` |
| **4** | Permission Denied | Insufficient role permissions, rate limited | User lacks permissions or rate limit exceeded, retry after delay |
| **5** | Invalid Argument | Missing required argument, invalid config | Fix command arguments or config file, re-run |

## Exit Codes by Error Type

### Error Code 0: Success
**Causes:**
- Command executed successfully
- All operations completed without errors

**Example:**
```bash
cloudctl switch --org bt-avm --account 235494790978 --role admin --non-interactive
echo $?  # 0
```

**Agent Next Steps:**
- Continue to next step in pipeline
- Proceed with remaining operations

---

### Error Code 1: General Error
**Causes:**
- Unrecognized command
- Unexpected exception during execution
- Network failure
- Unknown internal error

**Example:**
```bash
cloudctl invalid-command
echo $?  # 1

cloudctl switch --org invalid-org --non-interactive
# Error: Organization 'invalid-org' not found
echo $?  # 3 (actually this is "Not Found", see Code 3)

cloudctl whoami
# Some unexpected internal error
echo $?  # 1
```

**Agent Next Steps:**
- Stop and report error
- Log stderr for debugging
- Alert on-call team if critical path

---

### Error Code 2: Auth Required
**Causes:**
- Credentials have expired
- Token is no longer valid
- MFA is required but not provided
- SSO session has timed out

**Example:**
```bash
cloudctl switch --org bt-avm --account 235494790978 --role admin --non-interactive
# Error: Credentials expired for organization 'bt-avm': Token expired
echo $?  # 2

cloudctl status
# Error: MFA required for role 'admin'
echo $?  # 2
```

**Agent Next Steps:**
1. Call `cloudctl login <org>` to re-authenticate
2. Wait for user to complete MFA if required (interactive)
3. Retry the original command after successful login
4. If MFA times out (>30 seconds), escalate to manual intervention

---

### Error Code 3: Not Found
**Causes:**
- Organization name doesn't exist in config
- Account ID is not found in organization
- Role name is not available for account
- Resource doesn't exist

**Example:**
```bash
# Invalid org
cloudctl switch --org invalid-org --non-interactive
# Error: Organization 'invalid-org' not found (available: bt-avm, fdr-gvc, gcp-prod)
echo $?  # 3

# Invalid account
cloudctl switch --org bt-avm --account 999999999999 --role admin --non-interactive
# Error: Account '999999999999' not found in organization 'bt-avm'
echo $?  # 3

# Invalid role
cloudctl switch --org bt-avm --account 235494790978 --role nonexistent --non-interactive
# Error: Role 'nonexistent' not found for account '235494790978'
echo $?  # 3
```

**Agent Next Steps:**
1. Verify the org/account/role name is correct
2. Run `cloudctl switch <org>` interactively to see available options
3. Update your configuration with valid names
4. Retry the command

---

### Error Code 4: Permission Denied
**Causes:**
- User lacks IAM permissions for requested role
- Role requires approval (approval pending)
- Rate limit exceeded (too many requests)

**Example:**
```bash
# Insufficient permissions
cloudctl switch --org bt-avm --account 235494790978 --role security-admin --non-interactive
# Error: You do not have permission to assume role 'security-admin' in account '235494790978'
echo $?  # 4

# Rate limit exceeded
cloudctl switch --org bt-avm --account 235494790978 --role admin --non-interactive
# Then immediately retry
# Error: Rate limit exceeded for operation 'switch'. Retry after 60 seconds
echo $?  # 4

# Approval pending
cloudctl switch --org bt-avm --account 235494790978 --role admin --non-interactive
# Error: Access to role 'admin' is pending approval (request ID: req-12345)
echo $?  # 4
```

**Agent Next Steps:**
- If permission denied: Contact administrator to grant role permissions
- If approval pending: Wait for approval (check email/approval system)
- If rate limited: Wait and retry (see retry_after in error message)
- Exponential backoff: Wait progressively longer between retries (1s, 2s, 4s, 8s)

---

### Error Code 5: Invalid Argument
**Causes:**
- Missing required command-line argument
- Invalid configuration file syntax
- Invalid argument value (wrong format)
- Config validation failed

**Example:**
```bash
# Missing required argument in non-interactive mode
cloudctl switch --non-interactive
# Error: --non-interactive requires --account, --role, and --region
echo $?  # 5

# Invalid config file
# (orgs.yaml is malformed)
cloudctl doctor
# Error: Configuration file '~/.config/cloudctl/orgs.yaml' is invalid: ...
echo $?  # 5

# Invalid argument value
cloudctl switch --org bt-avm --account abc --role admin --non-interactive
# Error: Invalid account ID 'abc' (must be numeric)
echo $?  # 5
```

**Agent Next Steps:**
1. Review the error message (includes suggestion)
2. Fix the argument or configuration file
3. Re-run the command
4. Run `cloudctl doctor` to validate configuration

---

## Agent Workflow Example

Here's how an agent should use exit codes in a multi-step workflow:

```bash
#!/bin/bash
set -e  # Exit on first error

# Step 1: Authenticate
echo "Step 1: Authenticating to bt-avm..."
cloudctl login bt-avm
LOGIN_RC=$?

if [ $LOGIN_RC -eq 0 ]; then
    echo "  ✓ Authenticated"
elif [ $LOGIN_RC -eq 2 ]; then
    echo "  ✗ Credentials expired, manual login required"
    exit 1
else
    echo "  ✗ Login failed with exit code $LOGIN_RC"
    exit 1
fi

# Step 2: Switch context
echo "Step 2: Switching to account 235494790978 (admin role)..."
cloudctl switch --org bt-avm --account 235494790978 --role admin --region us-east-1 --non-interactive
SWITCH_RC=$?

if [ $SWITCH_RC -eq 0 ]; then
    echo "  ✓ Context switched"
elif [ $SWITCH_RC -eq 2 ]; then
    echo "  ✗ Need to re-authenticate"
    cloudctl login bt-avm
    # Retry switch
    cloudctl switch --org bt-avm --account 235494790978 --role admin --region us-east-1 --non-interactive
elif [ $SWITCH_RC -eq 3 ]; then
    echo "  ✗ Invalid org/account/role"
    cloudctl switch bt-avm  # Show available options
    exit 1
elif [ $SWITCH_RC -eq 4 ]; then
    echo "  ✗ Permission denied or rate limited"
    exit 1
elif [ $SWITCH_RC -eq 5 ]; then
    echo "  ✗ Invalid arguments"
    exit 1
else
    echo "  ✗ Switch failed with exit code $SWITCH_RC"
    exit 1
fi

# Step 3: Verify context
echo "Step 3: Verifying context..."
cloudctl env --format json | jq '.org, .account, .role'

# Step 4: Run command
echo "Step 4: Running terraform plan..."
terraform plan
```

---

## Testing Exit Codes

To test exit codes manually:

```bash
# Test success (0)
cloudctl doctor
echo "Exit code: $?"

# Test invalid org (3)
cloudctl switch --org invalid --non-interactive
echo "Exit code: $?"

# Test missing required arg (5)
cloudctl switch --org bt-avm --non-interactive
echo "Exit code: $?"

# Test after cleanup (2)
cloudctl cache-clear
cloudctl status
echo "Exit code: $?"  # Should be 2 (auth required)
```

---

## Exit Code Mapping to Error Classes

Exit codes are defined in `src/cloudctl/errors.py`:

| Exit Code | Error Class | Exception Raised When |
|-----------|-------------|----------------------|
| 0 | N/A (success) | N/A |
| 1 | `CloudCtlError` (base) | Generic error |
| 2 | `CredentialsExpiredError` | Token expired, MFA required |
| 3 | `InvalidOrgError`, `InvalidAccountError`, `InvalidRoleError` | Resource not found |
| 4 | `ApprovalPendingError`, `RateLimitedError` | Permission issue or rate limit |
| 5 | `ConfigInvalidError` | Invalid configuration |

---

## Implementation Notes for Developers

### Adding a New Error Type

1. Create a new error class in `src/cloudctl/errors.py`:
   ```python
   class MyNewError(CloudCtlError):
       """Description of error."""
       exit_code = <code>  # Pick 0-5
   ```

2. The exit code is automatically used in `src/cloudctl/cli.py`:
   ```python
   except CloudCtlError as e:
       return e.exit_code  # Uses the error's exit_code attribute
   ```

3. Update this documentation with the new error type

### Testing Exit Codes

All exit codes are tested in `tests/test_exit_codes.py`:
```bash
pytest tests/test_exit_codes.py -v
```

---

## References

- **Cloud CLI Best Practices:** https://en.wikipedia.org/wiki/Exit_status
- **CloudCtl Error Handling:** `src/cloudctl/errors.py`
- **CloudCtl CLI Implementation:** `src/cloudctl/cli.py`
