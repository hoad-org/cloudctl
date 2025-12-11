# awsctl v2.8.1 — Enterprise AWS Identity & Context Manager

[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/1/badge)](https://bestpractices.coreinfrastructure.org/projects/1)
[![SLSA Level 2](https://slsa.dev/images/gh-badge-level2.svg)](https://slsa.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Zero Trust](https://img.shields.io/badge/Security-Zero%20Trust-blueviolet)](docs/SECURITY.md)
[![NIST 800-53](https://img.shields.io/badge/NIST_800--53-Compliant-blue?style=flat&logo=nist)](docs/SECURITY_APPRAISAL.md)
[![FedRAMP](https://img.shields.io/badge/FedRAMP-Ready-005288?style=flat&logo=files)](docs/SECURITY_APPRAISAL.md)
[![GovCloud](https://img.shields.io/badge/AWS_GovCloud-Compatible-232F3E?style=flat&logo=amazon-aws)](docs/USER_GUIDE.md)
[![FIPS 140-3](https://img.shields.io/badge/FIPS_140--3-Compatible-green?style=flat&logo=openssl)](docs/SECURITY.md)


> **⚠️ INTERNAL TOOL:** This repository is for internal use by **BeyondTrust** Engineering only.
> Do not fork to public repositories. Do not distribute binaries outside the corporate network.

---

**Secure. Governed. Zero-Trust. Auditor-Ready.**

`awsctl` is an enterprise security tool that provides controlled, auditable, Zero-Trust access to AWS accounts through AWS IAM Identity Center (SSO). It delivers:

* **Strong Guardrails:** Enforced centrally via Immutable Registry.
* **Context Switching:** Fast, fuzzy-search selection for Accounts and Roles.
* **Zero Leakage:** No long-term keys on disk; credentials exist only in process memory.
* **Shell Safety:** TTY Guards and fail-closed wrapper logic.
* **Audit-Ready:** "Break Glass" logging for sensitive role access.

**Validation Status (v2.8.1):**
* ✅ Unit test coverage > 78% (Strictly Enforced)
* ✅ Comprehensive smoke tests (Cross-Platform)
* ✅ Enterprise Acceptance Suite (UAT) Passed
* ✅ Static Analysis (Bandit, pip-audit, MyPy Strict)

---

## ⚡️ Key Features

### 🔐 Zero Trust Credential Architecture
- **In-Memory Only:** Uses the **Context Bridge** shell integration pattern to export short-lived STS credentials directly to your shell environment variables.
- **Diskless:** Never writes `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to `~/.aws/credentials`.
- **Isolated:** Each terminal tab maintains its own independent AWS context.
- **TTY Guard:** Detects and blocks accidental printing of credentials to the screen.

### 🛡️ Registry-Backed Governance
- **Hydration Model:** Configuration is hydrated from a central Registry (Embedded or Signed Remote).
- **Pinned Trust:** Tier 3 Remote Registry uses a hardcoded Minisign key to prevent Trust Downgrade attacks.
- **Region Locking:** Prevents users from authenticating to non-approved regions.
- **Role Prioritization:** Enforces "Preferred Roles" (e.g., `ViewOnlyAccess`) to appear at the top.
- **Plugin Sandboxing:** Strict namespace enforcement (`awsctl.plugins.*`) prevents arbitrary code execution.

### 🔍 Break Glass & Audit
- **Sensitive Roles:** Accessing high-privilege roles (e.g., `AdministratorAccess`) triggers a mandatory interactive prompt.
- **Justification:** Users must provide a reason (Ticket #), which is logged locally to `~/.awsctl/audit.log`.

---

## 📥 Installation

### Prerequisites
- **Python 3.9+** (Required)
- AWS CLI v2 installed and configured.
- **Amazon Linux 2:** Install Python 3.11 via `amazon-linux-extras` first.

### Recommended: `pipx`

To ensure isolation and easy upgrades, install via `pipx` using a pinned release tag:

> pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@v2.8.1"

---

## 🏎️ Quickstart

### 1. Setup
Initialize configuration and inject shell integration:

> awsctl setup
> source ~/.zshrc    # or: source ~/.bashrc

### 2. Login
Authenticate to your organization (opens browser):

> awsctl login --org btavm

### 3. Switch
Select Context interactively:

> awsctl switch

### 4. Verify
Check your "Flight Deck" status:

> awsctl status

---

## 🏗️ Architecture: The "Context Bridge"

`awsctl` is a **shell function wrapper** around a Python binary.

1.  **Interception:** The wrapper intercepts `awsctl switch`.
2.  **Strategy Check:** It asks the binary: "EXEC or EVAL?"
3.  **Fail-Closed:** If the binary crashes or returns invalid output, the wrapper aborts.
4.  **Evaluation:** Securely `eval`s exported variables into your current session.

---

## 🔐 Security & Compliance

`awsctl` is engineered to meet the requirements of high-assurance environments (GovCloud, FedRAMP, Finance).

| Framework | Control | `awsctl` Implementation |
| :--- | :--- | :--- |
| **NIST 800-53** | **AC-3** | Registry guardrails strictly enforce Region and Role allow-lists. |
| **NIST 800-53** | **IA-5** | Zero static keys on disk. Credentials are ephemeral. |
| **NIST 800-53** | **AU-2** | "Break Glass" creates a local audit trail for sensitive access. |
| **SLSA** | **Level 2** | Binary built via immutable CI/CD pipelines (Signed Tags). |

For a deep dive, see:
- `docs/SECURITY_APPRAISAL.md`
- `docs/GUARDRAILS.md`
- `docs/SECURITY_OPERATIONS.md`
