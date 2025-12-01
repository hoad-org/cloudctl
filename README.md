# awsctl

`awsctl` is a production-grade command-line interface for AWS IAM Identity Center (SSO).  
It is designed for high-security environments where **Zero Trust** is mandatory.  
It streamlines login, enforces organization-wide guardrails, and provides a fast, shell-integrated workflow for switching accounts and roles without ever writing static credentials to disk.

---

## ⚡️ Key Features

### 🔐 Zero Trust Credential Architecture

- **In-Memory Only:** Uses the "Trojan Horse" shell integration pattern to export short-lived STS credentials directly to your shell environment variables.
- **Diskless:** Never writes `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to `~/.aws/credentials`.
- **Isolated:** Each terminal tab maintains its own independent AWS context.

### 🛡️ Registry-Backed Guardrails

- **Hydration Model:** Configuration is hydrated from a central, immutable `registry.py` compiled into the tool.
- **Region Locking:** Prevents users from authenticating or switching to non-approved regions (for example, restrict to `eu-west-2`).
- **Role Prioritization:** Enforces "Preferred Roles" (for example, `ViewOnlyAccess`) to appear at the top of selection lists, promoting Least Privilege.
- **Plugin Enforcement:** Mandatory security hooks (VPN checks, Okta validation, device posture) run *before* login.

### 🚀 Developer Experience

- **Smart Context Switching:** Fuzzy-search selection for Accounts and Roles.
- **Context Toggle:** Jump back to your previous context instantly with `awsctl switch -`.
- **Headless Support:** Full support for CI/CD and scripts via non-interactive flags.
- **Implicit Execution:** Run commands in your active context using `awsctl exec -- <command>`.

---

## 📥 Installation

### Recommended: `pipx`

To ensure isolation and easy upgrades, install via `pipx` using a pinned release tag:

    pipx install "git+https://github.com/your-org/awsctl.git@v2.0.0"

Validation:

    awsctl --version
    # Output: awsctl v2.0.0

---

## 🏎️ Quickstart

### 1. Setup and Shell Integration

Initialize the configuration and inject the shell wrapper function:

    awsctl setup
    source ~/.zshrc    # or: source ~/.bashrc

Note: Fish shell users must manually install the wrapper. See `docs/SHELL_INTEGRATION.md`.

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

## 🛠️ Command Reference (High Level)

| Command          | Description                                     | Strategy |
|------------------|-------------------------------------------------|----------|
| `awsctl login`   | Authenticate via AWS SSO.                       | EXEC     |
| `awsctl switch`  | Interactive context switcher (exports vars).    | EVAL     |
| `awsctl switch -`| Toggle to immediate previous context.           | EVAL     |
| `awsctl logout`  | Clear credentials and cached tokens.            | EVAL     |
| `awsctl status`  | View current identity and token expiry.         | EXEC     |
| `awsctl exec`    | Run command in a target account (one-shot).     | EXEC     |
| `awsctl doctor`  | Run system diagnostics and health checks.       | EXEC     |
| `awsctl list`    | View available Orgs, Accounts, or Roles.        | EXEC     |

(Export to Sheets: copy this table into your spreadsheet tool of choice.)

---

## 🧩 Configuration (`~/.awsctl/orgs.yaml`)

`awsctl` uses a **Hydration Model**.

- Your local config is minimal; it only declares which organizations you want to enable.
- All security settings come from the compiled Registry.

Example `~/.awsctl/orgs.yaml`:

    enabled_orgs:
      - engineering
      - production

    plugins:
      enabled:
        - awsctl.plugins.okta

Notes:

- You cannot override `allowed_regions` or `start_url` locally.
- These are enforced by the Registry (`src/awsctl/registry.py`).

---

## 🏗️ Architecture: The "Trojan Horse"

`awsctl` is not just a binary; it is a shell function wrapper.

- **Interception:** When you type `awsctl switch`, the shell function intercepts the command.
- **Strategy Check:** It asks the binary: "Does this command need to modify the shell environment?"
- **Evaluation:**
  - If **Yes** (for example, `switch`), the binary outputs `export AWS_...` commands, and the shell function `eval`s them.
  - If **No** (for example, `status`), the binary runs as a standard subprocess.

This allows secure environment variable injection without requiring the user to manually type `eval $(...)`.

---

## 🔐 Security Overview

- **Credential Storage:** Ephemeral (RAM only).
- **SSO Tokens:** Delegated to AWS CLI v2 (`~/.aws/sso/cache`, permissions `0600`).
- **Config Permissions:** `~/.awsctl` directory enforced to `0700`.
- **Compliance:** Full audit trail via CloudTrail (on AWS side) and immutable Registry policies (on client side).

For a deep dive, see:

- `docs/SECURITY_APPRAISAL.md`
- `docs/GUARDRAILS.md`
- `docs/SECURITY_OPERATIONS.md`
