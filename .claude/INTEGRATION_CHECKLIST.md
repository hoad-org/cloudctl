# CloudCTL Integration Checklist

**Before EVERY cloud operation, complete this safety checklist.**

This checklist prevents accidental operations in the wrong cloud account, region, or partition. CloudCTL contexts are session-specific — multiple Claude sessions can have different contexts loaded.

---

## Pre-Operation Checklist (MANDATORY)

### Step 1: Read Orientation
- [ ] Read `.claude/CLAUDE.md` — project overview and safety rules
- [ ] Understand which org (bt-avm or fdr-gvc) is required for your task
- [ ] Understand partition differences (aws vs aws-us-gov)

### Step 2: Set Context
```bash
cloudctl switch <org>
```

**Options:**
- `cloudctl switch bt-avm` — BeyondTrust Commercial AWS (us-east-1)
- `cloudctl switch fdr-gvc` — FedRAMP GovCloud (us-gov-east-1)

**Expected Output:**
- Interactive picker shows available accounts
- Select the correct account and role
- Credentials are loaded into current shell session

### Step 3: Verify Context
```bash
cloudctl env
```

**Required Output:**
```
Active Context:
  Organization: [bt-avm or fdr-gvc]
  Account ID:   [12-digit number]
  Role:         [role name]
  Region:       [region code]
  Partition:    [aws or aws-us-gov]
```

**Verification Checklist:**
- [ ] Organization matches your intent (bt-avm for commercial, fdr-gvc for GovCloud)
- [ ] Account ID matches your target environment
- [ ] Role has sufficient permissions for your operation
- [ ] Region is correct for your deployment
- [ ] Partition matches org (aws for bt-avm, aws-us-gov for fdr-gvc)

### Step 4: Check DevArmor Status
```bash
cloudctl doctor
```

**Expected Output:**
- DevArmor connectivity: ✅ Active
- Cost control enforcement: ✅ Active
- Rollback procedures: ✅ Ready
- Multi-cloud orchestration: ✅ Configured

**If any component is ❌ Failed:**
- Stop all operations
- Report status to DevArmor team
- Do not proceed until resolved

### Step 5: Review Confluence Rail
- [ ] Open: https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/
- [ ] Read: "How Claude should use cloudctl across AWS, GCP, Azure"
- [ ] Understand: Context switching patterns for your cloud provider
- [ ] Verify: Error handling procedures

### Step 6: Execute Operation

Only after completing steps 1-5:

```bash
# Example: Terraform plan
terraform plan

# Example: AWS CLI command
aws s3 ls

# Example: List GCP resources
gcloud compute instances list
```

---

## Safety Rules

### Rule 1: Never Skip Context Verification
Running commands with the wrong context loaded causes unintended changes in wrong accounts. Always run `cloudctl env` before any operation.

### Rule 2: Multi-Session Safety
If multiple Claude sessions are active:
- Each session has its own shell environment
- Session A with bt-avm loaded will NOT affect Session B with fdr-gvc loaded
- Always verify context in YOUR session before running commands

### Rule 3: Partition Awareness
- **aws partition** (bt-avm): All AWS regions worldwide
- **aws-us-gov partition** (fdr-gvc): GovCloud only (us-gov-east-1, us-gov-west-1)
- Attempting to use commercial credentials in GovCloud fails silently with `InvalidClientTokenId`

### Rule 4: One Context at a Time
- `cloudctl switch` replaces the active context in the current shell
- Only one context can be active per shell session
- To switch: run `cloudctl switch <other-org>` again

---

## Common Workflows

### Workflow A: Deploy to Commercial AWS (bt-avm)

```bash
# 1. Read orientation
cat .claude/CLAUDE.md

# 2. Set context
cloudctl switch bt-avm
# Select: Account ID, Role (usually AdminAccess), Region (us-east-1)

# 3. Verify
cloudctl env
# ✓ Organization: bt-avm
# ✓ Partition: aws
# ✓ Region: us-east-1

# 4. Check DevArmor
cloudctl doctor
# ✓ All systems nominal

# 5. Proceed
terraform plan
terraform apply  # If approved by GitHub Actions
```

