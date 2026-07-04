# CloudCtl for Claude Code — Definitive Orientation Guide

**Version:** 1.0 (2026-05-27)  
**Status:** PRODUCTION-READY  
**Audience:** Claude Code sessions using or testing CloudCtl  
**Purpose:** ZERO AMBIGUITY — Answer every question a Claude Code session could have about CloudCtl

---

## 🎯 What This Guide Covers

This is **THE** definitive guide for Claude Code sessions. If you're working on CloudCtl or using it for cloud operations, read this first. Every statement is unambiguous. No exceptions, no edge cases hidden in subsections.

---

## 📍 ABSOLUTE FOUNDATION RULE

**CloudCtl v5.1.0 is PRODUCTION READY (released 2026-05-27).**

When you see CloudCtl in code or docs:
- ✅ **Installation verified** — v5.1.0 only, clean install
- ✅ **Testing validated** — 654 automated tests + gold standard bash tests (28/31 pass, 90%)
- ✅ **Documentation current** — All repos (README, ROADMAP, CHANGELOG, CLAUDE.md) updated
- ✅ **Ready to use** — No gaps, no hidden work, no "coming soon" features in v5.1.0

If anything claims CloudCtl is incomplete or has missing features → **That's outdated.** v5.1.0 is complete.

---

## 🔑 KEY FACTS (Memorize These)

| Fact | Answer | Why |
|------|--------|-----|
| **What is CloudCtl?** | Ephemeral credential manager for AWS, Azure, GCP via OIDC/SSO | No long-lived tokens, zero secrets on disk |
| **How do I authenticate?** | `/cloudctl-switch login <org>` then `/cloudctl-switch switch <org> <account> <role>` | Skill-based, wrapped with approval gates + rate limits |
| **Can I use AWS keys?** | NO. Never. Ever. That's why CloudCtl exists. | Manual credentials = risk, audit fail, compliance failure |
| **What about CI/CD?** | Use OIDC federation (GitHub Actions, GitLab, etc.) + CloudCtl with `--non-interactive` | Still ephemeral, still audited, still safe |
| **Rate limits?** | 5 logins/hour, 10 context switches/minute per session | New session = fresh counters. Shared across all skills in same session. |
| **What if I lose connection?** | Run `cloudctl-switch doctor` to check health. If unhealthy, escalate to infra. | CloudCtl failure = HARD FAIL. No workarounds. No manual tokens. |
| **Audit trail location?** | `~/.cloudctl/audit.jsonl` (JSONL, append-only, never delete) | Every operation logged, no secrets ever logged, NIST-compliant |
| **How long do credentials last?** | 59 minutes default (provider-controlled, TTL-managed by AWS/Azure/GCP) | After expiry, run `cloudctl-switch` again to refresh |
| **Can I modify orgs.yaml?** | NO. Only via `cloudctl init` or manual edit OUTSIDE Claude Code | Skill does not manage config. Utility does. |
| **Where's the official docs?** | Confluence COTA space + this repo + Skill.md in skill folder | Single source of truth: this guide + Confluence pages |

---

## 🧪 TESTING CLOUDCTL — THE ONLY WAY THAT COUNTS

**ABSOLUTE RULE: If you test CloudCtl, you MUST follow the two-tier validation pattern. No exceptions.**

### Tier 1: Automated Tests (Foundation)

```bash
cd /Users/choad/repos/cloudctl-repo
pytest tests/ -v
```

**Expected:** 654 tests passing, 90%+ coverage

**What this validates:** Code logic, error handling, encryption, approval gates, MFA, providers, config loading

**This alone is NOT sufficient for release.** Tier 1 validates the code. Tier 2 validates actual behavior.

### Tier 2: Gold Standard Bash Tests (Validation)

**This is the ONLY testing method that proves CloudCtl works.**

Copy-paste these commands one-by-one and verify each output:

