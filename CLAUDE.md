# Claude Instructions — cloudctl Context Safety

---

# 🚨 TESTING REQUIREMENT: GOLD STANDARD IS USER-SIMULATED TESTING

## CRITICAL: Two-Tier Testing Requirement

### Tier 1: Automated Tests (REQUIRED Foundation)
- ✅ **MUST RUN:** `pytest tests/ -v` — all tests must pass
- ✅ **MUST VERIFY:** Code coverage 90%+
- ✅ **MUST CHECK:** All unit tests, integration tests, CI/CD pipeline tests
- ✅ **REQUIRED:** Commit should not break any existing tests

**BUT: Automated tests alone are NOT sufficient for release.**

### Tier 2: User-Simulated Testing (GOLD STANDARD - Required for Release)
- ✅ **GOLD STANDARD:** Run actual `cloudctl` commands one-by-one via bash
- ✅ **GOLD STANDARD:** Validate output by parsing stdout/stderr
- ✅ **GOLD STANDARD:** Test every single command and flag combination
- ✅ **GOLD STANDARD:** Document what was tested and actual output received
- ✅ **GOLD STANDARD:** Prove the tool works in real scenarios

**User-simulated testing is the definitive proof the tool actually works.**

### Testing Decision Matrix

| Scenario | Automated Tests | User-Simulated | Release Ready? |
|----------|---|---|---|
| Both pass | ✅ | ✅ | **YES** ✅ |
| Only automated pass | ✅ | ❌ | **NO** — Unknown if tool works |
| Only user-simulated pass | ❌ | ✅ | **NO** — Missing foundation |
| Both fail | ❌ | ❌ | **NO** — Do not release |

### Why This Two-Tier Requirement Exists

**Automated tests** provide code quality foundation, but **cannot verify:**
- Actual credential handling in live shells
- Real approval gate workflows with actual user interaction
- AWS SSO authentication against real identity providers
- Shell environment exports to parent process
- Multi-cloud context switching in real scenarios

**User-simulated testing** provides the definitive proof:
- Commands work as users will use them
- Output is human-readable and correct
- All flags and options function properly
- Credentials are handled safely
- Multi-cloud switching works in practice

**Both tiers together ensure release quality.**

### Complete Testing Checklist

#### Step 1: Run Automated Tests (Foundation)
```bash
cd /Users/choad/repos/cloudctl-repo
poetry run pytest tests/ -v          # Must pass all tests
poetry run pytest --cov=src/cloudctl # Must be 90%+
```

**If automated tests fail:** Stop. Fix the code, re-run tests. Do not proceed to user-simulated testing.

#### Step 2: Run User-Simulated Tests (Gold Standard)

When automated tests pass, proceed with user-simulated command testing:

```bash
# 1. Run the actual command (one by one)
cloudctl-switch login bt-avm --no-interactive

# 2. Capture output
# Expected: Exit code 0, message "Logged in to bt-avm"

# 3. Validate output
cloudctl env
# Expected: Shows bt-avm, account 235494790978, role admin, TTL remaining

# 4. Test every flag and option
cloudctl list-roles --assigned
# Expected: Shows only roles you can assume

cloudctl list-roles --format json
# Expected: Valid JSON output, parseable

# 5. Test error cases
cloudctl list-roles invalid-org
# Expected: Error with helpful message, exit code 1

# 6. Document all results
# ✅ TEST 1: cloudctl login       PASS
# ✅ TEST 2: cloudctl env         PASS
# ✅ TEST 3: cloudctl list-roles  PASS
# ✅ TEST 4: cloudctl doctor      PASS
# ⚠️  TEST 5: cloudctl exec       EXPECTED FAIL (needs AWS enrollment)
```

### Complete Testing Example

See `/tmp/cloudctl-v5.1.0-test-results.md` and `/tmp/CLOUDCTL_V5.1.0_FINAL_STATUS.txt` 
for reference implementations of proper two-tier testing (automated + user-simulated).

### Release Checklist

- [ ] `poetry run pytest tests/ -v` — All tests pass
- [ ] `poetry run pytest --cov` — Coverage 90%+
- [ ] `cloudctl doctor` — System check passes
- [ ] User-simulated testing complete — All commands tested one-by-one
- [ ] Test results documented — See test results files
- [ ] No secrets leaked in output — Verified
- [ ] All features working — Approval gates, context switching, multi-cloud

