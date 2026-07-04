# CloudCtl Command Reference

Complete reference for all CloudCtl commands.

## Core Commands

### login

Create an authenticated session with AWS Identity Center.

```bash
python3.12 -m cloudctl login --org <ORG> [--non-interactive]
```

**Options:**
- `--org ORG` (required): Organization name (e.g., `bt-avm`)
- `--non-interactive`: Skip prompts (required for automation)

**Example:**
```bash
python3.12 -m cloudctl login --org bt-avm --non-interactive
```

**What it does:**
1. Authenticates with SSO
2. Creates ephemeral credentials
3. Stores session locally (valid for 8-12 hours)

---

### switch

Assume a different role in an account.

```bash
python3.12 -m cloudctl switch <ORG> \
  --account <ACCOUNT_ID> \
  --role <ROLE_NAME> \
  --region <REGION> \
  [--non-interactive]
```

**Options:**
- `ORG` (required): Organization name
- `--account` (required): 12-digit account ID
- `--role` (required): IAM role name
- `--region` (required): AWS region (e.g., `us-east-1`)
- `--non-interactive`: Skip prompts (required for automation)

**Example:**
```bash
python3.12 -m cloudctl switch bt-avm \
  --account 235494790978 \
  --role administrator \
  --region us-east-1 \
  --non-interactive
```

---

### exec

Execute AWS commands with assumed role credentials. **PRIMARY COMMAND FOR AUTOMATION.**

```bash
python3.12 -m cloudctl exec \
  --org <ORG> \
  --account <ACCOUNT_ID> \
  --role <ROLE_NAME> \
  --region <REGION> \
  [--non-interactive] \
  -- <COMMAND>
```

**Options:**
- `--org` (required): Organization name
- `--account` (required): 12-digit account ID
- `--role` (required): IAM role name
- `--region` (required): AWS region
- `--non-interactive`: Skip prompts (required for automation)
- `--`: Everything after this is the command to execute

**Examples:**

List S3 buckets:
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- aws s3 ls
```

Run Terraform:
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role administrator \
  --region us-east-1 \
  --non-interactive \
  -- terraform apply
```

Run complex bash command:
```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  --non-interactive \
  -- bash -c "aws s3 ls | grep -i prod"
```

---

### logout

End current session and clear cached credentials.

```bash
python3.12 -m cloudctl logout
```

**What it does:**
- Invalidates SSO session
- Clears cached credentials
- Requires re-authentication on next login

---

## Utility Commands

### doctor

Check configuration and system health.

```bash
python3.12 -m cloudctl doctor
```

**Output:**
```
✅ Python 3.12 available
✅ CloudCtl package installed
✅ orgs.yaml found
✅ orgs.yaml YAML syntax valid
✅ orgs.yaml schema valid
✅ SSO session active
```

All checks must pass (✅) for CloudCtl to function.

---

### accounts

List all accounts in an organization.

```bash
python3.12 -m cloudctl accounts --org <ORG>
```

**Example:**
```bash
python3.12 -m cloudctl accounts --org bt-avm
```

**Output:**
```
Account ID       Account Name
235494790978     production
123456789012     staging
987654321098     development
```

---

### list-roles

List available or assigned IAM roles.

```bash
# List all available roles
python3.12 -m cloudctl list-roles --org <ORG> --account <ACCOUNT_ID>

# List roles assigned to current user
python3.12 -m cloudctl list-roles --org <ORG> --assigned
```

**Examples:**

All available roles:
```bash
python3.12 -m cloudctl list-roles --org bt-avm --account 235494790978
```

Your assigned roles:
```bash
python3.12 -m cloudctl list-roles --org bt-avm --assigned
```

---

### org

Show organization configuration.

```bash
python3.12 -m cloudctl org --org <ORG>
```

**Example:**
```bash
python3.12 -m cloudctl org --org bt-avm
```

---

### status

Show current session status.

```bash
python3.12 -m cloudctl status
```

**Output:**
```
Organization: bt-avm
Account: 235494790978
Role: administrator
Region: us-east-1
Session expires in: 2 hours
```

---

### init

Initialize default configuration.

```bash
python3.12 -m cloudctl init
```

Creates `~/.config/cloudctl/orgs.yaml` with guided setup wizard.

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Operation completed |
| 1 | General error | Check error message |
| 2 | Argument error | Check command syntax |
| 30 | Network timeout | Retry operation |
| 124 | Command timeout | Operation exceeded timeout |

---

## Common Patterns

### Automation/CI-CD Pattern

Always use this pattern for automation:

```bash
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role administrator \
  --region us-east-1 \
  --non-interactive \
  -- <YOUR_COMMAND_HERE>
```

### Interactive Pattern (Local Development)

```bash
# 1. Login
python3.12 -m cloudctl login --org bt-avm

# 2. Switch to desired role
python3.12 -m cloudctl switch bt-avm \
  --account 235494790978 \
  --role developer \
  --region us-east-1

# 3. Run commands
python3.12 -m cloudctl exec ... -- aws s3 ls
```

### One-off Operations

```bash
# All in one command
python3.12 -m cloudctl exec \
  --org bt-avm \
  --account 235494790978 \
  --role read-only \
  --region us-east-1 \
  -- aws ec2 describe-instances
```

---

## Next Steps

- [Quick Start](QUICK_START.md) — Your first commands
- [Troubleshooting](TROUBLESHOOTING.md) — Resolve errors
- [Error Reference](ERROR_REFERENCE.md) — Error message index