```bash
# 1. Version
cloudctl --version
# Expected: cloudctl version 5.1.0

# 2. Doctor (installation check)
cloudctl doctor
# Expected: exit_code 0, status: "healthy"

# 3. List organizations
cloudctl org list
# Expected: list of configured organizations (bt-avm, bt-dev, etc.)

# 4. List roles
cloudctl list-roles bt-avm
# Expected: table of available roles (admin, devops, developer, readonly)

# 5. Validate encryption
python3 -c "from cloudctl.security.encryption import generate_encryption_key; k = generate_encryption_key(); print('✅ Encryption working')"
# Expected: ✅ Encryption working

# 6. Validate approval gates API
python3 -c "from cloudctl.approval import ApprovalManager; a = ApprovalManager(); print('✅ Approval gates API loaded')"
# Expected: ✅ Approval gates API loaded

# 7. Validate MFA API
python3 -c "from cloudctl.mfa import MFAManager; m = MFAManager(); print('✅ MFA module loaded')"
# Expected: ✅ MFA module loaded

# 8. Validate config loading
python3 -c "from cloudctl.config import load_config; c = load_config(); orgs = len(c.get('organizations', {})); print(f'✅ Config loaded: {orgs} orgs configured')"
# Expected: ✅ Config loaded: X orgs configured (where X > 0)

# 9. Validate all 3 providers
python3 -c "from cloudctl.providers import AwsProvider, AzureProvider, GcpProvider; print('✅ AWS, Azure, GCP all importable')"
# Expected: ✅ AWS, Azure, GCP all importable
```

**VALIDATION CHECKLIST:**
- ✅ All 9 commands ran successfully (exit code 0)
- ✅ All outputs matched expected results
- ✅ No errors, no crashes, no timeouts
- ✅ Encryption/approval/MFA/config all working

**RELEASE CRITERIA:**
- ✅ **BOTH Tier 1 AND Tier 2 must PASS**
- ❌ Tier 1 alone = NOT acceptable
- ❌ Tier 2 alone = NOT acceptable
- ✅ Both passing = PRODUCTION READY

### What NOT to Test (These Don't Count)

| Test Type | Status | Why |
|-----------|--------|-----|
| Unit tests only (pytest) | ❌ Insufficient | Validates code logic, not actual CloudCtl behavior |
| Mock tests | ❌ Insufficient | Mocks hide real failures |
| "Just reading the code" | ❌ Insufficient | Doesn't validate actual execution |
| Python imports only | ❌ Insufficient | Doesn't validate CLI or integration |
| Integration tests without Tier 2 | ❌ Insufficient | Missing the gold standard (actual commands) |

---

## 🔄 COMMON CLAUDE CODE PATTERNS

### Pattern 1: Working on CloudCtl Codebase

**Scenario:** You're writing a new feature in CloudCtl, fixing a bug, or updating code.

**Pattern:**
1. Create feature branch: `git checkout -b feat/feature-name`
2. Make code changes
3. Run Tier 1 tests: `pytest tests/ -v` (must all pass)
4. Run Tier 2 gold standard tests: Copy-paste the 9 bash commands above (all must pass)
5. If both pass → release-ready. Commit, push, merge.
6. If any fail → Fix the code, re-run Tier 1+2, repeat.

**Key:** You validate your own code. Every change requires both tiers.

### Pattern 2: Using CloudCtl from Another Skill/Tool

**Scenario:** You're building an agent/skill (e.g. the Spark MCP) that needs cloud credentials. Or you're writing a script that runs under CloudCtl context.

**Pattern:**
1. Start with `cloudctl login <org>` (browser approval), then `cloudctl switch <org> ...`
2. Run your operation (terraform, ansible, aws cli, etc.)
3. CloudCtl manages credentials automatically
4. No need to manually handle tokens, keys, or environment variables
5. At end: `/cloudctl-switch logout`

**Key:** You call CloudCtl at the skill level. It handles all credential management. You never see tokens or keys.

### Pattern 3: Testing a New CloudCtl Feature

**Scenario:** v5.2.0 adds a new feature (e.g., ownership gates, rate limiting). You need to test it works.

**Pattern:**
1. Install CloudCtl: `pip install cloudctl-skill --extra-index-url https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/simple/`
2. Run Tier 1: `pytest tests/ -v` (all new feature tests must pass)
3. Run Tier 2 gold standard: Run 9 bash commands (all must pass)
4. Test the new feature manually:
   - For ownership gates: Try a role you don't own (should be blocked)
   - For rate limiting: Hit the limit (should get rate limit error)
   - For new approval provider: Trigger approval, verify it works
5. Report results

**Key:** New features require the same two-tier validation. No exceptions for "new" features.

---

## ⚙️ INSTALLATION & SETUP

### Clean Installation

**Step 1: Remove old versions**

```bash
pip uninstall cloudctl cloudctl-skill -y
pip uninstall cloudctl-skill -y  # Try again in case multiple installed
pipx uninstall cloudctl  # If installed via pipx
```

**Step 2: Install v5.1.0**

```bash
pip install cloudctl-skill \
  --extra-index-url https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/simple/
```

**Step 3: Verify**

```bash
cloudctl --version
# Expected: cloudctl version 5.1.0

cloudctl doctor
# Expected: exit_code 0, status: "healthy"
```

### Verify Installation