### Test Results Location

After running user-simulated tests, save results to:
```bash
/tmp/cloudctl-v5.1.0-test-results.md          # Individual test cases
/tmp/cloudctl-v5.1.0-all-commands-test.md     # All commands matrix
/tmp/CLOUDCTL_V5.1.0_FINAL_STATUS.txt         # Final release report
```

These files serve as:
- Release documentation
- Verification of user-simulated testing completion
- Reference for future testing runs
- Evidence that all commands work as expected

---

## CRITICAL: Always Switch Context Before Running Commands

**You MUST run `cloudctl switch` before executing ANY AWS command in this repository.**

Multiple Claude sessions can be active simultaneously. Each session may have a different AWS account and role loaded into the shell environment. Running a command intended for account A while the context is set to account B causes unintended changes in the wrong account.

### Rule: Switch First, Always

```bash
# ALWAYS do this first — never skip it
cloudctl switch <org> <account-id> <role>

# Verify the context before running anything
cloudctl env

# THEN run your command
terraform plan
aws s3 ls
```

### Configured Organisations

| Alias   | Partition     | SSO Region     | Description                              |
|---------|---------------|----------------|------------------------------------------|
| bt-avm  | aws           | us-east-1      | BeyondTrust AVM — Commercial AWS         |
| fdr-gvc | aws-us-gov    | us-gov-east-1  | FedRAMP GovCloud — AWS GovCloud (US)     |

### Example: Switching to BeyondTrust Commercial

```bash
cloudctl switch bt-avm
cloudctl env  # confirm context before proceeding
```

### Example: Switching to FedRAMP GovCloud

```bash
cloudctl switch fdr-gvc
cloudctl env  # confirm context before proceeding
```

## Why This Matters

- `cloudctl` stores the active org/account/role/region in `~/.config/cloudctl/context.json`
- The shell function `cloudctl` exports credentials into the current shell session
- If two Claude sessions are running: Session A may have `bt-avm` loaded, Session B may have `fdr-gvc` loaded
- Without explicit switching, the **wrong credentials are used silently** — there is no warning
- GovCloud (`fdr-gvc`) commands run in Commercial (`bt-avm`) context will fail with `InvalidClientTokenId` or worse, operate on the wrong partition

## Checklist Before Any AWS/Terraform Operation

1. `cloudctl switch <org>` — set the correct org context
2. `cloudctl env` — verify account ID, role, region match your intent
3. If using Terraform: confirm `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` point to the right account
4. Never assume the previous Claude session left the correct context active

## Shell Wrapper Architecture

- `cloudctl` — shell function that captures `export K=V` output and applies it to the current shell
- `_cloudctl_bin` — raw Python binary; does NOT modify parent shell environment
- Always use the `cloudctl` shell function (not `_cloudctl_bin`) to switch contexts

## Useful Commands

```bash
cloudctl org list          # show configured orgs (also: cloudctl list)
cloudctl env               # show active context (org, account, role, region)
cloudctl switch <org>      # interactive account/role picker for an org
cloudctl login <org>       # (re)authenticate with SSO
cloudctl cache-clear       # clear cached credentials and SSO tokens
cloudctl doctor            # check installation and config health
```

---

# Claude App Management Guide

## Overview

cloudctl is an enterprise multi-cloud identity and context manager supporting AWS, Azure, and GCP. This guide helps Claude instances manage the codebase, respond to user requests, and maintain the application.

## Quick Start for Claude

### 1. Understand the Architecture

**Core Components:**
- `src/cloudctl/` — Main package (31 modules)
  - `cli.py` — Command dispatcher and argument parsing
  - `config.py` — Configuration loading and validation
  - `shell.py` — Shell integration (bash/zsh/fish/PowerShell)
  - `providers/` — Cloud provider implementations (AWS, Azure, GCP)
  - `commands/` — Command implementations (login, switch, exec, etc.)
  - `context_manager.py` — State persistence and context switching
  - `registry.py` — Organization registry loader
  - `guardrails.py` — Security controls and audit logging

**Testing:**
- `tests/` — 431 automated tests covering all features
- Run with: `poetry run pytest tests/ -v`

