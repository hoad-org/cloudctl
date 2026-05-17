# CloudCTL Claude Code Documentation Index

Welcome to the CloudCTL `.claude` folder. This folder contains everything a Claude Code session needs to know about CloudCTL, its architecture, and safe cloud operations.

---

## Quick Start (5 minutes)

**New to CloudCTL?** Read in this order:

1. **[CLAUDE.md](./CLAUDE.md)** — Project overview and critical safety rules
2. **[INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md)** — Pre-operation safety checklist (MANDATORY before every cloud command)
3. **[SKILL.md](./SKILL.md)** — CloudCTL skill reference and commands

**Then you're ready to work.**

---

## Complete Documentation

### 1. [CLAUDE.md](./CLAUDE.md) — Project Orientation (PRIMARY ENTRY POINT)

**Read this first in every session.**

Contains:
- **Project Overview:** What CloudCTL is, version 4.1.0, purpose
- **Critical Safety Rules:** Context switching, multi-session safety, partition awareness
- **Configured Organizations:** bt-avm (Commercial AWS), fdr-gvc (GovCloud)
- **Repository Links:** GitHub, Confluence Rail, documentation
- **Integration Requirements:** DevArmor, Confluence
- **Cloud Provider Support Matrix:** AWS, GCP, Azure status
- **Useful Commands:** Common operations reference
- **Development & Testing:** Test suite status (516/516 passing, 81.32% coverage)
- **Common Workflows:** Examples for AWS, GovCloud, GCP, Azure

**Read time:** 8-10 minutes  
**When to read:** Start of every Claude Code session

---

### 2. [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md) — Pre-Operation Safety Checklist

**Use this before EVERY cloud operation.**

Contains:
- **Pre-Operation Checklist:** 6 mandatory steps
  1. Read orientation
  2. Set context (`cloudctl switch`)
  3. Verify context (`cloudctl env`)
  4. Check DevArmor status (`cloudctl doctor`)
  5. Review Confluence Rail
  6. Execute operation
- **Safety Rules:** Critical rules for context management
- **Common Workflows:** A, B, C examples (Commercial AWS, GovCloud, Troubleshooting)
- **Troubleshooting:** Q&A for common issues
- **Integration Points:** DevArmor, Confluence, GitHub Actions, Jira

**Use this:** Before running ANY cloud command (terraform, aws, gcloud, az)  
**Bookmark this:** Most-referenced document

---

### 3. [SKILL.md](./SKILL.md) — CloudCTL Skill Reference

**Skill documentation for Claude Code integration.**

Contains:
- **Purpose:** What the CloudCTL skill does
- **When to Use:** Specific use cases
- **Key Features:** Multi-cloud switching, context verification, DevArmor integration
- **Installation & Setup:** Prerequisites and configuration
- **Usage in Claude Code:** Safe workflows and examples
- **Safety Rules:** Context management rules
- **Commands Reference:** All CloudCTL commands with descriptions
- **Testing:** Test suite overview
- **Troubleshooting:** Common issues and solutions

**Use when:** Working with CloudCTL in Claude Code  
**Reference:** For command syntax and usage patterns

---

### 4. [DEVARMOR_INTEGRATION.md](./DEVARMOR_INTEGRATION.md) — DevArmor Integration Details

**How CloudCTL integrates with DevArmor governance.**

Contains:
- **Overview:** DevArmor purpose and CloudCTL integration points
- **Context Validation Flow:** How contexts are validated
- **Cost Control Integration:** Budget enforcement, resource pricing
- **Rollback Procedures:** 3-phase rollback execution
- **Multi-Cloud Orchestration:** Cross-cloud deployment sequencing, OIDC validation
- **Health Check:** `cloudctl doctor` explained
- **Audit Logging:** What gets logged and why
- **Integration Workflows:** 3 real-world workflows
- **Troubleshooting:** Cost limits, rollback issues

