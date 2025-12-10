# file: docs/USER_GUIDE.md
# awsctl User Guide (v2.8.0)

`awsctl` is a security-focused helper for AWS IAM Identity Center (SSO).
It allows you to obtain short-lived credentials for your shell without ever storing sensitive keys on your disk.

---

## 1. Installation

The recommended method is `pipx`, which installs the tool in an isolated environment and links the binary to your `PATH`.

### Prerequisites (typical workstation setup)

- AWS CLI v2 installed and configured for IAM Identity Center (SSO).
- A supported shell (bash or zsh).

### Install `awsctl` pinned to v2.8.0

> pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@v2.8.0"

### Verify installation

> awsctl --version

You should see a version string containing `2.8.0`.

---

## 2. First-Time Setup

Run the interactive setup wizard. This handles initial configuration and shell integration for you.

> awsctl setup

The wizard will:

- Create or update your `~/.awsctl` configuration directory.
- Generate a minimal `orgs.yaml` (org enablement file) as needed.
- Inject the shell wrapper function into your shell configuration file (for example, `~/.bashrc` or `~/.zshrc`).

⚠️ **Critical Step:** The setup wizard modifies your shell configuration (`~/.bashrc` or `~/.zshrc`).
You must reload your shell for these changes to take effect:

> source ~/.zshrc
> # or
> source ~/.bashrc

After reloading, `awsctl` should be a **shell function**, not just a binary.
Confirm with:

> type awsctl

You should see output similar to:

> awsctl is a function

If you instead see a path (for example, `/usr/local/bin/awsctl`), the wrapper is not loaded correctly and `switch` will not update your shell environment.

---

## 3. How awsctl Works (Execution Wrapper Overview)

At a high level:

- `awsctl` installs a shell **function** which wraps an internal binary (`_awsctl_bin`).
- When you run interactive commands (like `awsctl switch`), the function intercepts the call.
- The function receives a sanitized payload of `export AWS_...` statements.
- It uses `eval` to apply those variables to your **current shell**.

This “Context Bridge” pattern allows `awsctl` to update your shell environment safely.
**Credentials are held only in memory.**

**CRITICAL SECURITY WARNING (TTY Guard):**
You must **always** run the `awsctl` function.
Running the underlying binary (`_awsctl_bin`) directly for `switch` or `exec` commands is **blocked** and will trigger a security error.

---

## 4. Daily Workflow

The typical daily workflow consists of four steps.

### Step 1: Login

Authenticate with your Identity Provider (Okta, Azure AD, etc.):

> awsctl login --org btavm

This will:

- Open your browser for SSO authentication.
- Store the SSO token in the AWS CLI v2 SSO cache, typically under `~/.aws/sso/cache/`.

Once this token exists, `awsctl` can obtain short-lived AWS credentials on demand.

---

### Step 2: Switch Context

Select your AWS Account, Role, and Region interactively:

> awsctl switch

#### 🕒 Smart History

`awsctl` remembers your last 5 contexts.
They appear at the very top of the list with a clock icon:

> > 🕒 Production (123456789012)
>   🕒 Sandbox (112233445566)
>   --- All Accounts ---
>   Analytics
>   ...

Behind the scenes:

- `awsctl` consults the central registry (maintained by your platform team) for allowed regions and role ordering.
- Guardrails ensure you can only switch to regions and roles approved for your organization.
- **Session Duration Note:** The resulting credentials are short-lived (typically 8–12 hours) and are not automatically refreshed.