**Configuration:**
- `pyproject.toml` — Package metadata, dependencies, version (currently 5.1.0)
- `Makefile` — Build targets and development tasks
- `MIGRATION.md` — Upgrade guide (awsctl v3.x → cloudctl v4.0.0)

**Documentation:**
- `README.md` — User-facing installation and usage guide (GitHub)
- `ROADMAP.md` — Feature roadmap and development status
- Confluence Wiki — Comprehensive user guide and examples
  - URL: https://beyondtrust.atlassian.net/wiki/spaces/COTA/pages/3530981386
  - Content: 40+ sections, 5800+ words, complete reference
- `CLAUDE.md` — This file (Claude developer instructions)

### 2. Handle Common User Requests

**"I want to use cloudctl"**
→ Direct to: `pip install cloudctl` and run `cloudctl init`

**"How do I switch AWS accounts?"**
→ Guide them: `cloudctl switch <org>` then `cloudctl env` to verify

**"What's new in v4.0.0?"**
→ See: Major rename from awsctl to cloudctl, multi-cloud support (AWS/Azure/GCP equally)

**"I'm upgrading from v3.x"**
→ See: [MIGRATION.md](MIGRATION.md) for complete upgrade instructions

**"The tool isn't working"**
→ Run diagnostic: `cloudctl doctor`

### Current Version: 5.1.0 (Latest - Released 2026-05-27)

**What's New in v5.1.0:**
- ✅ Error Handling Framework — 9 error types with recovery suggestions
- ✅ Config Encryption — AES-256 field-level encryption
- ✅ List Roles Command — Discover available and assigned IAM roles
- ✅ Comprehensive Testing
- ✅ Complete Documentation — Confluence wiki + updated README

**Installation:**
```bash
pip install cloudctl-skill \
  --extra-index-url https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/simple/
```

**Verify Installation:**
```bash
cloudctl-switch doctor
# Expected: ✅ CloudCtl skill is healthy
```

**Release Status:** ✅ PRODUCTION READY
- All 654 automated tests passing
- Two-tier testing complete (automated + user-simulated)
- All core commands operational
- Approval gates functional
- Multi-cloud support ready (AWS, Azure, GCP)

### 3. Handle Feature Requests

**Pattern:**
1. Understand requirement (read code to see if it exists)
2. Check if it's already in code but undocumented
3. If implementing: update tests first, then code
4. Run: `poetry run pytest tests/ -v` (must pass 431+ tests)
5. Update: [README.md](README.md) and/or docs/ with examples

**Example Features Already Built:**
- Multi-org switching: `cloudctl switch <org>`
- Multi-cloud support: AWS, Azure, GCP providers
- Token caching: `~/.aws/sso/cache/` (AWS standard)
- Shell integration: Bash, Zsh, Fish, PowerShell
- Context persistence: `~/.cloudctl/context.json`
- Audit logging: Break-glass logging for sensitive roles
- Plugin system: Okta MFA support

### 4. Handle Bug Reports

**Pattern:**
1. Reproduce: use `poetry run cloudctl <cmd>` to test
2. Isolate: check `poetry run pytest tests/ -v` for related tests
3. Locate: grep for code patterns in `src/cloudctl/`
4. Fix: minimal change to src, then add/update test
5. Verify: all 654 tests must pass (v5.1.0+)
6. Run user-simulated testing to validate behavior

**Common Issues & Fixes:**

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Not installed** | `command not found: cloudctl` | `pip install cloudctl-skill --extra-index-url ...` |
| **Not initialized** | `Error: orgs.yaml not found` | `cloudctl init` to create config |
| **Wrong context** | Commands run against wrong AWS account | `cloudctl env` to verify, then `cloudctl switch <org>` |
| **Expired token** | `InvalidClientTokenId` or `UnrecognizedClientException` | `cloudctl cache-clear` then `cloudctl login <org>` |
| **Shell wrapper missing** | Credentials not exported to shell | `cloudctl init --shell-only` to reinstall wrapper |
| **System misconfigured** | Unclear what's wrong | `cloudctl doctor` for diagnostic output |
| **Approval timeout** | Switch hangs waiting for approval | Check ServiceNow (production) or mock (test) |
| **MFA prompt hangs** | MFA stuck or not responding | Ctrl+C to cancel, check device for MFA push |

