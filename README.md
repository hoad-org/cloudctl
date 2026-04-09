# awsctl v3.0.0 — Enterprise Cloud Identity & Context Manager

[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/1/badge)](https://bestpractices.coreinfrastructure.org/projects/1)
[![SLSA Aligned](https://slsa.dev/images/gh-badge-level2.svg)](https://slsa.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Zero Trust](https://img.shields.io/badge/Security-Zero%20Trust-blueviolet)](docs/SECURITY.md)
[![NIST 800-53](https://img.shields.io/badge/NIST_800--53-Compliant-blue?style=flat&logo=nist)](docs/SECURITY_APPRAISAL.md)
[![FedRAMP Supporting](https://img.shields.io/badge/FedRAMP-Ready-005288?style=flat&logo=files)](docs/SECURITY_APPRAISAL.md)
[![GovCloud Compatible](https://img.shields.io/badge/AWS_GovCloud-Compatible-232F3E?style=flat&logo=amazon-aws)](docs/USER_GUIDE.md)
[![FIPS 140-3 Compatible](https://img.shields.io/badge/FIPS_140--3-Compatible-green?style=flat&logo=openssl)](docs/SECURITY.md)

⚠️ **INTERNAL TOOL:** This repository is for internal use by **BeyondTrust Engineering only.**
Do **not** fork to public repositories or distribute binaries outside the corporate network.

---

**Secure. Governed. Zero-Trust. Auditor-Ready.**

`awsctl` is an enterprise security tool that provides controlled, auditable access to cloud accounts across **AWS, Microsoft Azure, and Google Cloud Platform** through each provider's native authentication mechanism.

It delivers:

- **Strong Guardrails:** Enforced centrally via an Immutable Registry.
- **Context Switching:** Fast, fuzzy-search selection for Accounts and Roles.
- **Ephemeral Credentials:** Credentials exist only in memory and the active shell session.
- **Shell Safety:** TTY Guards, fail-closed wrapper logic, and shell-escaped exports.
- **Audit-Ready:** “Break Glass” logging for sensitive role access.

---

## 🛠 The Identity Engine: No Reinvented Wheels

`awsctl` does **not** implement its own identity or cryptographic protocols.
It depends exclusively on **official AWS and open-source components**, ensuring compatibility, reliability, and security.

- **Token Management:** Uses AWS CLI v2’s `~/.aws/sso/cache` for OIDC token persistence.
- **Identity Resolution:** Identity is derived via the official `aws sts get-caller-identity` command.
- **Credential Acquisition:** Short-lived STS credentials are fetched via AWS CLI v2 (OIDC) and/or Python `boto3`.
- **Authentication:** The actual IdP handshake (Okta, Azure AD, etc.) is managed by AWS SSO’s OIDC flow.
- **Azure Credentials:** Short-lived access tokens are fetched via `az account get-access-token`, emitted as `ARM_*` / `AZURE_*` env vars.
- **GCP Credentials:** Access tokens are fetched via `gcloud auth print-access-token`, emitted as `GOOGLE_*` / `CLOUDSDK_*` env vars.

This ensures awsctl remains lightweight, secure, and natively compatible with AWS infrastructure.

---

## ⚡️ Key Features

### 🔐 Zero Trust Credential Architecture

- **Ephemeral Session Environment:** Exports STS credentials only to your current shell session using the Context Bridge pattern.
- **Diskless Credentials:** No credentials are written to disk at any point.
- **Isolated Contexts:** Each terminal or tab maintains an independent AWS environment.
- **TTY Guard:** Refuses to print credentials when executed outside its validated wrapper context.
- **Injection Protection:** All exported variables are sanitized via `shlex.quote()` to neutralize command injection vectors.

---

### 🛡️ Registry-Backed Governance

- **Hydration Model:** awsctl loads configuration from a centrally managed governance registry.
- **Hybrid Integrity:**
  - *Pilot Mode (Current):* Relies on administrative control of distributed registries.
  - *Tier 3 (Future):* Adopts signed Minisign manifest validation anchored to an Ed25519 public key.
- **Region Locking:** Prevents interactive use in non-approved AWS regions.
- **Bypass Notes:** If users are authorized to use `aws` CLI directly, client enforcement can be bypassed—SCPs and Organization policies must remain active.
- **Plugin Sandboxing:** Enforces namespace boundaries (`awsctl.plugins.*`) to prevent untrusted execution through plugin tampering.

---

## 🏗 Architecture: The Split-Plane Model

The **Split-Plane Architecture** addresses the core limitation of CLI tools:
child processes cannot mutate their parent shell’s environment.

- **Shell Wrapper (Data Plane):** Injected into `.zshrc` or `.bashrc`; intercepts commands for real-time context bridging.
- **Bash Shim (Control Plane):** POSIX binary (`/usr/local/bin/awsctl`) that routes commands and enforces safety constraints.
- **Python Core:** Executes AWS SDK/CLI logic and emits environment variables.
- **The Bridge:** For mutating commands (e.g., `switch`), the core emits `export` statements that the wrapper applies via `eval`.

This design guarantees security, portability, and full session-level context control.

---

## 🛡️ Security Boundaries & Governance

### 🎯 Trust Boundaries

awsctl defines and enforces clear operational trust assumptions:

| Boundary | Trust Level | Description |
|-----------|-------------|-------------|
| **Workstation** | Untrusted | The local endpoint is considered semi-trusted; malicious software could potentially access environment variables. |
| **Shell Environment** | Limited-Trust | Considered the boundary for session mutability; secure only against unauthorized shell commands, not local memory scraping. |
| **Registry** | Trusted Anchor | Configuration integrity and signed manifests originate here. |
| **Identity Provider (IdP)** | Trusted | Delegated trust boundary connecting awsctl to the enterprise authentication system (AWS SSO / SAML). |

---

### 🚫 Non-Goals

awsctl **does not** replace or duplicate other enterprise systems:

- **Privileged Access Management (PAM):** It does not manage IdP passwords or MFA policies.
- **Service Control Policies (SCPs):** Enforcement remains server-side; awsctl acts as a complementary client guardrail.
- **IAM Policy Design:** awsctl does not define or modify permissions; it enforces existing governance.
- **Runtime Guardrails:** Once valid credentials are assumed, awsctl does not prevent intended AWS operations.

---

## 📥 Installation

### Prerequisites

- Python **3.9+**
- AWS CLI v2 installed and configured for SSO.

---

### Option A: System-Wide Install (sudo required)

```
git clone [https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git](https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git)
cd awsctl
make deploy-system
```

Installs both core libraries and the `/usr/local/bin/awsctl` Bash shim.

---

### Option B: User-Space Install (no sudo required)

```
make deploy-system BIN_DIR=$HOME/.local/bin
```

Ensure `$HOME/.local/bin` is in your `PATH` before executing:
```
export PATH="$HOME/.local/bin:$PATH"
```

---

## ❓ FAQ (Frequently Asked Questions)

### 🔑 Token Length & Expiry
**Q:** How long do my credentials last?
**A:** By default, awsctl requests 12-hour session tokens, aligned with AWS Identity Center defaults.

---

### 🛡️ Preventing Authentication Exposure
**In-Memory Enforcement:** Credentials are never persisted to disk.
**TTY Guard:** Prevents accidental output of secret material.
**Shell Escaping:** All variable exports are sanitized with `shlex.quote()` to prevent injection payloads.
**Scope:** Credentials are inherited only by child processes spawned from the active shell.

---

### 📝 Log Governance
**“Break Glass” Logs:**
- Saved at `~/.awsctl/audit.log`
- Format: `ISO8601 | ORGANIZATION | ROLE | REASON`
- Input Sanitation: Prevents injection or control characters in logs.
**Recommendation:** Forward logs to a centralized SIEM for retention and compliance integrity.

---

### 📁 Protecting Token Folders
awsctl reuses AWS CLI’s official SSO cache.
`awsctl doctor` validates that cache permissions are set to `0600` to prevent unauthorized local access.

---

## 💻 Supported Environments

| Operating System | Shell | Status |
|------------------|--------|--------|
| macOS | Zsh, Bash | ✅ Fully Supported |
| macOS | Fish | ✅ Fully Supported |
| Linux | Bash, Zsh | ✅ Fully Supported |
| Linux | Fish | ✅ Fully Supported |
| Windows (Native) | PowerShell (pwsh / Windows PS) | ✅ Fully Supported |
| Windows (WSL2) | Bash, Zsh | ✅ Fully Supported |

---

## 🔐 Security & Compliance

awsctl aligns with security frameworks used across high-assurance enterprise and government environments.

| Framework | Control | awsctl Implementation |
|-----------|----------|-----------------------|
| **NIST 800-53** | **AC-3** | Region and Role allow-list enforcement in the client registry. |
| **NIST 800-53** | **IA-5** | No static credentials on disk—ephemeral session tokens only. |
| **NIST 800-53** | **AU-2** | “Break Glass” logging with time-stamped justification records. |
| **SLSA** | **Aligned Practices** | Tag-driven CI/CD, immutable artifacts, signed builds, and provenance tracking. |

---

## 📜 Changelog (v3.0.0)

- **FEATURE:** Cross-cloud provider support — Azure and GCP alongside AWS via a unified `CloudProvider` interface.
- **FEATURE:** Native PowerShell shell wrapper (`awsctl` PS function) — full Split-Plane support on Windows without WSL.
- **FEATURE:** Fish shell wrapper — `~/.config/fish/functions/awsctl.fish` auto-installed via `awsctl init`.
- **FEATURE:** `awsctl init` wizard detects the running shell (bash/zsh/PowerShell/fish) and installs the appropriate wrapper.
- **FEATURE:** `provider` field in org config selects the cloud backend (`aws` | `azure` | `gcp`; defaults to `aws` for backward compatibility).
- **FIX:** CLI dispatcher resolves handlers at call time so `monkeypatch` works correctly in tests.
- **CHORE:** 47 new provider unit tests; 204 passing overall.

---

## 📜 Changelog (v2.8.2)

- **REFACTORED:** Implemented Split-Plane Architecture to eliminate bootstrap deadlocks.
- **FEATURE:** Added Idempotent Setup for safe repeated shell injections.
- **FIX:** Enhanced TTY Guard compatibility with multiplexers (`tmux`, `screen`).
- **DOCS:** Fully standardized on `make deploy-system` for installation consistency.

---

## 📄 License

**MIT License.** See `LICENSE` for complete details.

---

### ✅ Validation Summary (v2.8.2)

- ✅ Unit test coverage: **>78%**
- ✅ Cross-platform smoke testing
- ✅ Enterprise Acceptance Suite (UAT) passed
- ✅ Static analysis: Bandit, `pip-audit`, MyPy (strict mode) compliant
- ✅ CI/CD integrity: SLSA-aligned artifact release and cryptographic signature verification
```