After a successful switch, your shell is populated with:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_DEFAULT_REGION`

These values are short-lived and stored only in memory.

---

### Step 3: Work

Once your context is set, use the standard AWS tooling:

> aws s3 ls
> terraform plan

Any tool that respects standard AWS environment variables will run in the context you selected with `awsctl switch`.

---

### Step 4: Toggle Back (Smart Switching)

Need to jump back to the previous account you were working in?

> awsctl switch -

This behaves similarly to `cd -` in your shell:
it toggles back to the previously active context (account/role/region).

---

## 5. Advanced Usage

### 5.1 Quick Aliases

Define shortcuts in `~/.awsctl/orgs.yaml`:

> aliases:
>   prod:
>     org: btavm
>     account: "123456789012"
>     role: ViewOnlyAccess
>     region: eu-west-1

Use them instantly:

> awsctl switch @prod

### 5.2 Non-Interactive Switching

For scripts or when you know the exact target context, you can bypass the interactive selector:

> awsctl switch --account 123456789012 --role AdministratorAccess --region us-east-1

Notes:

- All three flags (`--account`, `--role`, `--region`) are typically required for deterministic behavior.
- Guardrails still apply. If the region or role is not allowed, the switch will fail.

### 5.3 Exec (One-Shot Commands)

Run a command in a specific context without altering your current shell environment.

Implicit (use last known context):

> awsctl exec -- aws s3 ls

Explicit (override context):

> awsctl exec --account 123456789012 --role ReadOnly --region eu-west-1 -- aws s3 ls

In both cases:

- `awsctl` obtains credentials for the chosen context.
- It runs the provided command in a subprocess.
- Your existing shell environment remains unchanged after the command completes.

This is useful for:

- One-off diagnostic commands.
- Scripts that should not permanently change the caller’s environment.

### 5.4 Dotfile Export (.env Files)

Generate a `.env` file with the current credentials for use in Docker or other tools.
The output is POSIX export compliant (text, not JSON).

> awsctl env > .env

You can then use tools that support environment file loading, for example:

> docker compose --env-file .env up

This still benefits from short-lived credentials.

---

## 6. Security Overview (v2.8.0)

`awsctl` is designed for secure workstation use with AWS IAM Identity Center.

Key properties:

- **No long-term access keys on disk.**
- **Short-lived credentials in memory.**
- **TTY Guard:** Running the binary directly for context commands is blocked for security.
- **Central Guardrails:** Regions and roles are controlled by a central registry.
- **Break Glass Audit:** Sensitive roles trigger a mandatory justification prompt.
- **Namespace Isolation:** Plugins must use approved naming conventions (`awsctl.plugins.*`) to prevent code injection via config files.

See `docs/SECURITY_APPRAISAL.md` for a deeper security assessment.

---

## 7. Guardrails & Registry Model

`awsctl` separates policy (admin-controlled) from preference (user-controlled).

### High-Level Model

**Corporate Registry (Policy)**
Lives in the awsctl source code (or a remote signed HTTPS endpoint).

Defines:
- Organizations (org names such as `btavm`)
- SSO start URLs and SSO regions
- Allowed AWS regions per org
- Preferred role ordering
- Sensitive Roles (triggering Break Glass)
- Plugin Namespace Allowlist (maintained by your platform/security team)

**User Enablement File (Preference)**
Typically: `~/.awsctl/orgs.yaml`.

- Allows users to declare which orgs are enabled on their machine.
- Does not allow overriding guardrails, start URLs, or SSO regions.

**CRITICAL PLUGIN NOTE:**
If you use custom plugins, ensure they are enabled using the full namespace, for example:

> awsctl.plugins.okta
> # not just okta

---

## 8. Working with Multiple Orgs

If your company uses multiple AWS organizations, your platform team may configure several org entries in the registry and enable them for you.

**General usage pattern:**

Login to a specific org:

> awsctl login --org btavm

Switch within that org:

> awsctl switch

You can repeat the login/switch workflow for another org if your workstation is allowed to access it.

---

## 9. Diagnostics and Debugging

When something goes wrong, start with built-in diagnostics.

### 9.1 Doctor Command

Run:

> awsctl doctor

Typical checks include:

- Registry availability (can awsctl see the configured orgs?).
- Basic configuration sanity (e.g., presence of `~/.awsctl`).
- Environment checks (AWS CLI v2 availability).

Review the output for misconfiguration hints (missing orgs, bad paths, strict policy blocks).

---

## 10. Troubleshooting

### 10.1 “Security Error: Refusing to print credentials to TTY”

**Symptom:** Immediate security error and exit when running a command that exports credentials.

**Cause:**
- The tool detected that you ran the internal binary (`_awsctl_bin`) directly, or
- An automation script is not properly invoking the `awsctl` function.

**What to do:**
- Always run the shell function `awsctl`.
- Never run `_awsctl_bin` directly for `switch` or `exec`.

---

### 10.2 “Command not found: _awsctl_bin”

**Symptom:** `command not found: _awsctl_bin`
**Cause:** The internal binary is not on your PATH.
`pipx` may have installed it into `~/.local/bin`, which is not in your PATH.

**What to do:**

> pipx ensurepath

Then re-open your terminal (or source your shell config).

If needed, reinstall:

> pipx install --force "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@v2.8.0"

---

### 10.3 “Switch doesn’t change my variables”

**Symptom:** `awsctl switch` appears to run, but `env | grep AWS_` shows no updates.

**Cause:**
- The shell wrapper is not loaded, or
- You invoked the underlying binary directly (blocked by TTY Guard).

**What to do:**

> type awsctl

If it prints `awsctl is a function`, the wrapper is loaded.
If it prints a path (e.g., `/usr/local/bin/awsctl`), the wrapper is missing.

Reload your shell config:

> source ~/.zshrc
> # or
> source ~/.bashrc

If it still doesn’t appear, re-run:

> awsctl setup

and reload.

---

### 10.4 “New account not showing up”

**Symptom:** A newly granted account/role doesn’t appear in the selector.

**Cause:** AWS CLI v2 caches account and role lists.

**What to do:**

> awsctl refresh

If the account still doesn’t appear:
- Confirm the account/role is granted to your SSO identity.
- Log out of your browser SSO and log back in.

Then run:

> awsctl login

===============================================
# file: src/awsctl/registry.py
# SPDX-License-Identifier: MIT
"""
The Corporate Registry.
Single source of truth for Organization definitions, Guardrails, and Policies.
"""

import os
from typing import Any, Dict, List, Optional, cast

from awsctl import config

# ---------------------------------------------------------------------------
# Tier 3: Signed Registry Trust Anchor
# ---------------------------------------------------------------------------
# [SECURITY] Hardcoded Public Key to prevent Trust Downgrade attacks.
_TRUSTED_ROOT_KEY = "RWQf6LRCGA9i53mlYec++jCqiotM3TRmxKv2kj/..."


# ---------------------------------------------------------------------------
# Tier 1: Embedded Defaults (Immutable Policy Source)
# ---------------------------------------------------------------------------

_EMBEDDED_ORGS: List[Dict[str, Any]] = [
    {
        "name": "btavm",
        "label": "btavm",
        "description": "AVM Org for MVP.",
        "sso_start_url": os.environ.get(
            "AWSCTL_BTAVM_URL", "https://dev-placeholder.awsapps.com/start"
        ),
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["SecurityAuditor"],
        "sensitive_roles": ["Admin", "DBAdmin", "AdministratorAccess"],
        "min_client_version": "2.8.0",
        # [FIX] Activated Okta plugin for pre-flight security checks
        "plugins": ["awsctl.plugins.okta"],
        "role_aliases": {
            "AWSReservedSSO_DatabaseAdministrator_.*": "DBAdmin",
            "AWSReservedSSO_AdministratorAccess_.*": "Admin",
            "AWSReservedSSO_SecurityAuditor_.*": "SecurityAuditor",
        },
    },
    {
        "name": "btdev",
        "label": "btdev",
        "description": "BT Development org.",
        "sso_start_url": os.environ.get(
            "AWSCTL_BTDEV_URL", "https://dev-placeholder.awsapps.com/start"
        ),
        "sso_region": "us-east-1",
        "default_region": "us-east-1",
        # Guardrails
        "allowed_regions": ["us-east-1", "us-east-2"],
        "preferred_roles": ["org_it-auditor"],
        "sensitive_roles": [
            "AdministratorAccess",
            "AccountAdmin",
        ],
        # [FIX] Activated Okta plugin for pre-flight security checks
        "plugins": ["awsctl.plugins.okta"],
        "role_aliases": {
            "AWSReservedSSO_AccountAdmin_.*": "AccountAdmin",
            "AWSReservedSSO_AdministratorAccess_.*": "AdministratorAccess",
            "AWSReservedSSO_org_it-auditor_.*": "OrgITAuditor",
        },
    },
]

# ---------------------------------------------------------------------------
# Registry Loader
# ---------------------------------------------------------------------------


def get_registry() -> List[Dict[str, Any]]:
    try:
        raw_cfg = config.load_raw_config()
        reg_conf = raw_cfg.get("registry", {})
        url: Optional[str] = cast(Optional[str], reg_conf.get("url"))

        if url:
            from awsctl.registry_loader import fetch_remote_registry

            # [SECURITY] Use the pinned Trust Anchor, ignoring any user-provided key.
            return fetch_remote_registry(url, public_key=_TRUSTED_ROOT_KEY)

    except Exception:  # nosec
        pass

    return _EMBEDDED_ORGS


KNOWN_ORGS = get_registry()


def get_choices() -> List[Dict[str, Any]]:
    choices: List[Dict[str, Any]] = []
    for o in KNOWN_ORGS:
        display = o.get("label", o["name"])
        desc = o.get("description")
        if desc:
            display = f"{display} — [dim]{desc}[/]"
        choices.append({"name": display, "value": o})
    return choices

===============================================
# file: .vscode/settings.json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.analysis.typeCheckingMode": "strict",
    "python.testing.pytestArgs": ["tests"],
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true,
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },
    "ruff.importStrategy": "fromEnvironment",
    "files.exclude": {
        "**/.git": true,
        "**/.DS_Store": true,
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/.mypy_cache": true,
        "**/.ruff_cache": true,
        "**/*.egg-info": true
    }
}

===============================================
# file: .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug: Doctor",
            "type": "debugpy",
            "request": "launch",
            "module": "awsctl",
            "args": ["doctor"],
            "console": "integratedTerminal"
        },
        {
            "name": "Debug: Login (btavm)",
            "type": "debugpy",
            "request": "launch",
            "module": "awsctl",
            "args": ["login", "--org", "btavm"],
            "console": "integratedTerminal"
        },
        {
            "name": "Debug: Switch",
            "type": "debugpy",
            "request": "launch",
            "module": "awsctl",
            "args": ["switch"],
            "console": "integratedTerminal"
        },
        {
            "name": "Debug: Current File",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ]
}

===============================================
# file: .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "charliermarsh.ruff",
        "ms-python.mypy-type-checker",
        "tamasfe.even-better-toml",
        "yzhang.markdown-all-in-one"
    ]
}

===============================================
# file: docs/CLI_REFERENCE.md
# awsctl Command Reference (v2.8.0)

This document is the **Single Source of Truth** for the `awsctl` CLI.

---

## 1. Core Workflow

### `awsctl login`
- **Strategy:** `EXEC`
- **Purpose:** Authenticate to AWS IAM Identity Center (SSO).
- **Example:** `awsctl login --org btavm`

### `awsctl switch`
- **Strategy:** `EVAL`
- **Purpose:** Select a specific Account, Role, and Region to export into the current shell.
- **Exports:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`.
- **Example:** `awsctl switch` or `awsctl switch @prod`