### 5. Emergency Troubleshooting

**If cloudctl is completely broken:**

```bash
# Step 1: Verify installation
python3 -c "import cloudctl; print(cloudctl.__version__)"
# Expected: 5.1.0

# Step 2: Clear all caches and state
cloudctl cache-clear
rm -f ~/.cloudctl/context.json
rm -f ~/.aws/sso/cache/*

# Step 3: Re-initialize
cloudctl init

# Step 4: Test basic command
cloudctl doctor

# Step 5: Re-authenticate
cloudctl login bt-avm
```

**If shell wrapper is broken:**

```bash
# Reinstall wrapper without wizard
cloudctl init --shell-only

# Verify it's in ~/.zshrc or ~/.bashrc
grep -A5 "cloudctl" ~/.zshrc

# Restart shell
exec $SHELL
```

**If credentials won't export:**

```bash
# Check if CLOUDCTL_WRAPPER_ACTIVE is set (should be 1)
echo $CLOUDCTL_WRAPPER_ACTIVE

# Force reactivate
export CLOUDCTL_WRAPPER_ACTIVE=1
cloudctl switch bt-avm  # Try again

# If still broken, check shell type
echo $SHELL  # Should be bash, zsh, fish, or powershell
```

### 6. Multi-Cloud Organizations

CloudCtl supports three cloud providers with dedicated CLI commands:

**AWS Organizations** (4 configured):
- `bt-avm` — BeyondTrust Commercial (us-east-1)
- `bt-dev` — Development AWS (us-east-1)  
- `fdr-gvc` — FedRAMP GovCloud (us-gov-east-1)
- `fdr-cmc` — FedRAMP Commercial (us-east-1)

**Commands:**
```bash
cloudctl switch bt-avm          # Interactive picker
cloudctl switch bt-avm --account 235494790978 --role admin --region us-east-1 --non-interactive
cloudctl list-roles bt-avm      # List available roles
cloudctl list-roles bt-avm --assigned  # List roles you can assume
```

**GCP Organization** (1 configured):
- `gcp-prod` — Production GCP (Project: beyondtrust-prod)

**Commands:**
```bash
cloudctl switch gcp-prod        # Interactive picker
cloudctl env                    # Show current context
```

**Azure Organization** (1 configured):
- `avm-prod` — Azure Production (Tenant: 00000000-0000-0000-0000-000000000000)

**Commands:**
```bash
cloudctl switch avm-prod        # Interactive picker
cloudctl env                    # Show current context
```

**Configuration Location:**
```bash
~/.config/cloudctl/orgs.yaml   # Edit to add/remove orgs
```

### 7. Handle Bug Reports

### 5. Development Workflow

**Setup:**
```bash
cd /Users/choad/repos/cloudctl
poetry install              # Install dependencies
poetry run pytest tests/     # Run all 431 tests (should pass)
poetry run cloudctl --help  # Verify CLI works
```

**Making Changes:**
```bash
# Edit src/cloudctl/<module>.py
# Add/update test in tests/test_<module>.py
poetry run pytest tests/test_<module>.py -v  # Test your change
poetry run pytest tests/ -v                   # Verify all tests pass
poetry run cloudctl --help                    # Manual smoke test
```

**Code Style:**
- Use Black for formatting (auto via pre-commit)
- Use Ruff for linting
- Run: `make lint` to check style

---

## 🔐 SECURITY NOTES FOR CLAUDE DEVELOPERS

### Credential Handling Rules (CRITICAL)

cloudctl is a **credential management tool**. Follow these rules absolutely:

1. **NEVER log credentials to stdout/stderr**
   - AWS Access Keys (AKIA*, ASIA*)
   - Secret Access Keys
   - Session Tokens
   - GCP service account keys
   - Azure client secrets

2. **ALWAYS mask credentials in output**
   ```python
   # ❌ WRONG
   print(f"Access Key: {access_key}")
   
   # ✅ RIGHT
   print(f"Access Key: {access_key[:4]}...{access_key[-4:]}")
   ```

3. **NEVER hardcode credentials in code**
   - No example keys in docstrings
   - No test credentials in fixtures (use mocks)
   - No credentials in config examples

