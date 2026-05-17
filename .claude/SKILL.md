---
name: CloudCTL Skill
description: Multi-cloud context manager for Claude Code workflows
version: 2.0.0
status: Production Ready
created: 2026-05-17
---

# CloudCTL Skill for Claude Code

**Skill Name:** CloudCTL Context Manager  
**Version:** 2.0.0  
**Status:** Production Ready  
**Repository:** https://github.com/rhyscraig/aws-terraform-infra-cloudops-awsctl

---

## Purpose

The CloudCTL skill enables Claude Code to manage cloud contexts across AWS (Commercial and GovCloud), GCP, and Azure. It provides:

- **Unified Context Management:** Single interface to switch between cloud accounts and roles
- **Multi-Cloud Support:** AWS (aws, aws-us-gov partitions), GCP, Azure
- **Safe Credential Export:** Credentials isolated to shell session, never stored in code
- **Context Verification:** `cloudctl env` validates context before operations
- **DevArmor Integration:** Cost control, rollback procedures, multi-cloud orchestration
- **Audit Logging:** Sensitive operations logged for compliance

---

## When to Use This Skill

Use CloudCTL in Claude Code sessions when you need to:

1. **Switch cloud contexts** — Set active AWS account, GCP project, or Azure subscription
2. **Verify context** — Confirm you're operating in the correct environment
3. **Authenticate** — Re-authenticate with cloud provider SSO
4. **Check health** — Validate CloudCTL installation and DevArmor status
5. **Clear cache** — Reset credentials and context

**Example commands:**
```bash
cloudctl switch bt-avm        # Interactive picker for BeyondTrust Commercial
cloudctl switch fdr-gvc       # Interactive picker for FedRAMP GovCloud
cloudctl env                  # Verify active context
cloudctl doctor               # Check health and DevArmor status
```

---

## Key Features

### 1. Multi-Cloud Context Switching

**AWS (Commercial):**
```bash
cloudctl switch bt-avm
# Prompts for: Account ID → Role → Region
# Exports: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_PROFILE
```

**AWS GovCloud (FedRAMP):**
```bash
cloudctl switch fdr-gvc
# Prompts for: Account ID → Role → Region (us-gov-east-1 or us-gov-west-1)
# Exports: Same as commercial AWS but in aws-us-gov partition
```

**GCP:**
```bash
cloudctl switch gcp-prod
# Prompts for: Project → Role → Region
# Exports: GOOGLE_CLOUD_PROJECT, GOOGLE_OAUTH_ACCESS_TOKEN, GCLOUD_PROJECT
```

**Azure:**
```bash
cloudctl switch azure-prod
# Prompts for: Subscription → Role → Region
# Exports: AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, ARM_ACCESS_TOKEN
```

### 2. Context Verification

Before running ANY cloud operation:

```bash
cloudctl env
# Output:
#   Organization: bt-avm
#   Account:      123456789012
#   Role:         AdminAccess
#   Region:       us-east-1
#   Partition:    aws
#   Provider:     aws
```

### 3. DevArmor Integration

```bash
cloudctl doctor
# Checks:
# ✓ Python environment
# ✓ Cloud provider CLI tools (aws, gcloud, az)
# ✓ Shell integration
# ✓ Configuration files
# ✓ DevArmor connectivity
# ✓ Cost control status
# ✓ Rollback procedures
# ✓ Multi-cloud orchestration
# ✓ GitHub OIDC trust policies
# ✓ Jira integration
```

### 4. Configuration Hierarchy

CloudCTL loads configuration from 4 levels (highest to lowest priority):

1. **Environment Variables** — `CLOUDCTL_ORG`, `CLOUDCTL_REGION`
2. **Repo Config** — `./.claude/cloudctl.json`
3. **Master Config** — `~/.config/cloudctl/orgs.yaml`
4. **Code Defaults** — Built-in schema and defaults

See `.claude/ARCHITECTURE_REFERENCE.md` for details.

### 5. Audit Logging

All sensitive operations logged to `~/.cloudctl/audit.log`:
```
2026-05-17T14:32:45Z | CONTEXT_SWITCH | org=bt-avm | account=123456789012
2026-05-17T14:32:50Z | CREDENTIAL_EXPORT | account=123456789012 | role=AdminAccess
```

---

## Installation & Setup

### Prerequisites

- **Python:** 3.12 or later
- **Cloud CLIs:** 
  - AWS: `aws-cli` v2
  - GCP: `gcloud` CLI
  - Azure: `az` CLI
- **Shell:** bash, zsh, or fish (shell integration required)

### Installation

```bash
# From source
git clone https://github.com/rhyscraig/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl

# Install development dependencies
pip install -e .[dev]

# Run installation wizard
cloudctl init

# Or manual setup
install.sh  # macOS/Linux
install.ps1 # Windows
```

### Configuration

**Master config:** `~/.config/cloudctl/orgs.yaml`

```yaml
orgs:
  - name: bt-avm
    provider: aws
    partition: aws
    sso_start_url: https://beyond-trust.awsapps.com/start
    sso_region: us-east-1
    allowed_regions:
      - us-east-1
      - us-west-2
    default_region: us-east-1
    default_role: AdminAccess

  - name: fdr-gvc
    provider: aws
    partition: aws-us-gov
    sso_start_url: https://beyond-trust.awsapps.com/start
    sso_region: us-gov-east-1
    allowed_regions:
      - us-gov-east-1
    default_region: us-gov-east-1
    default_role: AdminAccess
```

