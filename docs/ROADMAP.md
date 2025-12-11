# file: docs/ROADMAP.md
# Product Roadmap

**Current Version:** v2.8.1
**Status:** Secure / Enterprise Ready (AWS Only)
**Strategic Direction:** Evolution to Multi-Cloud Identity Broker

---

## Phase 1: Security & Hardening (Completed v2.2)

**Status:** ✅ Live

- [x] **Secure Shell Integration:** Fail-closed wrapper logic to prevent token leakage.
- [x] **Namespace Allowlisting:** Strict plugin namespacing to block Arbitrary Code Execution (ACE).
- [x] **TTY Guards:** Auto-detection of interactive terminals to prevent credential dumping.
- [x] **Environment Sanitization:** Active stripping of ambient `AWS_` variables before execution.
- [x] **SSRF Protection:** Strict HTTPS enforcement in network plugins.

---

## Phase 2: Enterprise Governance (Completed v2.8.1)

**Status:** ✅ Live

- [x] **Smart History:** "Recent Contexts" appear at the top of the selector with a `🕒` icon.
- [x] **Remote Registry (GitOps):** Load `registry.json` from a signed S3/HTTPS URL to update guardrails without rebuilding the binary.
- [x] **Pinned Trust Anchor:** Hardcoded Public Key enforcement for Remote Registry (Trust Downgrade prevention).
- [x] **Break Glass Audit:** Intercept sensitive role assumptions (e.g., `AdministratorAccess`) and require a justification ticket/reason.
- [x] **Quick Switch Aliases:** Support `@alias` syntax (e.g., `awsctl switch @prod-db`).
- [x] **Min Version Enforcement:** Registry-driven policy to force client upgrades (block login if version < X).

---

## Phase 3: The Multi-Cloud Refactor (Architecture)

**Status:** 🚧 Planned

The goal is to decouple the core "Context Bridge" shell integration from AWS-specific logic, enabling a pluggable provider model.

### 3.1 Core Abstraction (The Adapter Pattern)
- [ ] **Abstract Base Class:** Create `AuthProvider` interface defining `login()`, `get_credentials()`, and `list_contexts()`.
- [ ] **Config Schema V2:** Update `orgs.yaml` and Registry to support a `provider: aws|gcp|azure` field.
- [ ] **AWS Adapter:** Move existing `boto3`/SSO logic into `src/awsctl/providers/aws.py`.

### 3.2 Shell Integration V2
- [ ] **Generic Exports:** Update shell wrapper to handle provider-agnostic export maps (e.g., mapping generic `ACCESS_TOKEN` to `AWS_SESSION_TOKEN` or `CLOUDSDK_AUTH_ACCESS_TOKEN`).

---

## Phase 4: Google Cloud (GCP) Support

**Status:** 📅 Planned

Google Cloud shares the "Environment Variable" authentication model with AWS, making it the ideal first expansion candidate.

- [ ] **GCP Adapter:** Implement `GcpProvider` using `google-auth` library.
- [ ] **OIDC Integration:** Support browser-based OIDC login flows for GCP.
- [ ] **Token Export:** Map session tokens to `CLOUDSDK_AUTH_ACCESS_TOKEN`.
- [ ] **Guardrails:** Implement `allowed_projects` and `allowed_zones` in the Registry.

---

## Phase 5: Advanced Observability & Automation

**Status:** 🔮 Future

### 5.1 Audit Webhooks
- [ ] **Slack/Teams Integration:** Send "Break Glass" justification events directly to a webhook URL defined in the Registry.
- [ ] **Splunk/Datadog Forwarder:** Optional plugin to emit structured JSON audit logs to a local agent.

### 5.2 "Headless" Session Management
- [ ] **Session Refresh:** `awsctl refresh --background` to attempt token renewal without browser interaction (if refresh token is valid).
- [ ] **Docker Credential Helper:** Expose a local socket or credential helper binary compatible with `docker-credential-ecr-login`.

### 5.3 Policy as Code (OPA)
- [ ] **OPA Integration:** Allow complex guardrails (e.g., "Allow `Admin` only on weekdays between 9-5") by evaluating a Rego policy file downloaded alongside the Registry.

---

## 🏁 Milestone: Rebrand to `ssoctl`

**Status:** Planned (Post-GCP)

Upon achieving multi-cloud parity (AWS + GCP), the tool will be renamed to reflect its provider-agnostic nature.

- [ ] **Rename Binary:** Migrate `awsctl` -> `ssoctl`.
- [ ] **Unified Config:** Migrate `~/.awsctl` -> `~/.ssoctl`.
- [ ] **Legacy Alias:** Provide `awsctl` alias for backward compatibility.