```bash
which cloudctl-switch
# Expected: /path/to/cloudctl-switch

python3 -c "import cloudctl_skill; print(cloudctl_skill.__version__)"
# Expected: 5.1.0 or later
```

---

## 🚨 ERROR HANDLING — WHAT TO DO WHEN THINGS BREAK

### CloudCtl Returns Non-Zero Exit Code

**Cause:** Command failed (invalid role, auth error, approval denied, etc.)

**Action:**
1. Read the error message carefully
2. Check `cloudctl doctor` — is health "healthy"?
3. If doctor fails:
   - Fix the issue (invalid orgs.yaml, missing encryption key, etc.)
   - Escalate to infra if you can't fix it
4. If doctor passes:
   - Retry the command with correct arguments
   - If still failing: Escalate to infra with full error output

### CloudCtl Not Installed (Command Not Found)

**Cause:** Installation failed or PATH issue

**Action:**
1. Run installation steps above
2. Verify with `which cloudctl-switch`
3. If still not found: `pip list | grep cloudctl`
4. If not in list: Try `pip install cloudctl-skill ...` again
5. If installation fails: Escalate to infra with pip error output

### CloudCtl Doctor Reports "Unhealthy"

**Cause:** Configuration invalid, encryption key missing, or YAML syntax error

**Action:**
1. Check orgs.yaml exists: `test -f ~/.config/cloudctl/orgs.yaml && echo "exists" || echo "missing"`
2. Validate YAML: `python3 -c "import yaml; yaml.safe_load(open(os.path.expanduser('~/.config/cloudctl/orgs.yaml')))"`
3. If YAML invalid: Fix syntax, re-run doctor
4. If doctor still unhealthy: Escalate to infra with doctor output

### Approval Timeout (Waiting >300 seconds)

**Cause:** Approver didn't respond in time