### Workflow B: Deploy to FedRAMP GovCloud (fdr-gvc)

```bash
# 1. Read GovCloud specifics
# CRITICAL: GovCloud is SEPARATE partition from commercial AWS
# Credentials do NOT transfer between partitions

# 2. Set context
cloudctl switch fdr-gvc
# Select: Account ID, Role, Region (us-gov-east-1 or us-gov-west-1 only)

# 3. Verify
cloudctl env
# ✓ Organization: fdr-gvc
# ✓ Partition: aws-us-gov
# ✓ Region: us-gov-* only

# 4. Check DevArmor
cloudctl doctor
# ✓ FedRAMP compliance enforced

# 5. Proceed
terraform plan
terraform apply
```

### Workflow C: Troubleshooting Wrong Context

```bash
# 1. Check current context
cloudctl env
# ❌ Organization: bt-avm (but I need fdr-gvc!)

# 2. Clear and re-set
cloudctl switch fdr-gvc
# Re-select account and role

# 3. Verify again
cloudctl env
# ✓ Organization: fdr-gvc

# 4. Retry operation
terraform plan
```

---

## Troubleshooting

### Q: How do I know if I'm in the wrong context?
**A:** Run `cloudctl env` — it will show the current organization, account, role, region, and partition.

### Q: What happens if I run a command in the wrong context?
**A:** Depends on the operation:
- Terraform: May create resources in wrong account
- AWS CLI: Lists resources from wrong account
- GCP/Azure: Lists resources from wrong project/subscription
- DevArmor may block the operation if it violates cost controls or multi-cloud rules

### Q: Can I have two contexts active in the same shell?
**A:** No. Only one context per shell. To switch contexts, run `cloudctl switch` again.

### Q: How do I log out from all contexts?
**A:** Run `cloudctl cache-clear` to clear all cached credentials.

### Q: What if DevArmor reports a failure?
**A:** Stop all operations immediately. The failure indicates:
- Cost control limit may be exceeded
- Rollback procedures are unavailable
- Multi-cloud orchestration is misconfigured
Contact the DevArmor team before proceeding.

---

## Integration Points

This checklist integrates with:

1. **DevArmor** (Cost Control, Rollback, Multi-Cloud)
   - Documentation: `~/.claude/projects/-Users-craighoad-Repos/memory/devarmor_status.md`
   - Health check: `cloudctl doctor`
   - Purpose: Enforce $30/mo budget, enable safe rollback, coordinate cross-cloud deployments

2. **Confluence Rail** (CloudCTL Best Practices)
   - Link: https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/
   - Purpose: Document how Claude should use cloudctl across clouds
   - Coverage: Context switching, multi-cloud patterns, error handling

3. **GitHub Actions** (Infrastructure Deployments)
   - All infrastructure changes via GitHub Actions only
   - No manual `terraform apply` or `terraform destroy`
   - DevArmor enforces this via CLI-level blocking

4. **Jira Tickets** (Change Tracking)
   - Every infrastructure change must reference an HCP Jira ticket
   - Tickets assigned to Craig Hoad
   - DevArmor tracks tickets for audit trail

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `cloudctl list` | Show configured organizations (bt-avm, fdr-gvc) |
| `cloudctl env` | Show active context (MANDATORY before operations) |
| `cloudctl switch <org>` | Interactive picker to set context |
| `cloudctl login <org>` | (Re)authenticate with SSO |
| `cloudctl doctor` | Check installation and DevArmor status |
| `cloudctl cache-clear` | Clear credentials and SSO tokens |

---

## Version & Status

**Document Version:** 1.0.0  
**Last Updated:** May 17, 2026  
**Status:** Production Ready  
**CloudCTL Version:** 4.1.0

**Next Review:** June 17, 2026