4. **ALWAYS use environment variables for credentials**
   ```bash
   # ✅ RIGHT
   AWS_ACCESS_KEY_ID=${secret}
   
   # ❌ WRONG
   aws_access_key_id = "AKIA1234567890ABCDEF"
   ```

5. **ALWAYS validate secrets before operations**
   ```python
   # Check credential before using
   if not has_valid_credentials():
       sys.exit("No valid credentials found")
   ```

6. **Memory-only credential handling**
   - Load credentials into memory
   - Use immediately
   - Clear from memory when done
   - Never write to disk (except encrypted cache)

### Testing Credentials (For User-Simulated Testing)

When testing cloudctl commands:

```bash
# ✅ Safe: Use actual cloudctl contexts
cloudctl switch bt-avm --account 235494790978 --role admin

# ✅ Safe: Commands use real AWS SSO
cloudctl login bt-avm

# ❌ UNSAFE: Never pass credentials as arguments
cloudctl switch --access-key AKIA... --secret-key ...

# ❌ UNSAFE: Never export credentials to test script
export AWS_ACCESS_KEY_ID=AKIA...
```

### Audit Logging (Already Implemented)

cloudctl logs sensitive operations:
- Role switches to sensitive roles (admin, security, devops)
- Approval requests and approvals
- Failed authentication attempts
- Credential refresh operations

Location: `~/.cloudctl/audit.jsonl` (append-only, immutable)

Never modify or delete audit logs.

---

### 8. Understand the Release Process

**Version Scheme:**
- Major (X.0.0): Breaking changes (e.g., v3.x → v4.0.0 rename)
- Minor (3.X.0): New features (backward compatible)
- Patch (3.1.X): Bug fixes

**Current Version:** 5.1.0 (latest - Phase 1-Immediate complete)

**Release Process:**
1. Ensure all 654+ tests pass: `poetry run pytest tests/ -v`
2. Run user-simulated testing — Gold standard (see testing section)
3. Update version in `pyproject.toml` and `src/cloudctl/__init__.py`
4. Commit changes with release notes
5. Create git tag: `git tag v5.1.0`
6. Push to GitHub (triggers CI/CD publish to python-packages)
7. Verify publication: https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/

**Release Artifacts:**
- PyPI wheel: `cloudctl_skill-5.1.0-py3-none-any.whl`
- Source tarball: `cloudctl_skill-5.1.0.tar.gz`
- GitHub Release: https://github.com/BT-IT-Infrastructure-CloudOps/infra-cloudops-ai-claude-skill-cloudctl/releases/tag/v5.1.0

---

## 📚 Quick Reference for Claude Developers

### Key File Locations

```
/Users/choad/repos/cloudctl-repo/
├── src/cloudctl/                # Main source code
│   ├── cli.py                   # Entry point and command router
│   ├── core.py                  # Core business logic
│   ├── commands/                # Individual command implementations
│   ├── providers/               # AWS, Azure, GCP integrations
│   ├── errors.py                # Error types and handling
│   └── encryption.py            # Config encryption (AES-256)
├── tests/                       # Test suite (654 tests)
├── pyproject.toml              # Package config (version 5.1.0)
├── CLAUDE.md                    # This file
├── README.md                    # User guide
├── ROADMAP.md                   # Feature roadmap
└── ~/.config/cloudctl/orgs.yaml # User configuration (6 orgs)
```

### Useful Commands for Development

```bash
# Testing
poetry run pytest tests/ -v              # Run all tests
poetry run pytest tests/test_cli.py -v   # Run specific test file
poetry run pytest --cov=src/cloudctl     # Show coverage
poetry run pytest -k "test_login"        # Run tests matching pattern

# Code Quality
poetry run black src/ tests/              # Format code
poetry run ruff check src/ tests/         # Lint code
make lint                                 # Run all style checks

# Running CloudCtl
poetry run cloudctl --help                # Show help
poetry run cloudctl doctor                # Run health check
poetry run cloudctl login bt-avm          # Authenticate
poetry run cloudctl switch bt-avm         # Interactive context picker

# Building
poetry build                              # Build wheel and tarball
poetry publish                            # Publish to PyPI (requires credentials)

# Documentation
poetry run cloudctl --version             # Show version
grep -r "def cmd_" src/                   # Find all commands
```

