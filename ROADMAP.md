# CloudCtl v5.x Roadmap

**Current Version:** v5.1.0 (Phase 1-Immediate Complete)  
**Last Updated:** 2026-05-27  
**Status:** 🚀 PRODUCTION READY — Released to python-packages

---

## 🎯 Mission

CloudCtl is your **ephemeral credential manager for multi-cloud with safety gates**.

- **Authenticate** to AWS, Azure, GCP via single sign-on
- **Manage** credentials with lifecycle control (request → use → expire → cleanup)
- **Enforce** safety gates (approval, MFA, ownership, rate limiting)
- **Audit** all operations (immutable, no-secrets-logged)
- **Support** multiple organizations and clouds

---

## 📊 Current State: v5.1.0 ✅ PRODUCTION READY

### ✅ Phase 1-Immediate COMPLETE (v5.1.0 — May 27, 2026)

| Feature | Status | Notes |
|---------|--------|-------|
| **A. Multi-Cloud Authentication** | ✅ COMPLETE | AWS SSO, Azure Entra, GCP OIDC; token caching |
| **B. Credential Management** | ✅ COMPLETE | Account/role/region switching; env var export |
| **C. Session Management** | ✅ COMPLETE | Multiple sessions; timeout; cleanup; expiry tracking |
| **D. Interactive & Non-Interactive** | ✅ COMPLETE | TTY mode with InquirerPy; automation mode (no prompts) |
| **E. Validation (Safety)** | ✅ COMPLETE | Role validation with fuzzy matching; account/region checks |
| **F. Audit & Compliance** | ✅ COMPLETE | Immutable JSONL logging; no secrets; operation tracking |
| **G. Configuration** | ✅ COMPLETE | orgs.yaml multi-cloud support; provider selection |

**Coverage:** 7/7 core features ✅

---

## 🚀 Roadmap: v5.1 → v5.3

### **v5.1.0 — Critical Foundation** ✅ COMPLETE (2 weeks)
**Goal:** Production-ready with minimum viable governance  
**Status:** 🚀 RELEASED May 27, 2026

**Features (All Implemented):**
- [x] **M. Credential Validation** — Test credentials work with live API call (sts:GetCallerIdentity)
  - [x] Auto-detect expired/invalid tokens
  - [x] Return credential health status
  - [x] Fail if credentials invalid
  - ✅ Effort: 1-2h

- [x] **N. Schema Validation** — JSON Schema validation for orgs.yaml
  - [x] Validate on file load
  - [x] Clear error messages for violations
  - [x] Schema versioning for migrations
  - ✅ Effort: 2-3h

- [x] **H. Approval Gates (Mock Provider)** — Governance for sensitive roles
  - [x] Approval request workflow
  - [x] Mock provider (auto-approve for Phase 2)
  - [x] Approval timeout (default 300s)
  - [x] Audit logging (who approved, when)
  - ✅ Effort: 4-5h

- [x] **I. MFA Enforcement (TOTP)** — Multi-factor authentication
  - [x] TOTP (Time-based One-Time Password) support
  - [x] MFA prompt in interactive mode
  - [x] MFA timeout (2 minutes)
  - [x] Per-role MFA requirements (orgs.yaml config)
  - ✅ Effort: 3-4h

- [x] **Error Handling** — Production-grade error messages
  - [x] 9 error types with recovery suggestions
  - [x] Clear context in error output
  - [x] Audit trail logging

- [x] **Config Encryption** — Fernet AES-256 encryption
  - [x] Encrypt sensitive fields (SSO URLs, webhook secrets)
  - [x] Transparent encrypt/decrypt
  - [x] Key management

- [x] **List Roles Command** — Role discovery
  - [x] `cloudctl list-roles <org>`
  - [x] `cloudctl list-roles --assigned`
  - [x] Fuzzy matching support

**Testing & Quality:**
- ✅ 654 unit tests passing (90%+ coverage)
- ✅ 2-tier testing: automated pytest + user-simulated bash commands
- ✅ Integration tests validated
- ✅ No regressions

**Documentation:**
- ✅ Confluence COTA space complete
- ✅ GitHub README updated
- ✅ CLAUDE.md developer guide created
- ✅ Troubleshooting guide included

**Release:** v5.1.0 (production-ready, enterprise-grade governance)
**Availability:** Python-packages repository (pip install cloudctl-skill)
**Installation:** `pip install cloudctl-skill --extra-index-url https://BT-IT-Infrastructure-CloudOps.github.io/python-packages/simple/`

