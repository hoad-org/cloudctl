# awsctl Product Roadmap

This document outlines the strategic direction for `awsctl`.

**Current Version:** v2.0.0  
**Status:** Stable / Enterprise Ready

---

## Phase 1: Core Foundation and Security (Completed)

**Status:** ✅ Live

### 🛡️ Security Architecture

- [x] **Zero Trust Storage:** Credentials exist only in memory; never written to disk.
- [x] **Registry-Backed Hydration:** Configuration is centrally enforced via `registry.py`.
- [x] **Region Guardrails:** Strict enforcement of `allowed_regions`.
- [x] **Filesystem Hardening:** Enforced `0o700` permissions on `~/.awsctl`.
- [x] **Plugin System:** Mandatory pre-login hooks (for example, Okta/VPN checks).

### 🔧 Core Features

- [x] **Interactive Wizard:** `awsctl setup` TUI for configuration.
- [x] **Trojan Horse Integration:** Seamless shell exports via wrapper function.
- [x] **Smart Switching:** Toggle context using `awsctl switch -`.
- [x] **Implicit Exec:** Run commands in active context (`awsctl exec -- cmd`).
- [x] **Browser Login:** Full integration with AWS CLI v2 SSO flow.

---

## Phase 2: Usability and Automation

**Status:** 🚧 In Progress

### 2.1 Native PowerShell Support

- [ ] **Output Format:** Add `--format=powershell` option to CLI.
- [ ] **Helper Function:** Ship `awsctl-use.ps1` for Windows users (native support without WSL).

### 2.2 Advanced Interactive UI

- [ ] **Visual Preview:** Show Region and Role metadata in the fuzzy selector side pane.
- [ ] **Role Highlighting:** Visually distinguish `preferred_roles` (for example, bold/green) in the TUI.
- [ ] **Keyboard Shortcuts:** Add vim-style bindings to the fuzzy matcher.

### 2.3 Automation Profiles

- [ ] **Profile Aliases:** Allow shortcuts in `orgs.yaml` (for example, `dev: {role: ViewOnly}`).
- [ ] **Quick Switch:** Support `awsctl switch @dev` syntax.

---

## Phase 3: Security Hardening (Next Gen)

**Status:** 📅 Planned

### 3.1 Advanced Policy Enforcement

- [ ] **Min Version Check:** Add `min_client_version` to Registry to force client upgrades.
- [ ] **Role Deny-Lists:** Registry support for `denied_roles` (block specific roles per account).
- [ ] **Context Awareness:** Add `pre_use(context)` hook to validate specific role requests dynamically.

### 3.2 Session Intelligence

- [ ] **TTL Monitor:** Daemon or hook to warn users *before* their SSO token expires.
- [ ] **Session Audit:** Option to log successful session creations to a local, encrypted audit file.

### 3.3 Device Posture Framework

- [ ] **Agent Check:** Native support for checking EDR agent status (CrowdStrike, SentinelOne) via plugins.

---

## Phase 4: Platform and Operations

**Status:** 🔮 Future

### 4.1 Remote Registry Sync

- [ ] **Remote Source:** Consume Registry from S3 signed URL or Git-hosted JSON (removing the need to rebuild binary for config changes).
- [ ] **Integrity:** GPG/Sigstore signature verification for remote definitions.

### 4.2 Observability

- [ ] **Drift Detection:** `awsctl doctor` checks if local `orgs.yaml` contains deprecated orgs.
- [ ] **Telemetry Hooks:** Optional anonymized usage signals for platform teams.

---

## Versioning Strategy

`awsctl` follows **Semantic Versioning**:

- **Major (2.x):** Stable API, Registry schema, and CLI arguments.
- **Minor (2.1.x):** New features (for example, new plugins, new UI modes) that are backwards compatible.
- **Patch (2.0.1):** Bug fixes, role ordering tweaks, text updates.
