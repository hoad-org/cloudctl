# CloudCTL & DevArmor Integration

This document explains how CloudCTL integrates with DevArmor to enforce cost controls, enable safe rollback procedures, and coordinate multi-cloud deployments.

---

## Overview

**DevArmor** is Craig's infrastructure governance system (v1.0.0, production-ready). It provides:

1. **Cost Control** — $30/mo budget enforcement via AWS
2. **Rollback Capability** — 3-phase infrastructure state recovery
3. **Multi-Cloud Orchestration** — Cross-cloud deployment sequencing and OIDC validation
4. **CLI Enforcement** — Prevents unauthorized direct deployments (GitHub Actions only)

CloudCTL integrates with DevArmor through:
- **Context validation** before credential export
- **Health checks** via `cloudctl doctor`
- **Cost tracking** during multi-cloud operations
- **Audit logging** for sensitive role access

---

## How CloudCTL Validates Against DevArmor

### Context Validation Flow

```
User runs: cloudctl switch <org>
    ↓
CloudCTL loads org config (~/.config/cloudctl/orgs.yaml)
    ↓
DevArmor health-check validates org is compliant
    ↓
If compliant: Export credentials to shell
If non-compliant: Block and report issue
    ↓
User verifies: cloudctl env
    ↓
Proceed with operation (terraform plan, aws s3 ls, etc.)
```

### Pre-Operation Validation

```bash
cloudctl doctor
```

**Checks:**
- ✅ DevArmor connectivity (health-check.sh reachable)
- ✅ Cost control status ($30/mo budget)
- ✅ Rollback procedures (infrastructure state backups available)
- ✅ Multi-cloud orchestration (OIDC trust policies valid)
- ✅ GitHub Actions configuration (correct org, repos, workflows)
- ✅ Jira ticket integration (HCP project, issue linking)

**If any check fails:**
- Do not proceed with infrastructure changes
- Report failure to DevArmor team
- Clear cache and retry: `cloudctl cache-clear && cloudctl doctor`

---

## Cost Control Integration

### Budget Enforcement

**Current Budget:** $30/month  
**Enforcement Mechanism:** AWS Cost Explorer API  
**Validation Point:** `cloudctl doctor` and multi-cloud orchestration

CloudCTL queries DevArmor cost state during:
1. **Context switching** — Verifies budget remains available
2. **Multi-cloud operations** — Estimates costs across AWS, GCP, Azure
3. **Large deployments** — Checks if operation would exceed budget

**Example Blocked Operation:**

```bash
cloudctl switch bt-avm
# ✓ Context loaded

cloudctl doctor
# ⚠️ Cost Warning: Current spend $28/mo
# ⚠️ Proposed deployment estimated at $5/mo
# ❌ Would exceed $30/mo budget
# Action: Request budget increase or defer deployment
```

### Resource Pricing Reference

See: `~/.claude/projects/-Users-craighoad-Repos/memory/COST-CONTROL-STANDARDS.md`

| Resource | Monthly Cost | Notes |
|----------|--------------|-------|
| AWS EC2 (t2.micro) | $0.01 (free tier) | Free tier active until limit |
| RDS (db.t3.micro) | $0.015/hour | ~$11/month if running 24/7 |
| Lambda (1M invocations) | Free | Free tier: 1M/month |
| S3 (1GB) | $0.023/month | Very low cost storage |

---

## Rollback Procedures Integration

### Three-Phase Rollback Execution

DevArmor provides infrastructure rollback capability (3 phases):

**Phase 1: Dry Run**
```bash
# CloudCTL context is switched to correct org
cloudctl switch bt-avm

# DevArmor validates rollback capability
cloudctl doctor
# ✓ Rollback procedures ready

# Dry-run initiated
terraform plan -destroy
```

**Phase 2: Safety Check**
```bash
# Verify resources to be destroyed
terraform plan -destroy | grep "will be destroyed"

# Confirm with DevArmor safety gates
# (Prevents critical resource destruction)
```

**Phase 3: Execute Rollback**
```bash
# Only after user approval
terraform destroy -auto-approve

# DevArmor logs rollback to audit trail
# ~/.cloudctl/audit.log
```

### When Rollback is Blocked

```bash
cloudctl doctor
# ❌ Rollback procedures: UNAVAILABLE
# Reason: Critical resource (database) missing prevent_destroy
# Solution: Add lifecycle { prevent_destroy = true } and retry
```

See full details: `~/.claude/projects/-Users-craighoad-Repos/memory/ROLLBACK-PROCEDURES.md`

---

## Multi-Cloud Orchestration Integration

### Cross-Cloud Deployment Sequencing

CloudCTL coordinates deployments across AWS, GCP, and Azure through DevArmor's multi-cloud orchestration layer.

**Example: Deploy to AWS and GCP**