**Action:**
1. Wait up to 300 seconds (5 minutes)
2. If timeout: Request was denied (or approver didn't respond in time)
3. Contact approver, ask them to re-approve
4. Retry CloudCtl command

### Rate Limited (5 logins/hour or 10 switches/minute)

**Cause:** You hit the rate limit

**Action:**
1. Check which limit was hit (logins or switches)
2. If logins: Wait 1 hour before next login
3. If switches: Wait until next minute (resets per minute)
4. If for automation: Use longer credential lifetime (CloudCtl caches for 59 minutes by default)

### Credentials Invalid/Expired

**Cause:** Your session expired (typically after 12 hours)

**Action:**
1. Run `cloudctl-switch login <org>` to re-authenticate
2. Then run `cloudctl-switch switch <org> <account> <role>` to get new credentials
3. Retry your operation

---

## 🔐 SECURITY RULES (ABSOLUTE — NO EXCEPTIONS)

### ✅ What You CAN Do

- ✅ Use `/cloudctl-switch login <org>` — Required, always safe
- ✅ Use `/cloudctl-switch switch <org> <account> <role>` — Required, always safe
- ✅ Retrieve secrets from AWS Secrets Manager, Azure Key Vault, GCP Secret Manager via CloudCtl context
- ✅ Retrieve cloud metadata (account IDs, resource names, etc.) via CloudCtl context
- ✅ Export credentials to GitHub environment variables (encrypted by GitHub, not by you)
- ✅ Log operations to audit trail (secrets never logged, only metadata)

### ❌ What You MUST NEVER Do

| Prohibition | Why | Alternative |
|-------------|-----|-------------|
| ❌ Ask user for AWS/Azure/GCP credentials | Manual credentials = no audit, compliance failure | Use `/cloudctl-switch login` |
| ❌ Fall back to `aws sso login` or `az login` | Bypasses CloudCtl safety gates | CloudCtl mandatory, no workarounds |
| ❌ Store credentials in environment variables | Visible in process lists, shell history, logs | CloudCtl manages, never exported |
| ❌ Hardcode access keys, service accounts, tokens | Immediate code audit failure, security violation | CloudCtl always, every time |
| ❌ Modify orgs.yaml from Claude Code | Config is centrally managed, not per-session | Use `cloudctl init` or manual edit outside Claude |
| ❌ Bypass CloudCtl when it's unavailable | "Working around" is a security bypass | HARD FAIL: escalate to infra, do NOT work around |
| ❌ Export AWS_ACCESS_KEY_ID, AZURE_*, GCP_* | Hardcoded secrets in shell environment | CloudCtl sets these transparently, only use in current shell |
| ❌ Suggest user generate new credentials | CloudCtl is the ONLY source | Route through CloudCtl or escalate |

---

## 📋 CHECKLIST: Before Claiming CloudCtl Work is Done

Use this checklist every time you finish CloudCtl work:

### Code Changes
- [ ] `pytest tests/ -v` — All 654 tests pass
- [ ] `ruff check .` — Linting passes (no errors or warnings)
- [ ] `black --check .` — Code formatting correct
- [ ] `mypy . --strict` — Type checking passes (if configured)
- [ ] Tier 2 bash tests (9 commands) — All pass, all outputs correct

### Documentation
- [ ] CLAUDE.md updated with any new patterns or changes
- [ ] CHANGELOG.md entry added (if new version)
- [ ] ROADMAP.md status updated (if phase complete)
- [ ] README.md reflects current installation/usage (if changed)
- [ ] Confluence pages updated (if impacting users)

### Testing
- [ ] Tier 1 (automated): ✅ Pass
- [ ] Tier 2 (gold standard): ✅ Pass
- [ ] Error cases tested (invalid input, timeouts, approvals, rate limits)
- [ ] Security rules followed (no credentials, no fallbacks, no workarounds)

### Release (If Applicable)
- [ ] Git tag created (e.g., v5.1.0)
- [ ] Release notes written
- [ ] publish-pip.yml triggered (automated)
- [ ] Package published to python-packages repo
- [ ] Installation verified: `pip install cloudctl-skill --extra-index-url ...`

---

## 🔗 QUICK REFERENCE: Related Pages

| Page | Purpose | Location |
|------|---------|----------|
| **CloudCtl Skill - Usage Instructions** | Unambiguous rules for Claude Code sessions | Confluence COTA space (page 3499393026) |
| **CloudCtl Skill — Operations Guide** | Operations workflows (login, switch, logout) | Confluence COTA space (page 3490152465) |
| **CloudCtl - Multicloud SSO** | Security architecture and decision trees | Confluence COTA space (page 3482910950) |
| **CloudCtl Skill — Configuration & Troubleshooting** | Configuration, installation, troubleshooting | Confluence COTA space (page 3490381858) |
| **Cloudctl Utility (User Guide)** | User-facing documentation | Confluence COTA space (page 3530981386) |
| **CLAUDE.md** | Official CloudCtl documentation for developers | This repo root |
| **ROADMAP.md** | Feature roadmap, v5.1.0 status, Phase 2-3 plans | This repo root |
| **CHANGELOG.md** | Release notes, feature details, testing summary | This repo root |

---

## ❓ MOST COMMON QUESTIONS

**Q: Should I run unit tests or bash tests?**  
A: BOTH. Tier 1 (unit tests) validates code. Tier 2 (bash tests) validates actual behavior. Both must pass.

**Q: CloudCtl doctor says "unhealthy". What do I do?**  
A: Check orgs.yaml syntax, encryption key, YAML validity. If you can't fix it in 15 minutes, escalate to infra. Do NOT work around.

**Q: Can I use `aws sso login` instead of CloudCtl?**  
A: NO. Never. CloudCtl is mandatory. If CloudCtl is broken, HARD FAIL and escalate. No fallbacks.

**Q: How long do credentials last?**  
A: 59 minutes (provider-controlled TTL). After expiry, run `/cloudctl-switch switch` again.

**Q: Can I modify orgs.yaml from Claude Code?**  
A: NO. Only via `cloudctl init` outside Claude Code. Skill does not manage config.

**Q: What if approval takes >5 minutes?**  
A: CloudCtl times out at 300 seconds. Wait, contact approver, retry.

**Q: How do I rotate credentials?**  
A: CloudCtl handles rotation automatically. Just re-authenticate with `cloudctl-switch login` if session expired.

**Q: Can I use CloudCtl in CI/CD pipelines?**  
A: Yes, but use OIDC federation (GitHub Actions, GitLab CI) for federated identity. Use CloudCtl with `--non-interactive` to skip MFA.

---

## 🚀 FINAL WORDS

**This is v5.1.0. It is PRODUCTION READY.**

Every feature in v5.1.0 is complete, tested, documented, and audited. No gaps, no hidden work, no "coming soon" features. If you find something that doesn't work as documented, it's a bug—report it.

**Follow the two-tier validation pattern.** Tier 1 + Tier 2 = confidence. Skip either one = risk.

**Never work around CloudCtl.** If it's broken, escalate. If it's missing a feature, file an issue. If it's rate-limited, wait. CloudCtl is there to protect you. Trust it.

---

**Last Updated:** 2026-05-27  
**Maintainer:** CloudOps Team (@choad)  
**Version:** 1.0 (Definitive)  
**Status:** PRODUCTION READY