---

### **v5.2.0 — Full Governance** (3 weeks)
**Goal:** Enterprise-grade governance + compliance  
**Effort:** 18-27 hours

**Features:**
- [ ] **J. Ownership Gates** — User authorization per organization
  - [ ] Owner field in org configuration
  - [ ] Verify user is org owner before switching
  - [ ] Support multiple owners
  - [ ] Default deny if no owner configured
  - **Effort:** 2-3h

- [ ] **K. Rate Limiting** — Prevent abuse and runaway operations
  - [ ] Logins per hour (default 5)
  - [ ] Switches per minute (default 10)
  - [ ] Failed attempts per hour (default 5)
  - [ ] Per-user/session tracking
  - [ ] Clear error messages + reset instructions
  - **Effort:** 2-3h

- [ ] **L. Scope Whitelists** — Account/role restrictions
  - [ ] Allowed accounts list (optional, per user)
  - [ ] Allowed roles list (optional, per user)
  - [ ] Hard enforcement (whitelist > approval)
  - [ ] Clear error showing allowed values
  - **Effort:** 2-3h

- [ ] **O. Config Encryption** — Protect sensitive orgs.yaml fields
  - [ ] Encrypt sso_start_url, webhook URLs, custom secrets
  - [ ] OS keychain integration (if available)
  - [ ] Transparent encryption/decryption
  - [ ] Key rotation procedures
  - **Effort:** 2-3h

- [ ] **H.2 Approval Provider: ServiceNow** — Production approval workflow
  - [ ] ServiceNow integration (create change requests)
  - [ ] Approval tracking via ServiceNow
  - [ ] Webhook callbacks for approvals
  - [ ] Timeout handling
  - **Effort:** 3-4h

- [ ] **I.2-3 Advanced MFA** — SMS + WebAuthn
  - [ ] SMS code delivery support
  - [ ] WebAuthn (hardware keys, biometrics)
  - [ ] Device selection UI
  - [ ] Fallback to TOTP
  - **Effort:** 3-4h

**Testing & Documentation:** 3-4h

**Deliverables:**
- ✅ Ownership gates enforced
- ✅ Rate limiting active + tracked
- ✅ Scope whitelists blocking invalid requests
- ✅ Sensitive config encrypted at rest
- ✅ ServiceNow approval integration
- ✅ Advanced MFA (SMS, WebAuthn, TOTP)

**Release:** v5.2.0 (enterprise-grade governance)

---

### **v5.3.0 — Enterprise Polish** (2 weeks)
**Goal:** Enterprise documentation + Spark MCP integration  
**Effort:** 13-18 hours

**Features:**
- [ ] **P. Error Handling** — Better error messages + recovery
  - [ ] Clear error messages for all failure modes
  - [ ] Suggestions for common mistakes (like role typos)
  - [ ] Recovery steps in error output
  - [ ] Consistent exit codes (0=success, 1=failure)
  - **Effort:** 2-3h

- [ ] **Q. Official Documentation** — Complete documentation
  - [ ] SKILL.md with execution model (for Claude Code)
  - [ ] Confluence pages:
    - [ ] Overview & features
    - [ ] Configuration guide (orgs.yaml)
    - [ ] Safety features (gates, MFA, rate limits)
    - [ ] API reference
    - [ ] Troubleshooting guide
  - [ ] orgs.yaml examples (AWS, Azure, GCP, multi-account)
  - [ ] CLI help text (--help, -h)
  - **Effort:** 4-5h

- [ ] **R. Spark MCP Integration** — agentic cloud login/switch via the Spark MCP
  - [ ] Spark invokes `cloudctl login`/`switch`/`exec` over its CloudCtlRunner seam
  - [ ] Pre-flight checks (org/account/role/region, approval, rate limits)
  - [ ] Browser-approve login surfaced through the agent flow
  - [ ] Error propagation back to the MCP caller
  - **Effort:** 3-4h

- [ ] **S. Version Management** — Handle schema evolution
  - [ ] Version field in orgs.yaml schema
  - [ ] Migration guide for config changes
  - [ ] Deprecation path for old fields
  - [ ] Upgrade testing procedures
  - [ ] Breaking change policy
  - **Effort:** 2-3h

**Testing & Integration:** 2-3h