### `awsctl logout`
- **Strategy:** `EVAL`
- **Purpose:** Securely clear credentials and cached tokens.

---

## 2. Discovery and Status

### `awsctl status`
- **Strategy:** `EXEC`
- **Purpose:** The "Flight Deck" dashboard. Shows current identity and token expiry.

### `awsctl list`
- **Strategy:** `EXEC`
- **Purpose:** Explore the hierarchy.
- **Subcommands:** `orgs`, `accounts`, `roles`.
- **Flags:** `--json` (Output raw JSON for scripting).

### `awsctl doctor`
- **Strategy:** `EXEC`
- **Purpose:** System diagnostics (Registry, Plugins, Config permissions).

---

## 3. Automation

### `awsctl exec`
- **Strategy:** `EXEC`
- **Purpose:** Run a command in a specific context *without* changing your current shell's environment variables.
- **Example:** `awsctl exec --account 123456789012 -- aws s3 ls`

### `awsctl env`
- **Strategy:** `EXEC`
- **Purpose:** Output current exports to stdout (useful for `.env` files).
- **Security:** Requires output redirection (pipe/file) to function; blocked on TTY.

---

## 4. System

### `awsctl setup`
- **Strategy:** `EXEC`
- **Purpose:** First-time configuration and shell integration injection.

