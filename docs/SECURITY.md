# CloudCtl Security Guide

Security best practices and compliance information for CloudCtl.

## Core Security Model

CloudCtl uses **ephemeral, ephemeral tokens**:
- Temporary credentials generated on-demand
- Automatic cleanup when expired
- Never stored on disk
- Unique to each operation

This is **more secure** than long-lived credentials because:
- Reduced exposure window (minutes to hours, not months)
- Automatic lifecycle management
- No manual credential rotation needed
- Perfect audit trail of all credential usage

## What CloudCtl Logs

CloudCtl maintains audit trail of:
- Login/logout events (who, when, from where)
- Role assumption operations (which account, which role)
- Success and failure outcomes
- Approval requests and responses

Audit log location: `~/.cloudctl/audit.log`

### What CloudCtl Does NOT Log

**Secrets NEVER logged:**
- AWS credentials (access keys, secret keys)
- Session tokens
- MFA codes
- Password values
- API keys

**AWS operations NOT logged:**
- AWS command outputs (not CloudCtl's responsibility)
- Data accessed via AWS CLI
- Infrastructure changes made by your commands

This ensures audit trail is useful for compliance without exposing sensitive data.

---

## Credential Exposure Prevention

### DO ✅

- Use `cloudctl exec` for all AWS operations
- Let CloudCtl manage credentials internally
- Let ephemeral tokens auto-cleanup
- Use `--non-interactive` for automation

### DO NOT ❌

- Save credentials to files
- Print credentials to console
- Put credentials in shell history
- Export credentials to environment variables
- Share credential strings
- Store credentials in config files

---

## Authentication & Authorization

### SSO (Single Sign-On)

CloudCtl uses AWS Identity Center (SSO) for all authentication:
- Multi-factor authentication (MFA) support
- Federated identity support
- Automatic session management
- Audit trail integration

### Approval Gates

Sensitive roles (admin, security, devops) require human approval:
- 1-2 approvers (configurable per role)
- Up to 30-second review time
- Denial possible (user contact required)
- Full audit trail

### Role-Based Access Control (RBAC)

Access controlled by:
- SSO group membership
- IAM role assumptions
- Approval gate configuration
- Region/partition restrictions

---

## Audit & Compliance

### Audit Trail

```bash
# View audit log
cat ~/.cloudctl/audit.log

# Sample entry:
# 2026-06-03T13:45:12 [login] user=choad org=bt-avm status=success
# 2026-06-03T13:46:00 [switch] user=choad org=bt-avm account=235494790978 role=admin status=success
```

### Retention

- Local audit log: kept indefinitely
- CloudCtl session cache: 12-hour TTL
- Credentials: auto-destroyed on expiration
- Platform audit logs: per organization policy

---

## Security Configuration

### Approval Gates

```yaml
approval_gate_roles:
  admin: 2        # Requires 2 approvers
  security: 2     # Requires 2 approvers
  devops: 1       # Requires 1 approver
```

Sensitive roles automatically trigger approval gates. Non-sensitive roles don't.

### MFA Requirements

```yaml
mfa_required_roles:
  - admin
  - security
```

Specified roles require MFA verification (TOTP, SMS, or WebAuthn).

---

## Alternative Authentication Methods

### NOT Recommended ❌

**DO NOT use:**
- AWS access keys manually entered
- Long-lived IAM user credentials
- Service principal secrets
- Static AWS credentials in env vars

**Why not:**
- Long-lived = higher risk if leaked
- Manual management = forget to rotate
- Audit gaps = compliance issues
- Defeats CloudCtl security model

### Recommended ✅

**DO use:**
- CloudCtl (ephemeral tokens)
- AWS Identity Center (SSO)
- STS temporary credentials
- MFA verification

---

## Network Security

### Encryption

All CloudCtl-to-SSO communication is encrypted:
- TLS 1.2+ required
- Certificate validation enforced
- No downgrade attacks possible

### Credential Injection

Credentials injected into subprocess environment only:
- Parent shell does NOT have access
- Subprocess auto-cleanup on exit
- No shell history exposure

Example:
```bash
python3.12 -m cloudctl exec ... -- aws s3 ls
# aws s3 ls can see credentials
# But your shell cannot access them
```

---

## Operational Security

### Shared Systems

On shared systems (CI/CD, shared servers):
- Each user gets isolated CloudCtl session
- Credentials not visible across users
- Audit trail tracks all access
- No credential file sharing

### Local Development

On your local machine:
- Keep CloudCtl updated
- Review `~/.cloudctl/audit.log` periodically
- Logout (`cloudctl logout`) when done
- Use unique roles per project

---

## Security Incident Response

If you suspect credential exposure:

1. **Immediately logout:**
   ```bash
   python3.12 -m cloudctl logout
   ```

2. **Inform platform team** with:
   - Timestamp of suspected exposure
   - Which role/account was affected
   - Suspected exposure method

3. **Platform team will:**
   - Revoke credentials
   - Audit what was accessed
   - Advise on remediation
   - Rotate long-lived credentials if needed

---

## Compliance

CloudCtl supports:
- **FedRAMP High** (GovCloud deployments)
- **NIST 800-53** (federal compliance)
- **SOC 2 Type II** (data security)
- **PCI-DSS** (payment systems)
- **HIPAA** (healthcare data)

CloudCtl maintains:
- Complete audit trail
- Encryption in transit
- Ephemeral credentials
- MFA enforcement
- Role-based access control

---

## Security Checklist

Before production use:

- [ ] Configured approval gates for sensitive roles
- [ ] MFA required for admin roles
- [ ] Audit log review process established
- [ ] Team trained on credential handling
- [ ] No credentials stored in files or history
- [ ] Using `cloudctl exec` for all AWS operations
- [ ] CloudCtl updated to latest version
- [ ] Regular security updates applied

---

## Reporting Security Issues

Found a security vulnerability? Report it:

1. **Do NOT** create public GitHub issue
2. Email security team with details
3. Include: affected version, reproduction steps, impact
4. Platform team will acknowledge within 24 hours

---

## Next Steps

- [Configuration](CONFIGURATION.md) — Set up approval gates and MFA
- [Command Reference](COMMAND_REFERENCE.md) — Safe command patterns
- [Troubleshooting](TROUBLESHOOTING.md) — Incident response