**Deliverables:**
- ✅ Clear error messages with recovery steps
- ✅ SKILL.md with execution model
- ✅ Official Confluence documentation
- ✅ Agentic (Spark MCP) integration ready
- ✅ Version compatibility documented
- ✅ Enterprise-ready release

**Release:** v5.3.0 (enterprise-ready, fully documented)

---

## 📈 Separate Utilities (Keep CloudCtl Lean)

CloudCtl stays focused. These features live in separate repos:

| Utility | Purpose | Status | Link |
|---------|---------|--------|------|
| **github-secrets** | Write credentials to GitHub repo/org secrets | 🚧 In Progress | https://github.com/BT-IT-Infrastructure-CloudOps/github-secrets |
| **cloudperms** | Check if role can perform action | 🚧 In Progress | https://github.com/BT-IT-Infrastructure-CloudOps/cloudperms |
| **cloudhealth** | Monitor organization/cloud health | 📋 Planned | TBD |
| **cloudquota** | Check AWS/Azure/GCP quotas and capacity | 📋 Planned | TBD |
| **cloudcost** | Estimate operation costs | 📋 Planned | TBD |
| **cloudorch** | Orchestrate multi-account operations | 📋 Planned | TBD |
| **cloudaudit** | Generate compliance reports | 📋 Planned | TBD |

---

## 🎯 Success Criteria

### v5.0.x (Current) ✅
- [x] Multi-cloud authentication (AWS, Azure, GCP)
- [x] Interactive + non-interactive modes
- [x] Role validation with fuzzy matching
- [x] Immutable audit logging
- [x] 581+ tests passing

### v5.1.0 ✅ COMPLETE (Production-Ready)
- [x] Credentials tested before return
- [x] orgs.yaml schema validated
- [x] Approval gates functional (mock provider)
- [x] MFA enforcement (TOTP)
- [x] Error handling with recovery suggestions
- [x] Config encryption (AES-256)
- [x] List roles command
- [x] Agentic-usage foundation (exec/switch for automation)
- [x] All 654 tests passing (90%+ coverage)
- [x] Comprehensive documentation
- [x] Released to python-packages May 27, 2026

### v5.2.0
- [ ] Ownership gates enforced
- [ ] Rate limiting active
- [ ] Scope whitelists blocking
- [ ] Config encryption working
- [ ] ServiceNow approval provider
- [ ] Advanced MFA (SMS, WebAuthn)

### v5.3.0
- [ ] Error handling complete
- [ ] SKILL.md with execution model
- [ ] Confluence documentation complete
- [ ] Spark MCP integration ready
- [ ] Version management implemented

---

## 📅 Timeline

```
Week 1-2:  v5.1.0 (Critical Foundation)
           Credential validation, schema validation, approval gates (mock), MFA (TOTP)
           Status: 🚧 In Progress

Week 3-5:  v5.2.0 (Full Governance)
           Ownership gates, rate limiting, scope whitelists, encryption, advanced MFA
           Status: 📋 Planned

Week 6-7:  v5.3.0 (Enterprise Polish)
           Error handling, documentation, Spark MCP integration, version management
           Status: 📋 Planned

Week 8+:   v6.0.0 (Future)
           Breaking changes, new cloud providers, major refactoring
           Status: 🔮 Future
```

---

## 🚀 Getting Started (Developers)

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Check code quality
ruff check .
black --check .
```

### Making Changes
1. Create feature branch: `git checkout -b feat/feature-name`
2. Implement feature with tests
3. Ensure tests pass: `pytest tests/ -v`
4. Submit PR for review

### Release Process
1. Update version in `src/cloudctl/__init__.py`
2. Update `ROADMAP.md` with completion status
3. Create GitHub release with changelog
4. Publish to python-packages repo
5. Announce in team channels

---

## 📞 Questions?

- **Documentation:** See [docs/README.md](docs/README.md)
- **Issues:** Report on GitHub: https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-cloudctl/issues
- **Slack:** #cloud-ops channel

---

## 📝 Related Documents

- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) — Role validation feature details
- [docs/ROLE_VALIDATION_FEATURE.md](docs/ROLE_VALIDATION_FEATURE.md) — Complete API reference
- [INTEGRATION_TEST_REPORT.md](INTEGRATION_TEST_REPORT.md) — Test results

---

**Last Updated:** 2026-05-27  
**Maintainer:** BT IT CloudOps Team  
**License:** Proprietary (BeyondTrust)