```bash
# Step 1: Switch to AWS context (bt-avm)
cloudctl switch bt-avm
cloudctl env
# ✓ AWS Commercial credentials loaded

# Step 2: Deploy AWS infrastructure
terraform apply

# Step 3: Switch to GCP context
cloudctl switch gcp-prod
cloudctl env
# ✓ GCP credentials loaded

# Step 4: Deploy GCP infrastructure
gcloud deployment-manager deployments create my-deployment --config=config.yaml

# DevArmor coordinates:
# - Cost tracking across both clouds
# - Rollback sequencing (GCP first, then AWS)
# - OIDC validation for GitHub Actions
```

### OIDC Validation

CloudCTL validates GitHub Actions OIDC trust policies before exporting credentials:

```bash
cloudctl doctor
# ✓ GitHub OIDC validation: PASSED
# ✓ AWS OIDC trust policy: Valid for rhyscraig org
# ✓ GCP OIDC trust policy: Valid for rhyscraig org
# ✓ Azure OIDC trust policy: Valid for rhyscraig org

# If validation fails:
# ❌ GitHub OIDC validation: FAILED
# Reason: Trust policy mismatch for rhyscraig org
# Solution: Update trust policy to match GitHub Actions environment
```

See full details: `~/.claude/projects/-Users-craighoad-Repos/memory/MULTI-CLOUD-ORCHESTRATION.md`

---

## DevArmor Status Check

### Real-Time Status

```bash
cloudctl doctor
```

**Sample Output:**
```
CloudCTL v4.1.0 System Health Check
====================================

Python:           3.12.3 ✓
Shell Integration: zsh ✓
Config File:      ~/.config/cloudctl/orgs.yaml (valid) ✓

Cloud Provider Support:
  AWS:   ✓ (partition: aws, aws-us-gov)
  GCP:   ✓ (auth: gcloud)
  Azure: ✓ (auth: az CLI)

DevArmor Integration:
  Version:               v1.0.0 ✓
  Status:                ACTIVE ✓
  Cost Control:          $30/mo budget (current: $8/mo) ✓
  Rollback Procedures:   READY ✓
  Multi-Cloud:           3 clouds configured ✓
  Audit Logging:         ACTIVE ✓

GitHub Actions:
  Organization:         rhyscraig ✓
  OIDC Trust Policies:   All 3 clouds validated ✓
  Workflow Status:       Operational ✓

Jira Integration:
  Project:              HCP ✓
  Instance:             darkmothcreative.atlassian.net ✓
  Token:                CONFIGURED ✓

Configuration Hierarchy (4-level):
  1. Code Defaults:     LOADED ✓
  2. Master Config:     ~/.config/cloudctl/ ✓
  3. Repo Config:       ./.claude/ ✓
  4. Environment Vars:  None set ✓

No issues detected. System is healthy.
```

### Health Check Frequency

- **Manual:** Run `cloudctl doctor` before each major operation
- **Pre-Switch:** Automatically validated when running `cloudctl switch`
- **Pre-Deploy:** Explicitly checked before `terraform apply`

---

## Audit Logging

CloudCTL logs sensitive operations to `~/.cloudctl/audit.log` for compliance tracking.

### Logged Events

| Event | Trigger | Details |
|-------|---------|---------|
| CONTEXT_SWITCH | `cloudctl switch` | Org, account, role, region, timestamp |
| LOGIN | `cloudctl login` | Org, provider, authentication result |
| CREDENTIAL_EXPORT | Role assumption | Account ID, role name, region |
| LOGOUT | `cloudctl logout` | Org, provider, logout result |
| CACHE_CLEAR | `cloudctl cache-clear` | All cached credentials cleared |
| DOCTOR | `cloudctl doctor` | Health check results (success/failure) |
| AUDIT_VIEW | `cat ~/.cloudctl/audit.log` | Audit log access (for sensitive roles) |

**Example Audit Log Entry:**
```
2026-05-17T14:32:45Z | CONTEXT_SWITCH | org=bt-avm | account=123456789012 | role=AdminAccess | region=us-east-1
2026-05-17T14:32:50Z | CREDENTIAL_EXPORT | account=123456789012 | role=AdminAccess | region=us-east-1 | partition=aws
```

### Who Can View Audit Logs?

- **CloudOps team:** Full access to all logs
- **Regular users:** Only their own entries
- **Break-glass roles:** Flagged in log for compliance review

---

## Integration Workflows

### Workflow 1: Safe Infrastructure Deployment

