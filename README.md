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

- Python **3.12+**
- AWS CLI v2 (for AWS orgs)
- `az` CLI (for Azure orgs — optional)
- `gcloud` CLI (for GCP orgs — optional)

---

### Option A: GitHub Release — direct wheel download (recommended)

awsctl is distributed as a wheel attached to each [GitHub Release](https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl/releases).
You need a GitHub [Personal Access Token (PAT)](https://github.com/settings/tokens) with
`read:contents` (or `repo`) scope to access the private repository.

The `install.sh` / `install.ps1` scripts handle the download automatically:

```bash
# macOS / Linux / WSL2
export GITHUB_TOKEN=ghp_your_token_here
bash install.sh
```

```powershell
# Windows PowerShell
$env:GITHUB_TOKEN = "ghp_your_token_here"
.\install.ps1
```

Or install manually in one command:

```bash
# macOS / Linux / WSL2 — one-liner (queries the Releases API, downloads the wheel)
export GITHUB_TOKEN=ghp_your_token_here
RELEASE=$(curl -sf -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  https://api.github.com/repos/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl/releases/latest)
WHEEL_URL=$(echo "${RELEASE}" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(next(a['url'] for a in d['assets'] if a['name'].endswith('.whl')))")
curl -sf -L -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/octet-stream" "${WHEEL_URL}" -o /tmp/awsctl.whl
pip3 install --user /tmp/awsctl.whl --extra-index-url "https://pypi.org/simple/"
awsctl init --shell-only
```

---

### Option B: Script install (macOS / Linux / WSL)

Clones the repo and calls `install.sh`, which handles GitHub Packages auth automatically
when `GITHUB_TOKEN` is set, then injects the shell wrapper.

```bash
export GITHUB_TOKEN=ghp_your_token_here

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl
bash install.sh
```

`install.sh` installs via GitHub Packages (or local source if no token), adds the user
Scripts directory to PATH for the session, and injects the shell wrapper (bash/zsh/fish).

---

### Option C: Windows (PowerShell / pwsh)

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl
.\install.ps1
```

Installs via GitHub Packages (or local source if no token) and injects the PowerShell function wrapper into `$PROFILE`.

---

### Post-install: first-time setup

```bash
awsctl init         # full interactive wizard — configure orgs + shell wrapper
# OR
awsctl org add      # add a single org interactively (auth-first for Azure/GCP)
```

---

### Upgrading

Once installed, upgrade in place without cloning the repo.
`awsctl upgrade` queries the GitHub Releases API, downloads the latest wheel, and runs `pip install --upgrade`:

```bash
# macOS / Linux / WSL2
export GITHUB_TOKEN=ghp_your_token_here
awsctl upgrade

# Windows PowerShell
$env:GITHUB_TOKEN = "ghp_your_token_here"
awsctl upgrade
```

`GITHUB_TOKEN` must have `read:contents` (or `repo`) scope on the repository.

`awsctl upgrade` pulls the latest release from GitHub Packages and restarts gracefully.

---

### Uninstall

```bash
bash uninstall.sh   # macOS / Linux / WSL
# or
.\uninstall.ps1     # Windows PowerShell
```

The uninstall scripts remove the shell wrapper from all profiles, uninstall the pip package,
clean awsctl-managed `[sso-session]` blocks from `~/.aws/config`, and remove `~/.awsctl`.

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

### Lifecycle completeness
- **FEATURE:** `awsctl org add` — auth-first interactive wizard; logs into AWS/Azure/GCP first, then discovers subscriptions/projects live for the picker.
- **FEATURE:** `awsctl org list` — tabular view of all configured orgs with provider label and key identifier (SSO URL / tenant ID / project ID).
- **FEATURE:** `awsctl org remove` — removes an org entry from orgs.yaml.
- **FEATURE:** `awsctl init --shell-only` — non-interactive flag to inject the shell wrapper only (no wizard); used by Homebrew `post_install` and CI.
- **FEATURE:** `awsctl doctor` — full health-check implementation; `check_tool`, `check_aws_version`, `check_shell_integration`, `check_permissions`, `check_time_sync`, `check_network_ssl`, `check_wsl_performance` all return `(bool, str)` tuples; `run_diagnostics` prints sectioned System Health Check report.
- **FEATURE:** `Formula/awsctl.rb` — Homebrew formula with hermetic virtualenv install, shim scripts, and `post_install` shell integration.
- **FIX:** `uninstall.sh` now removes awsctl-managed `[sso-session <name>]` sections from `~/.aws/config`.

### Cross-cloud
- **FEATURE:** Cross-cloud provider support — Azure and GCP alongside AWS via a unified `CloudProvider` interface.
- **FEATURE:** Native PowerShell shell wrapper (`awsctl` PS function) — full Split-Plane support on Windows without WSL.
- **FEATURE:** Fish shell wrapper — `~/.config/fish/functions/awsctl.fish` auto-installed via `awsctl init`.
- **FEATURE:** `awsctl init` wizard detects the running shell (bash/zsh/PowerShell/fish) and installs the appropriate wrapper.
- **FEATURE:** `provider` field in org config selects the cloud backend (`aws` | `azure` | `gcp`; defaults to `aws` for backward compatibility).

### Quality
- **FIX:** CLI dispatcher resolves handlers at call time so `monkeypatch` works correctly in tests.
- **FIX:** `shell.py` — atomic write propagates `OSError`, handles read failures gracefully, correct newline spacing.
- **CHORE:** 220+ tests passing; all doctor, shell, wizard, provider, and CLI tests green.

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

### ✅ Validation Summary (v3.0.0)

- ✅ 220+ unit tests passing (doctor, shell, wizard, providers, CLI)
- ✅ Cross-platform: macOS (zsh/bash/fish), Linux (bash/zsh/fish), Windows (PowerShell/pwsh), WSL2
- ✅ Static analysis: Bandit, `pip-audit`, ruff, black compliant
- ✅ CI/CD integrity: SLSA-aligned artifact release and cryptographic signature verification