**Use when:** Deploying infrastructure or managing costs  
**Key section:** "Cost Control Integration" for budget awareness

---

### 5. [ARCHITECTURE_REFERENCE.md](./ARCHITECTURE_REFERENCE.md) — Split-Plane Architecture Quick Reference

**Quick reference for CloudCTL's layered architecture.**

Contains:
- **Architecture Overview:** Visual diagram of 5-layer architecture
- **Layer 1: Shell Integration:** How credentials are injected into shell
- **Layer 2: CLI Layer:** Command routing, argument parsing
- **Layer 3: Configuration Management:** 4-level configuration hierarchy
- **Layer 4: Credential Cache:** Where credentials are stored
- **Layer 5: Provider Abstraction:** AWS, GCP, Azure interfaces
- **Data Flow:** Step-by-step context switch flow
- **Independence of Layers:** Why each layer can be tested separately
- **Performance Characteristics:** Target vs actual performance

**Use when:** Understanding how CloudCTL works under the hood  
**Reference:** For architecture decisions and debugging

---

## Integration Reference

### DevArmor Status & Documentation

**Current Status:** v1.0.0 (Production Ready)  
**Location:** `~/.claude/projects/-Users-craighoad-Repos/memory/devarmor_status.md`

Key files:
- `devarmor_status.md` — Current version and enforcement status
- `COST-CONTROL-STANDARDS.md` — Budget and resource pricing
- `ROLLBACK-PROCEDURES.md` — Infrastructure recovery procedures
- `MULTI-CLOUD-ORCHESTRATION.md` — Cross-cloud coordination

### Confluence Rail

**Purpose:** How Claude should use CloudCTL across AWS, GCP, Azure  
**Link:** https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/

**Must read:** Before executing cloud operations

### GitHub & Jira Integration

**GitHub:** All infrastructure via GitHub Actions (no manual apply)  
**Jira:** Every change references HCP ticket assigned to Craig Hoad

---

## Document Overview

| Document | Size | Read Time | Purpose | When |
|----------|------|-----------|---------|------|
| CLAUDE.md | 20KB | 8-10 min | Project orientation | Start of session |
| INTEGRATION_CHECKLIST.md | 7.2KB | 5-7 min | Pre-op safety | Before every command |
| SKILL.md | 9.7KB | 6-8 min | Skill reference | During work |
| DEVARMOR_INTEGRATION.md | 12KB | 8-10 min | Governance integration | Before deploy |
| ARCHITECTURE_REFERENCE.md | 17KB | 10-12 min | Technical reference | For debugging |

**Total reading:** ~40-55 minutes for complete understanding  
**Essential minimum:** 15 minutes (CLAUDE.md + INTEGRATION_CHECKLIST.md)

---

## Quick Navigation by Task

### Task: Deploy to AWS Commercial (bt-avm)

1. Read: [CLAUDE.md](./CLAUDE.md) — "Critical Safety Rules"
2. Read: [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md) — "Workflow A"
3. Execute:
   ```bash
   cloudctl switch bt-avm
   cloudctl env
   terraform plan
   ```

### Task: Deploy to GovCloud (fdr-gvc)

1. Read: [CLAUDE.md](./CLAUDE.md) — "Configured Organisations" and "Partition Awareness"
2. Read: [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md) — "Workflow B"
3. Execute:
   ```bash
   cloudctl switch fdr-gvc
   cloudctl env  # Verify partition: aws-us-gov
   terraform plan
   ```

### Task: Check Cost Status

1. Read: [DEVARMOR_INTEGRATION.md](./DEVARMOR_INTEGRATION.md) — "Cost Control Integration"
2. Execute:
   ```bash
   cloudctl doctor
   ```

### Task: Understand Architecture

1. Read: [ARCHITECTURE_REFERENCE.md](./ARCHITECTURE_REFERENCE.md) — "Layer 1-5"
2. Read: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — For detailed patterns

### Task: Emergency Rollback