### Documentation Links

| Resource | URL | Purpose |
|----------|-----|---------|
| **User Guide** | https://beyondtrust.atlassian.net/wiki/spaces/COTA/pages/3530981386 | Complete user documentation |
| **GitHub Repo** | https://github.com/BT-IT-Infrastructure-CloudOps/infra-cloudops-ai-claude-skill-cloudctl | Source code |
| **Python Packages** | https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/simple/ | Package repository |
| **AWS SSO Setup** | https://docs.aws.amazon.com/singlesignon/latest/userguide/ | AWS Identity Center docs |

### When Stuck

**Problem:** Something not working and you don't know what's wrong

**Solution:**
1. Run `cloudctl doctor` — Gives 80% of the answers
2. Check `/tmp/cloudctl-v5.1.0-test-results.md` — See what was tested
3. Look at `tests/test_cli.py` — See how commands are tested
4. Check `src/cloudctl/cli.py` — See command implementation
5. Search `src/cloudctl/errors.py` — See error handling

**If Still Stuck:**
- Look at recent commits: `git log --oneline -20`
- Check git diffs: `git diff HEAD~5..HEAD`
- Run specific test: `poetry run pytest tests/test_cli.py::test_login -v`

**Release Steps:**
1. Create feature branch from main
2. Make changes + tests
3. Update version in pyproject.toml if needed
4. Create commit with clear message
5. Create git tag (e.g., `git tag v4.1.0`)
6. Push to GitHub (GitHub Actions handles publication)
7. CI/CD publishes to Artifactory/PyPI

### 7. Important Files for Claude to Know

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — Claude app management guide |
| `MIGRATION.md` | User upgrade guide for v3.x → v4.0.0 |
| `README.md` | User-facing documentation with examples |
| `pyproject.toml` | Package metadata, dependencies, version |
| `src/cloudctl/cli.py` | Entry point and command dispatcher |
| `tests/test_cli.py` | CLI behavior tests (start here for understanding) |
| `Makefile` | Build tasks (test, lint, format) |

### 8. Multi-Cloud Context

cloudctl supports three cloud providers equally:

**AWS:**
- Provider: `src/cloudctl/providers/aws.py`
- Auth: AWS SSO (OIDC tokens cached at `~/.aws/sso/cache/`)
- Partitions: Commercial (aws), GovCloud (aws-us-gov), China (aws-cn)
- Example org: `bt-avm` (BeyondTrust AVM)

**Azure:**
- Provider: `src/cloudctl/providers/azure.py`
- Auth: Azure CLI (`az login`)
- Resources: ARM subscriptions and RBAC roles
- Export: `ARM_*` and `AZURE_*` environment variables

**GCP:**
- Provider: `src/cloudctl/providers/gcp.py`
- Auth: gcloud auth (`gcloud auth login`)
- Resources: GCP projects and IAM roles
- Export: `GOOGLE_*` and `CLOUDSDK_*` environment variables

All three use the same CLI and context management system.

### 9. Security Notes

cloudctl implements zero-trust credential handling:
- **No persistence**: Credentials never written to disk (ephemeral only)
- **Injection protection**: All shell exports use `shlex.quote()`
- **TTY guard**: Warns if `--eval` used outside wrapper context
- **Audit logging**: Sensitive role access logged to break-glass audit trail
- **Token caching**: Uses cloud provider standard locations (AWS SSO cache, gcloud config)

When making changes, preserve these security properties.

### 10. When to Ask the User

Ask for clarification when:
- Feature scope is ambiguous (ask user for examples)
- Breaking change might impact users (confirm with user first)
- Multiple valid approaches exist (let user choose)
- User's request conflicts with security (explain why and suggest alternative)

Don't ask for permission to:
- Run tests (always safe)
- Read documentation (always safe)
- Fix bugs (as long as tests pass)
- Update docs (as long as they're accurate)

---

## Summary

**You have everything needed to:**
- ✓ Understand user requests about cloudctl
- ✓ Investigate and fix bugs
- ✓ Implement features with proper testing
- ✓ Update documentation
- ✓ Guide users through common tasks
- ✓ Manage releases

When in doubt, check the code first. The 431 passing tests are your safety net.