### `awsctl cache-clear`
- **Strategy:** `EXEC`
- **Purpose:** Force refresh of account lists.

===============================================
# file: docs/DEVELOPER_ONBOARDING_AND_INTERNAL_ARCHITECTURE.md
# Developer Onboarding & Internal Architecture

**Target Audience:** Maintainers, Contributors, and Platform Engineers inheriting `awsctl`.
**Version:** v2.8.0

---

## 1. Architecture Overview

`awsctl` is not a standard CLI tool; it is a **shell-integrated identity broker**.
It bridges the gap between Python (where logic lives) and the Shell (where credentials must be exported).

### 1.1 The "Context Bridge" Pattern
1.  **Wrapper (`awsctl` function):** Intercepts user commands.
2.  **Binary (`_awsctl_bin`):** Calculates the state change.
3.  **Strategy Output:** The binary emits a "Strategy" line (`EXEC` or `EVAL`).
4.  **Execution:**
    * `EXEC`: The binary runs a subprocess (e.g., `status`, `login`).
    * `EVAL`: The binary outputs `export VAR=VAL` commands, which the wrapper `eval`s.

---

## 2. State Management

* **Identity:** `~/.aws/sso/cache/*.json` (Managed by AWS CLI v2).
* **Context:** `~/.aws/awsctl-context.json` (Stores current selection for "Smart History").
* **Config:** `~/.awsctl/orgs.yaml` (User enablement preference).
* **Policy:** **Immutable.** Hardcoded in `registry.py` or loaded from signed Remote Registry.

