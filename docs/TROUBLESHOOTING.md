# CloudCtl Troubleshooting Guide

Detailed troubleshooting procedures for common CloudCtl issues.

## Diagnosis Workflow

When CloudCtl fails, follow this workflow:

### Step 1: Run Health Check

```bash
python3.12 -m cloudctl doctor
```

**Interpretation:**
- ✅ All checks pass? → Issue is with your operation, not setup
- ❌ Any check fails? → Fix the issue reported, re-run doctor

### Step 2: Check Exit Code

```bash
python3.12 -m cloudctl <command>
echo $?
```

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Check output for errors |
| 1 | General error | Check error message (ERROR_REFERENCE.md) |
| 2 | Argument error | Check command syntax |
| 30 | Network timeout | Retry (network too slow) |
| 124 | Command timeout | Operation exceeded timeout |

### Step 3: Find Exact Error

Find exact error message in [ERROR_REFERENCE.md](ERROR_REFERENCE.md) and follow recovery steps.

---

## Common Issues & Solutions

### Issue: "Unable to locate credentials"

**Symptom:**
```
❌ Error: Unable to locate credentials
```

**Root Cause:**
Split CloudCtl operations across multiple Bash calls. Each call is independent with fresh environment.

**Solution:**
Put everything in ONE call:

```bash
# ❌ WRONG
python3.12 -m cloudctl login bt-avm
python3.12 -m cloudctl switch ...  # Credentials lost

# ✅ CORRECT
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role admin \
  --region us-east-1 \
  -- aws s3 ls
```

---

### Issue: "cloudctl: command not found"

**Symptom:**
```
command not found: cloudctl
```

**Root Cause:**
Not using full Python module invocation.

**Solution:**
Always use full form:

```bash
# ✅ CORRECT
python3.12 -m cloudctl <command>

# ❌ WRONG
cloudctl <command>          # Not in PATH
python cloudctl <command>   # Wrong Python version
```

---

### Issue: Role name not found after listing roles

**Symptom:**
```bash
$ python3.12 -m cloudctl list-roles --org bt-avm --assigned
✓ Your assigned roles in bt-avm:
  - administrator

$ python3.12 -m cloudctl exec --role admin ...  # ❌ Role 'admin' not found
```

**Root Cause:**
Using a different role name than what's listed.

**Solution:**
Use exact role name from `list-roles`:

```bash
# Discover roles
python3.12 -m cloudctl list-roles --org bt-avm --assigned
# Output: administrator

# Use exact name
python3.12 -m cloudctl exec --role administrator ...
```

---

### Issue: Approval timeout

**Symptom:**
```
Approval required for 'admin' role
Waiting for platform team to approve (30 seconds)...
❌ Approval request timed out after 30 seconds
```

**Root Cause:**
Platform team didn't respond within 30 seconds (normal for approval gates).

**Solution:**
Re-run the command to generate new approval request:

```bash
# Re-run the same command
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role admin \
  ...
```

---

### Issue: AWS CLI profile not found

**Symptom:**
```
❌ Error: The config profile (cloudctl-a1b2c3d4) could not be found
```

**Root Cause:**
CloudCtl's AWS_PROFILE generation bug (known issue in v5.3.2).

**Solutions:**

**Option 1: Use GitHub Actions instead**
```bash
# Instead of cloudctl exec, trigger a workflow
gh workflow dispatch trigger-ecs-inventory --ref main
```

**Option 2: Ensure ~/.aws/config is properly set up**
```ini
[default]
region = us-east-1
output = json
```

**Option 3: Use explicit region**
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --region us-east-1 \
  -- aws s3 ls --region us-east-1
```

---

## Verification Procedures

### Verify Configuration

```bash
# Check YAML syntax
python3.12 -c "import yaml; yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml')))"
# No output = success

# Check CloudCtl recognizes it
python3.12 -m cloudctl doctor
# All ✅ = success
```

### Verify AWS CLI Integration

```bash
# Check AWS CLI works with CloudCtl
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  -- aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "235494790978",
    "Arn": "arn:aws:iam::235494790978:role/..."
}
```

### Verify Long-Running Operations

For operations > 1 hour, verify token refresh is working:

```bash
# Terraform apply (2+ hours)
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role admin \
  --region us-east-1 \
  -- terraform apply

# Token auto-refreshes after 1 hour
# If operation completes: ✅ Token refresh worked
```

---

## Debugging Techniques

### Enable Debug Logging

```bash
export CLOUDCTL_DEBUG=1
python3.12 -m cloudctl <command>
```

### Check CloudCtl Logs

```bash
# View audit log
cat ~/.cloudctl/audit.log

# View recent entries
tail -20 ~/.cloudctl/audit.log
```

### Check SSO Cache Status

```bash
# List SSO cache files
ls -la ~/.cloudctl/sso_cache/

# Check if SSO session is valid
python3.12 -m cloudctl status
```

### Trace Network Issues

```bash
# Test connectivity to SSO
ping sso.provider.com

# Test AWS API connectivity
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  -- aws ec2 describe-regions
```

---

## When to Escalate

Contact platform team if:

1. `cloudctl doctor` shows ❌ that you cannot fix
2. Error message not in ERROR_REFERENCE.md
3. Permission denied (don't have role access)
4. SSO provider unreachable (network issue)
5. Issue persists after trying all solutions above

**Information to provide:**
```bash
# 1. Health check output
python3.12 -m cloudctl doctor

# 2. Exact error message
# (from your command)

# 3. Command you ran
# (copy-paste from your shell)

# 4. Exit code
echo $?

# 5. Context
# (org name, account ID, region)
```

---

## Next Steps

- [Error Reference](ERROR_REFERENCE.md) — Error message index
- [Command Reference](COMMAND_REFERENCE.md) — All available commands
- [Configuration](CONFIGURATION.md) — Setup and configuration