1. Read: [DEVARMOR_INTEGRATION.md](./DEVARMOR_INTEGRATION.md) — "Rollback Procedures"
2. Read: `~/.claude/projects/-Users-craighoad-Repos/memory/ROLLBACK-PROCEDURES.md`
3. Execute carefully with `cloudctl env` verification

---

## Safety Reminders

### ⚠️ MANDATORY BEFORE EVERY CLOUD COMMAND

```bash
# 1. Set context
cloudctl switch <org>

# 2. Verify context
cloudctl env
# ✓ Organization matches intent
# ✓ Account matches intent
# ✓ Partition matches intent (aws or aws-us-gov)

# 3. Check DevArmor
cloudctl doctor
# ✓ Cost control active
# ✓ Rollback procedures ready

# 4. THEN run your command
terraform apply
aws s3 ls
gcloud compute instances list
```

### ⚠️ MULTIPLE SESSIONS = DIFFERENT CONTEXTS

Each Claude session has its own shell environment. Session A (bt-avm) will not interfere with Session B (fdr-gvc). **But you must verify YOUR context before running commands.**

### ⚠️ PARTITION AWARENESS

- **aws partition:** bt-avm (Commercial AWS, all regions)
- **aws-us-gov partition:** fdr-gvc (GovCloud only, us-gov-* regions)

Using commercial credentials in GovCloud silently fails.

---

## Common Commands

```bash
# Verify context
cloudctl env

# Switch context
cloudctl switch <org>

# Check health
cloudctl doctor

# List orgs
cloudctl list

# Login/re-authenticate
cloudctl login <org>

# Clear cache
cloudctl cache-clear

# View audit log
tail ~/.cloudctl/audit.log
```

---

## Version & Status

**CloudCTL Version:** 4.1.0  
**Documentation Version:** 1.0.0  
**Status:** Production Ready  
**Last Updated:** May 17, 2026  
**Next Review:** June 17, 2026

---

## Getting Help

### Before You Ask

1. Check: [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md) → "Troubleshooting"
2. Check: [SKILL.md](./SKILL.md) → "Troubleshooting"
3. Run: `cloudctl doctor`
4. View: `~/.cloudctl/audit.log`

### When to Escalate

- DevArmor status is FAILED
- Cost limit appears to be exceeded
- OIDC trust policy validation fails
- Cannot authenticate with SSO

Contact the DevOps or CloudOps team.

---

## File Locations Reference

| File | Purpose | Location |
|------|---------|----------|
| This file | Documentation index | `./.claude/README.md` |
| Project orientation | Main reference | `./.claude/CLAUDE.md` |
| Pre-op checklist | Safety checklist | `./.claude/INTEGRATION_CHECKLIST.md` |
| Skill docs | Skill reference | `./.claude/SKILL.md` |
| DevArmor integration | Governance details | `./.claude/DEVARMOR_INTEGRATION.md` |
| Architecture reference | Technical details | `./.claude/ARCHITECTURE_REFERENCE.md` |
| Master config | User organizations | `~/.config/cloudctl/orgs.yaml` |
| Active context | Current context state | `~/.config/cloudctl/context.json` |
| Audit log | Operation history | `~/.cloudctl/audit.log` |
| DevArmor status | Governance system | `~/.claude/projects/-Users-craighoad-Repos/memory/devarmor_status.md` |

---

## Next Steps

1. **Bookmark [INTEGRATION_CHECKLIST.md](./INTEGRATION_CHECKLIST.md)** — Use before every operation
2. **Read [CLAUDE.md](./CLAUDE.md)** — Start of every session
3. **Bookmark Confluence Rail** — https://darkmothcreative.atlassian.net/wiki/spaces/hoadcloudp/pages/25165826/
4. **Run `cloudctl doctor`** — Verify installation
5. **Start deploying safely!**

---

**Welcome to CloudCTL. Write safe cloud code.**