---

## 3. Development Workflow

### 3.1 Prerequisites
* Python 3.9+
* `make`
* `pre-commit`

### 3.2 Quick Start
The `Makefile` automates the entire lifecycle.

> # 1. Create venv and install dependencies
> make install
>
> # 2. Activate
> source .venv/bin/activate
>
> # 3. Run full test suite
> make test
>
> # 4. Run static analysis (Bandit, MyPy, Ruff)
> make lint

### 3.3 Testing Strategy
We enforce a **strict >78% coverage floor**.
* **Unit Tests (`tests/`):** Validate logic in isolation.
* **Integration (`tests/test_integration_full.py`):** "God Mode" mock of AWS CLI.
* **Smoke Test (`tools/comprehensive_smoke.sh`):** Validates the shell wrapper logic.

---

## 4. Release Process

1.  **Verify:** `make test` and `make security`.
2.  **Tag:** Create a semantic version tag (e.g., `v2.8.1`).
3.  **Build:** GitHub Actions builds the wheel and sdist.
4.  **Publish:** Artifacts are attached to the GitHub Release.

===============================================
# file: docs/PLUGIN_DEVELOPMENT.md
# Plugin Framework — awsctl v2.8.0

Plugins allow enforcement of corporate posture (e.g., VPN check, device compliance) before login.

---

## 1. Requirements

### 1.1 Namespace Restriction
For security, plugins must be importable via the protected namespace:
* `awsctl.plugins.<name>`

### 1.2 Exposed Function
The module must define:

> def pre_login(org: dict) -> None:
>     ...

### 1.3 Execution Model
* **Threaded:** Runs in a separate thread to prevent blocking the UI loop indefinitely.
* **Timeout:** Hard limit of **10 seconds**. (Best practice: keep under 3 seconds).
* **Fail-Closed:** Uncaught exceptions or timeouts abort the login process.

---

## 2. Best Practices

* **No Side Effects:** Do not modify the `org` dictionary or global state.
* **StdErr Reporting:** Print user-facing errors to `sys.stderr` using `console.print`.
* **Exit Codes:** Use `sys.exit(1)` to signal a check failure (e.g., VPN disconnected).

===============================================
# file: docs/TROUBLESHOOTING.md
# Troubleshooting — awsctl v2.8.0

## 1. Common Issues

### 1.1 Shell wrapper not loaded
**Symptom:** `awsctl switch` runs but env vars don't change.
**Fix:** Run `source ~/.zshrc` (or `.bashrc`).

### 1.2 Corrupted wrapper (Dirty Edit)
**Symptom:** `setup` says "Wrapper already present" but it doesn't work.
**Fix:** Manually delete the `awsctl() { ... }` block from your rc file and re-run `awsctl setup`.

### 1.3 SSO cache invalid
**Symptom:** "Token does not exist" loops.
**Fix:**

> awsctl cache-clear
> awsctl login --org btavm

### 1.4 Fish shell issues
**Cause:** `setup` does not support Fish automatic injection.
**Fix:** Manually install the wrapper function (see Shell Integration doc).

---

## 2. SSL & Certificate Issues

### 2.1 macOS: "SSL: CERTIFICATE_VERIFY_FAILED"
**Fix:** Export system certs to PEM and set `REQUESTS_CA_BUNDLE`.

> security find-certificate -a -p /Library/Keychains/System.keychain > ~/macos_certs.pem
> export REQUESTS_CA_BUNDLE="$HOME/macos_certs.pem"

### 2.2 Windows / WSL: "Self Signed Certificate"
**Fix:** Import the corporate root CA into the WSL trust store (`/usr/local/share/ca-certificates/`) and run `update-ca-certificates`.

---

## 3. Installation Issues

### 3.1 `pipx install` fails
**Fix:** Ensure `git` is installed via your OS package manager (`brew`, `apt`, `yum`).
