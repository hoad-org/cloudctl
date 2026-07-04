# CloudCtl Error Reference

Quick lookup for CloudCtl error messages and solutions.

## Authentication & SSO Errors

### SSO session expired

**Message:** `SSO session expired`

**Cause:** Your SSO login has expired (typically after 8-12 hours)

**Solution:**
```bash
python3.12 -m cloudctl login --org <org> --non-interactive
```

---

### Unable to authenticate with SSO

**Message:** `Unable to authenticate with SSO`

**Cause:** SSO provider unreachable or network issues

**Solutions:**
1. Verify network connectivity
2. Check if behind corporate proxy (may need AWS CLI config)
3. Try again in 30 seconds
4. Contact platform team if persistent

---

## Configuration Errors

### orgs.yaml not found

**Message:** `orgs.yaml not found at ~/.config/cloudctl/orgs.yaml`

**Solution:**
```bash
python3.12 -m cloudctl init
```

Then edit `~/.config/cloudctl/orgs.yaml` with your organization details.

---

### Organization not found

**Message:** `Organization 'xyz' not found in orgs.yaml`

**Cause:** Organization name is misspelled or not configured

**Solution:**
```bash
# Check configured organizations
grep "^  " ~/.config/cloudctl/orgs.yaml

# Use correct organization name
python3.12 -m cloudctl switch bt-avm ...
```

---

### Invalid YAML syntax

**Message:** `Invalid YAML syntax in orgs.yaml at line N`

**Cause:** YAML formatting errors

**Solutions:**
1. Open `~/.config/cloudctl/orgs.yaml`
2. Fix indentation (must be 2 spaces, not tabs)
3. Check for missing colons after field names
4. Verify with: `python3.12 -c "import yaml; yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml')))"`

---

## Account & Role Errors

### Account not found

**Message:** `Account '235494790978' not found in organization 'bt-avm'`

**Cause:** Account ID is wrong or not in your organization

**Solution:**
```bash
# List valid accounts
python3.12 -m cloudctl accounts --org bt-avm

# Use correct account ID from the list
```

---

### Role not found

**Message:** `Role 'xyz_admin' not found for account 235494790978`

**Cause:** Role name is wrong or doesn't exist in that account

**Solution:**
```bash
# List valid roles
python3.12 -m cloudctl list-roles --org bt-avm --account 235494790978

# Use correct role name from the list
```

---

## Permission & Approval Errors

### Permission denied

**Message:** `Permission denied - you don't have permission to assume this role`

**Cause:** Your SSO user doesn't have permission for this role

**Solutions:**
1. Contact platform team to grant permission
2. Try a different role (if available)
3. Check available roles: `python3.12 -m cloudctl list-roles --org <org> --assigned`

---

### Approval required

**Message:** `Approval required for 'admin' role. Waiting for platform team to approve (30 seconds)...`

**Meaning:** This is normal for sensitive roles

**What to do:**
- Wait for approval (up to 30 seconds)
- If approved: Operation completes automatically
- If timeout: Approval didn't arrive, re-run command
- If denied: Contact platform team about access

---

## Region & Service Errors

### Invalid region

**Message:** `Region 'us-north-1' is invalid`

**Cause:** Region name is misspelled or doesn't exist

**Solution:**
```bash
# Use correct region name
# Examples: us-east-1, us-gov-west-1, eu-west-1

python3.12 -m cloudctl exec \
  --org bt-avm \
  --region us-east-1 \
  ...
```

---

### Service not available in region

**Message:** `Service 'eks' is not available in region 'us-gov-west-1'`

**Cause:** Service doesn't exist in that region (common in GovCloud)

**Solutions:**
1. Use a different region where service is available
2. Contact platform team about alternatives
3. Check AWS GovCloud service availability

---

## Credential & Token Errors

### Unable to locate credentials

**Message:** `Unable to locate credentials`

**Cause:** Split CloudCtl operations across multiple Bash calls (violates primary rule)

**Solution:**
```bash
# WRONG - split across calls:
python3.12 -m cloudctl login bt-avm
python3.12 -m cloudctl switch ...  # ❌ No credentials in new call

# CORRECT - everything in ONE call:
python3.12 -m cloudctl exec ... -- aws s3 ls
```

---

### Token expired

**Message:** `Token expired after 1 hour`

**Cause:** Operation exceeds token TTL

**Solutions:**
1. For long operations: CloudCtl auto-refreshes (if SSO still valid)
2. If refresh fails: Re-run command
3. Check SSO session: `python3.12 -m cloudctl doctor`

---

## Network & Timeout Errors

### Network timeout

**Message:** `Network timeout - operation exceeded 30 seconds`

**Cause:** Operation took too long (network too slow or operation too slow)

**Solutions:**
1. Check network: `ping cloudctl-provider`
2. Try again
3. Contact platform team if persistent

---

### Connection refused

**Message:** `Connection refused - unable to reach SSO provider`

**Cause:** SSO provider is down or unreachable

**Solutions:**
1. Check network connectivity
2. Check if behind corporate proxy
3. Try again in 1 minute
4. Contact platform team if persistent

---

## Python & Dependency Errors

### ModuleNotFoundError: No module named 'cloudctl'

**Message:** `ModuleNotFoundError: No module named 'cloudctl'`

**Cause:** CloudCtl package not installed in Python 3.12

**Solution:**
```bash
python3.12 -m pip install cloudctl
python3.12 -m cloudctl --version
```

---

### python3.12: command not found

**Message:** `python3.12: command not found`

**Cause:** Python 3.12 not installed

**Solution:**
```bash
# macOS
brew install python@3.12

# Linux
sudo apt install python3.12

# Then verify
python3.12 --version
```

---

## When to Escalate

Escalate to platform team if:
- Error not in this reference
- `cloudctl doctor` shows ❌ you cannot fix
- Permission denied (don't have role access)
- SSO provider unreachable
- Network issues that persist >5 minutes

## Escalation Information

When contacting platform team, provide:
1. Output of: `python3.12 -m cloudctl doctor`
2. Exact error message
3. Command you ran
4. Exit code: `echo $?`
5. Your organization name and account ID

---

## Next Steps

- [Troubleshooting](TROUBLESHOOTING.md) — Detailed troubleshooting guide
- [Command Reference](COMMAND_REFERENCE.md) — All available commands
- [Quick Start](QUICK_START.md) — Get started guide