```bash
# 1. Read orientation and checklist
cat .claude/INTEGRATION_CHECKLIST.md

# 2. Switch context
cloudctl switch bt-avm
cloudctl env

# 3. Check DevArmor status
cloudctl doctor
# ✓ Cost control active
# ✓ Rollback procedures ready

# 4. Plan deployment
terraform plan

# 5. Commit to GitHub (creates PR)
git add .
git commit -m "HCP-123: Add new RDS instance"
git push origin feature/new-rds

# 6. GitHub Actions runs plan automatically
# (CloudCTL used in GH Actions runner)

# 7. Merge PR (triggers apply in GitHub Actions)
# DevArmor validates:
# - Jira ticket HCP-123 exists and is linked
# - Cost estimate does not exceed budget
# - Rollback procedures are ready
# - All OIDC trust policies are valid

# 8. GitHub Actions applies changes
# Logs to CloudCTL audit trail
```

### Workflow 2: Emergency Rollback

```bash
# 1. Identify issue
# (e.g., database corruption, misconfiguration)

# 2. Load correct context
cloudctl switch bt-avm
cloudctl env

# 3. Initiate rollback
cloudctl doctor
# ✓ Rollback procedures: READY

# 4. Dry-run destruction
terraform plan -destroy

# 5. Execute rollback (Phase 3)
terraform destroy -auto-approve

# 6. Verify state restored
terraform plan
# (should show no changes)

# 7. DevArmor logs rollback to audit trail
# and notifies security team
```

### Workflow 3: Multi-Cloud Cost Validation

```bash
# 1. Planning multi-cloud deployment
# (AWS + GCP + Azure)

# 2. Check current costs
cloudctl doctor
# ✓ Current spend: $15/mo
# ✓ Available budget: $15/mo

# 3. Estimate per-cloud costs:
# - AWS deployment: ~$8/mo
# - GCP deployment: ~$5/mo
# - Azure deployment: ~$3/mo
# Total: $16/mo (EXCEEDS budget by $1)

# 4. Optimize or request budget increase
# Option A: Remove one cloud (total: $13/mo)
# Option B: Downsize GCP instance (total: $14/mo)
# Option C: Request budget increase to $45/mo

# 5. After optimization, deploy
cloudctl switch bt-avm
terraform apply

cloudctl switch gcp-prod
gcloud deployment-manager deployments create ...

cloudctl switch azure-prod
az deployment group create ...

# 6. DevArmor tracks spend across all clouds
# and alerts if budget is approached
```

---

## Troubleshooting

### Issue: DevArmor Status Shows FAILED

```bash
cloudctl doctor
# ❌ DevArmor Integration: FAILED
# Reason: Cost control service unreachable
```

**Solution:**
```bash
# 1. Check network connectivity
ping github.com

# 2. Clear cache and retry
cloudctl cache-clear

# 3. Retry health check
cloudctl doctor

# 4. If still failing, contact DevArmor team
```

### Issue: Rollback Procedures Unavailable

```bash
cloudctl doctor
# ❌ Rollback procedures: UNAVAILABLE
# Reason: Critical resource missing prevent_destroy
# Location: aws_db_instance.main
```

**Solution:**
```bash
# 1. Add prevent_destroy to critical resource
# terraform/main.tf:
#   resource "aws_db_instance" "main" {
#     ...
#     lifecycle {
#       prevent_destroy = true
#     }
#   }

# 2. Apply changes
terraform apply

# 3. Verify rollback is ready
cloudctl doctor
# ✓ Rollback procedures: READY
```

### Issue: Cost Limit Exceeded

```bash
cloudctl doctor
# ⚠️ Cost Warning: $32/mo (exceeds $30 budget)
# Action: Reduce spend or request budget increase
```

**Solution:**
```bash
# 1. Identify high-cost resources
# (See COST_CONTROL_STANDARDS.md)

# 2. Downsize or terminate unused resources
terraform destroy -target aws_instance.old_app

# 3. Verify cost
cloudctl doctor
# ✓ Current spend: $28/mo

# 4. Proceed with deployment
```

---

## Documentation References

| Document | Purpose | Link |
|----------|---------|------|
| DevArmor Status | Current version, features, health | `~/.claude/projects/-Users-craighoad-Repos/memory/devarmor_status.md` |
| Cost Control Standards | Budget, resource pricing, enforcement | `~/.claude/projects/-Users-craighoad-Repos/memory/COST-CONTROL-STANDARDS.md` |
| Rollback Procedures | 3-phase rollback execution, safety gates | `~/.claude/projects/-Users-craighoad-Repos/memory/ROLLBACK-PROCEDURES.md` |
| Multi-Cloud Orchestration | Cross-cloud sequencing, OIDC validation | `~/.claude/projects/-Users-craighoad-Repos/memory/MULTI-CLOUD-ORCHESTRATION.md` |
| Confluence Rail | How Claude should use cloudctl | https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/ |

---

## Version & Status

**Document Version:** 1.0.0  
**CloudCTL Version:** 4.1.0  
**DevArmor Version:** 1.0.0  
**Last Updated:** May 17, 2026  
**Status:** Production Ready

**Next Review:** June 17, 2026
