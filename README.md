# awsctl: Zero Trust AWS Credential Management

[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/1/badge)](https://bestpractices.coreinfrastructure.org/projects/1)
[![SLSA Level 2](https://slsa.dev/images/gh-badge-level2.svg)](https://slsa.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Zero Trust](https://img.shields.io/badge/Security-Zero%20Trust-blueviolet)](docs/SECURITY.md)
[![NIST 800-53](https://img.shields.io/badge/NIST_800--53-Compliant-blue?style=flat&logo=nist)](docs/SECURITY_APPRAISAL.md)
[![FedRAMP](https://img.shields.io/badge/FedRAMP-Ready-005288?style=flat&logo=files)](docs/SECURITY_APPRAISAL.md)
[![GovCloud](https://img.shields.io/badge/AWS_GovCloud-Compatible-232F3E?style=flat&logo=amazon-aws)](docs/USER_GUIDE.md)
[![FIPS 140-3](https://img.shields.io/badge/FIPS_140--3-Compatible-green?style=flat&logo=openssl)](docs/SECURITY.md)

`awsctl` is a production-grade command-line interface for AWS IAM Identity Center (SSO).
It is designed for high-security environments where **Zero Trust** is mandatory.
It streamlines login, enforces organization-wide guardrails, and provides a fast, shell-integrated workflow for switching accounts and roles without ever writing static credentials to disk.

---

## ⚡️ Key Features

### 🔐 Zero Trust Credential Architecture

- **In-Memory Only:** Uses the **Context Bridge** shell integration pattern to export short-lived STS credentials directly to your shell environment variables.
- **Diskless:** Never writes `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to `~/.aws/credentials`.
- **Isolated:** Each terminal tab maintains its own independent AWS context.
- **TTY Guard:** Detects and blocks accidental printing of credentials to the screen.

### 🛡️ Registry-Backed Guardrails

- **Hydration Model:** Configuration is hydrated from a central Registry (Embedded or Signed Remote) compiled into the tool or loaded securely at runtime.
- **Region Locking:** Prevents users from authenticating or switching to non-approved regions (for example, restrict to `eu-west-2`).
- **Role Prioritization:** Enforces "Preferred Roles" (for example, `ViewOnlyAccess`) to appear at the top of selection lists, promoting Least Privilege.
- **Plugin Enforcement:** Mandatory security hooks (VPN checks, Okta validation, device posture) run _before_ login.
- **Break Glass Audit:** Enforces mandatory justification prompts when accessing sensitive roles (e.g., `AdministratorAccess`).
- **Version Enforcement:** Blocks login if the client version is older than the policy requirement.

### 🚀 Developer Experience

- **Smart Context Switching:** Fuzzy-search selection for Accounts and Roles.
- **Smart History:** Automatically remembers your last 5 used contexts for instant access.
- **Quick Aliases:** Switch contexts instantly using `@alias` syntax (e.g., `awsctl switch @prod`).
- **Context Toggle:** Jump back to your previous context instantly with `awsctl switch -`.
- **Headless Support:** Full support for CI/CD and scripts via non-interactive flags.
- **Implicit Execution:** Run commands in your active context using `awsctl exec -- <command>`.

---

## 📥 Installation

### Recommended: `pipx`

To ensure isolation and easy upgrades, install via `pipx` using a pinned release tag:

    pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@v2.7.0"

Validation:

    awsctl --version
    # Output: v2.7.0 - Developer Delight


git clone git@github.com:myorg/awsctl.git
cd awsctl

./dev
# OR:
make setup
make install

Run the full suite:

make lint
make typecheck
make test
make security

---

## 🏎️ Quickstart

### 1. Setup and Shell Integration

Initialize the configuration and inject the shell wrapper function:

    awsctl setup
    source ~/.zshrc    # or: source ~/.bashrc

**Note:** You **must** reload your shell.
Direct execution of the binary is blocked for security.

### 2. Authenticate

Log in to your organization (triggers browser flow):

    awsctl login --org engineering

### 3. Select Context

Interactively select your Account, Role, and Region:

    awsctl switch

### 4. Verify

Check your "Flight Deck" status:

    awsctl status

---

## 🏗️ Architecture: The "Context Bridge"

`awsctl` is not just a binary;
it is a shell function wrapper.

- **Interception:** When you type `awsctl switch`, the shell function intercepts the command.
- **Strategy Check:** It asks the binary: "Does this command need to modify the shell environment?"
- **Evaluation:**
  - If **Yes** (`switch`), the binary outputs `export AWS_...` commands via a secure pipe.
  - The shell wrapper `eval`s them into your current session.
  - If **No** (`status`), the binary runs as a standard subprocess.
This allows secure environment variable injection without writing files to disk.

---

## 🔐 Security & Compliance

`awsctl` is engineered to meet the requirements of high-assurance environments (GovCloud, FedRAMP, Finance).

### Compliance Matrix

| Framework | Control | `awsctl` Implementation |
| :--- | :--- | :--- |
| **NIST 800-53** | **AC-3** (Access Enforcement) | Registry guardrails strictly enforce Region and Role allow-lists on the endpoint. |
| **NIST 800-53** | **IA-5** (Authenticator Mgmt) | Zero static keys on disk. Credentials exist only in ephemeral process memory. |
| **NIST 800-53** | **AU-2** (Audit Events) | "Break Glass" access to sensitive roles captures user justification in a local audit log. |
| **SLSA** | **Level 2** (Build Integrity) | Binary built via immutable CI/CD pipelines from version-controlled source (Signed Tags). |
| **FIPS 140-3** | **SC-13** (Crypto) | Compatible with FIPS-enabled hosts (relies on OS OpenSSL modules via Python). |

### Security Overview

- **Credential Storage:** Ephemeral (RAM only).
- **SSO Tokens:** Delegated to AWS CLI v2 (`~/.aws/sso/cache`, permissions `0600`).
- **Config Permissions:** `~/.awsctl` directory enforced to `0700`.
- **Fail-Closed:** Shell integration aborts immediately if strategy checks fail.
- **Namespace Isolation:** Plugins must adhere to strict namespace naming to prevent arbitrary code execution.
- **Remote Integrity:** Tier 3 Remote Registry uses Minisign cryptographic verification to prevent tampering.

### ⚙️ CI/CD Assurance

All code changes are validated by a comprehensive CI matrix that includes:

- **Cross-Platform Execution:** Tests run on Linux and macOS.
- **Shell Compatibility:** Specific jobs verify logic within **Bash, Zsh, and Fish** shells.
- **Security Gates:** Mandatory execution of **Mypy, Ruff, and Bandit** before deployment.

For a deep dive, see:

- `docs/SECURITY_APPRAISAL.md`
- `docs/GUARDRAILS.md`
- `docs/SECURITY_OPERATIONS.md`
