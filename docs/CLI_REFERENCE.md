# file: docs/CLI_REFERENCE.md
# awsctl Command Reference (v2.8.0)

This document is the **Single Source of Truth** for the `awsctl` CLI.

---

## 1. Core Workflow

### `awsctl login`

- **Strategy:** `EXEC`
- **Purpose:** Authenticate to AWS IAM Identity Center (SSO).
- **Security Note:** A **mandatory plugin check** (e.g., VPN status) runs before the browser window opens.
- **Example:**

> awsctl login --org btavm

### `awsctl switch`

- **Strategy:** `EVAL`
- **Purpose:** Select a specific Account, Role, and Region to export into the current shell.
- **Exports (In-Memory):** Exports `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, and `AWS_DEFAULT_REGION`.
- **Example:**
  - Interactive:
    > awsctl switch
  - Toggle Back:
    > awsctl switch -
  - Quick Alias:
    > awsctl switch @prod
- **Syntax:**

> awsctl switch [ @alias | - | --account <id> --role <name> --region <region> ]

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
- **Purpose:** Run a command in a specific context _without_ changing your current shell's environment variables. The temporary session is **destroyed** upon command completion.
- **Example:**

> awsctl exec --account 123456789012 -- aws s3 ls

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
- **Purpose:** Force refresh of account lists (alias: `awsctl refresh`).
