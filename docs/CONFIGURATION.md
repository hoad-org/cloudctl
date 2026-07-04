# CloudCtl Configuration Guide

## Configuration File Location

```
~/.config/cloudctl/orgs.yaml
```

## Complete Configuration Example

```yaml
version: "4.0.0"
organizations:
  bt-avm:
    provider: aws
    partition: aws
    sso_start_url: "https://beyondtrust.awsapps.com/start"
    sso_region: "us-east-1"
    sensitive_roles:
      - admin
      - devops
      - security
    approval_gate_roles:
      admin: 2
      devops: 1
      security: 2
    mfa_required_roles:
      - admin
      - security

  fdr-gvc:
    provider: aws
    partition: aws-us-gov
    sso_start_url: "https://fdr-gvc.awsapps.com/start"
    sso_region: "us-gov-east-1"
    sensitive_roles:
      - admin
```

## Field Reference

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (use "4.0.0") |
| `organizations` | dict | Yes | Organization configurations |

### Organization Fields

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `provider` | string | Yes | "aws" | Cloud provider |
| `partition` | string | Yes | "aws" or "aws-us-gov" | AWS partition |
| `sso_start_url` | string | Yes | HTTPS URL | AWS Identity Center URL |
| `sso_region` | string | No | Region code | SSO region (default: us-east-1) |
| `sensitive_roles` | list | Yes | Role names | Roles requiring approval |
| `approval_gate_roles` | dict | No | Role: count (1-2) | Approval requirements |
| `mfa_required_roles` | list | No | Role names | Roles requiring MFA |

## Commercial AWS vs GovCloud

### Commercial AWS (Standard)

```yaml
bt-avm:
  provider: aws
  partition: aws                    # ← Standard partition
  sso_start_url: "https://beyondtrust.awsapps.com/start"
  sso_region: "us-east-1"
```

### GovCloud (FedRAMP)

```yaml
fdr-gvc:
  provider: aws
  partition: aws-us-gov             # ← GovCloud partition
  sso_start_url: "https://fdr-gvc.awsapps.com/start"
  sso_region: "us-gov-east-1"
```

**Key Differences:**
- Partition name: `aws` vs `aws-us-gov`
- Region names are different (`us-east-1` vs `us-gov-east-1`)
- Service availability varies by region

## Approval Gates

Approval gates require human review before sensitive operations complete.

### Configuring Approval Gates

```yaml
approval_gate_roles:
  admin: 2        # admin role requires 2 approvers
  devops: 1       # devops role requires 1 approver
  # Roles NOT listed here don't require approval
```

### How Approval Gates Work

1. User requests sensitive role
2. CloudCtl sends approval request to platform team
3. User waits up to 30 seconds
4. Platform team approves or denies
5. Operation completes or fails

## MFA Requirements

```yaml
mfa_required_roles:
  - admin
  - security
```

Roles listed require MFA verification (TOTP, SMS, or WebAuthn).

## Validation

### Check Configuration Syntax

```bash
# Validate YAML syntax
python3.12 -c "import yaml; yaml.safe_load(open(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml'))))"

# Should return nothing (success) or show YAML error
```

### Check CloudCtl Recognizes Config

```bash
python3.12 -m cloudctl doctor
```

Expected output:
```
✅ orgs.yaml found
✅ orgs.yaml YAML syntax valid
✅ orgs.yaml schema valid
```

## Common Configuration Mistakes

### ❌ Using wrong field names

```yaml
# WRONG
ssoStartUrl: "..."        # Use snake_case: sso_start_url
approvalGateRoles: ...    # Use snake_case: approval_gate_roles
```

### ❌ Using wrong partition name

```yaml
# WRONG
partition: govcloud       # Use: aws-us-gov
partition: aws-gov        # Use: aws-us-gov
```

### ❌ Invalid indentation

```yaml
# WRONG
organizations:
  bt-avm:
    provider: aws         # Must use 2 spaces (not tabs)
	sso_start_url: "..."  # This tab will cause error
```

## Resetting Configuration

To start over:

```bash
rm ~/.config/cloudctl/orgs.yaml
python3.12 -m cloudctl init
```

## Next Steps

- [Quick Start](QUICK_START.md) — Get your first commands working
- [Command Reference](COMMAND_REFERENCE.md) — All available commands
- [Troubleshooting](TROUBLESHOOTING.md) — Resolve configuration issues