---

## Usage in Claude Code

### Safe Workflow

1. **Always switch context first:**
   ```bash
   cloudctl switch bt-avm
   cloudctl env  # Verify before proceeding
   ```

2. **Run cloud operations:**
   ```bash
   terraform plan
   aws s3 ls
   gcloud compute instances list
   ```

3. **Verify DevArmor status:**
   ```bash
   cloudctl doctor
   ```

4. **Check audit log:**
   ```bash
   tail ~/.cloudctl/audit.log
   ```

### Example: Terraform Deployment

```bash
# 1. Read safety checklist
cat .claude/INTEGRATION_CHECKLIST.md

# 2. Set context
cloudctl switch bt-avm
cloudctl env
# ✓ Organization: bt-avm
# ✓ Partition: aws
# ✓ Region: us-east-1

# 3. Check DevArmor
cloudctl doctor
# ✓ All systems nominal

# 4. Plan
terraform plan

# 5. Create PR (GitHub Actions runs apply)
git add .
git commit -m "HCP-123: Add new resource"
git push origin feature/new-resource

# 6. Merge PR → GitHub Actions → terraform apply
# (CloudCTL used in GitHub Actions runner)
```

---

## Safety Rules

### CRITICAL: Always Switch First

Multiple Claude sessions can have different contexts. Running commands in the wrong context causes unintended changes.

```bash
# WRONG:
terraform apply  # What context is this in?

# RIGHT:
cloudctl switch bt-avm
cloudctl env    # Verify first
terraform apply
```

### Rule: One Context Per Session

A shell session can only have one active context. To switch:

```bash
cloudctl switch fdr-gvc  # Replaces previous context
cloudctl env             # Verify new context
```

### Rule: Partition Awareness

- **aws partition:** All AWS commercial regions
- **aws-us-gov partition:** GovCloud only (us-gov-east-1, us-gov-west-1)

Attempting to use commercial credentials in GovCloud fails silently.

### Rule: DevArmor Validation

Before infrastructure changes:

```bash
cloudctl doctor
# ✓ Cost control active ($30/mo budget)
# ✓ Rollback procedures ready
# ✓ Multi-cloud orchestration configured

# If anything is ❌: Stop and investigate
```

---

## Integration with DevArmor

CloudCTL integrates with DevArmor (v1.0.0, production-ready) for:

- **Cost Control:** Enforces $30/mo budget
- **Rollback:** 3-phase infrastructure state recovery
- **Multi-Cloud:** Cross-cloud deployment sequencing
- **Audit Trail:** Logs sensitive operations

See `.claude/DEVARMOR_INTEGRATION.md` for details.

---

## Documentation

| Document | Purpose |
|----------|---------|
| `.claude/CLAUDE.md` | Project overview and orientation |
| `.claude/INTEGRATION_CHECKLIST.md` | Pre-operation safety checklist |
| `.claude/DEVARMOR_INTEGRATION.md` | DevArmor integration details |
| `.claude/ARCHITECTURE_REFERENCE.md` | Split-plane architecture reference |
| `docs/ARCHITECTURE.md` | Detailed design patterns |
| `docs/DEPLOYMENT.md` | Installation and setup guide |
| `docs/MULTI_CLOUD.md` | Cloud provider comparison |
| `README.md` | User-facing documentation |

---

## Troubleshooting

### Issue: `cloudctl: command not found`

**Solution:**
1. Verify installation: `pip list | grep cloudctl`
2. Check shell integration: `grep cloudctl ~/.zshrc`
3. Restart shell: `exec zsh` or `exec bash`

### Issue: Wrong context loaded

**Solution:**
```bash
cloudctl env
# Shows wrong org/account

cloudctl switch <correct-org>
cloudctl env
# Verify before proceeding
```

### Issue: AWS SSO login fails

**Solution:**
```bash
aws sso logout --sso-session bt-avm
cloudctl login bt-avm
```

### Issue: GCP credentials expired

**Solution:**
```bash
gcloud auth login
gcloud auth application-default login
cloudctl login gcp-prod
```

### Issue: DevArmor status FAILED

**Solution:**
```bash
cloudctl cache-clear
cloudctl doctor
# If still failing: Contact DevArmor team
```

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| `cloudctl list` | List configured organizations |
| `cloudctl env` | Show active context |
| `cloudctl switch <org>` | Interactive context switcher |
| `cloudctl login <org>` | (Re)authenticate with SSO |
| `cloudctl logout <org>` | Logout and clear tokens |
| `cloudctl doctor` | System health check |
| `cloudctl cache-clear` | Clear credentials and context |
| `cloudctl status` | Show provider status |

---

## Testing

CloudCTL has 516 tests (100% passing) with 81.32% coverage.

```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run specific test
pytest tests/test_aws.py -v

# Run health check
cloudctl doctor
```

---

## Version & Support

**CloudCTL Version:** 4.1.0  
**Skill Version:** 2.0.0  
**Status:** Production Ready  
**Python:** 3.12+  
**License:** MIT

**Next Release:** June 17, 2026

---

## Links

- **GitHub:** https://github.com/rhyscraig/aws-terraform-infra-cloudops-awsctl
- **Confluence Rail:** https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/
- **DevArmor Status:** `~/.claude/projects/-Users-craighoad-Repos/memory/devarmor_status.md`

---

**See also:** `.claude/CLAUDE.md` for complete project orientation.
