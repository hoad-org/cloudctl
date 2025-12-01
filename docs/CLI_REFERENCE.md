# awsctl Command Reference (v2.0.0)

This document is the **Single Source of Truth** for the `awsctl` CLI.  
It defines the architecture where the shell function `awsctl` intercepts commands to determine if they should modify the shell environment (`EVAL`) or just run a process (`EXEC`).

---

## 1. Environment Variables

| Variable          | Description                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| `AWSCTL_HEADLESS` | If set to `1`, `awsctl setup` runs without interactive prompts.            |
| `CI`              | If set (for example by GitHub Actions), implies `AWSCTL_HEADLESS=1`.       |
| `AWS_PROFILE`     | `awsctl` actively **unsets** this during `switch` to prevent conflicts.    |

---

## 2. Core Workflow Verbs

### `awsctl login`

- **Strategy:** `EXEC` (or `EVAL` if chaining)
- **Purpose:** Authenticate to AWS IAM Identity Center (SSO).

Usage patterns:

- Interactive (org prompt):

      awsctl login

- Explicit org:

      awsctl login --org engineering

- Chained (login + switch in one go):

      awsctl login --org engineering --account 123456789012 --role Admin

---

### `awsctl switch`

- **Strategy:** `EVAL`
- **Purpose:** Select a specific Account, Role, and Region to export into the current shell.

Usage patterns:

- Interactive fuzzy search:

      awsctl switch

- Smart toggle (jump to previous context):

      awsctl switch -

- Explicit, non-interactive:

      awsctl switch --account <id> --role <name> --region <region>

Exports:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_DEFAULT_REGION`

---

### `awsctl logout`

- **Strategy:** `EVAL`
- **Purpose:** Securely clear credentials.

Behavior:

1. Removes cached SSO tokens from disk (via AWS CLI where applicable).
2. Unsets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` in the current shell.

Usage:

    awsctl logout

---

## 3. Discovery and Status

### `awsctl status`

- **Strategy:** `EXEC`
- **Purpose:** The "Flight Deck" dashboard.

Shows current identity, token expiration time, and active region.

Usage:

    awsctl status

Outputs (typical):

- Organization
- Account ID and alias
- Role
- Region
- SSO token expiry information (if available)

---

### `awsctl list`

- **Strategy:** `EXEC`
- **Purpose:** Explore the hierarchy.

Subcommands:

- List orgs:

      awsctl list orgs

- List accounts (current org):

      awsctl list accounts

- List roles (current account):

      awsctl list roles

Flags:

- `--json` – Output raw JSON for scripting.

---

### `awsctl console`

- **Strategy:** `EXEC`
- **Purpose:** Open the AWS Console in your default browser using the current SSO Start URL.

Usage:

    awsctl console

---

### `awsctl --matrix` (Hidden)

- **Strategy:** `EXEC`
- **Purpose:** Visual "Matrix-style" login simulation.  
  Purely for demonstration or "please wait" screens.

Usage:

    awsctl --matrix

---

## 4. Automation Commands

### `awsctl exec`

- **Strategy:** `EXEC`
- **Purpose:** Run a command in a specific context *without* changing your current shell's environment variables.

Implicit (current context):

- Uses the context last set by `login` or `switch` (stored in `~/.aws/awsctl-context.json`).

Example:

    awsctl exec -- aws s3 ls

Explicit (one-shot):

- Overrides the context for a single command.

Example:

    awsctl exec --account 123456789012 --role ReadOnly -- aws s3 ls

---

### `awsctl env`

- **Strategy:** `EXEC`
- **Purpose:** Output current exports to stdout.  
  Useful for `.env` files or Docker injection.

Usage:

    awsctl env > .env

---

## 5. System and Maintenance

### `awsctl setup`

- **Strategy:** `EXEC`
- **Purpose:** First-time configuration.

Behavior:

- Initializes `~/.awsctl/orgs.yaml`.
- Installs shell wrapper.
- Detects headless mode via `AWSCTL_HEADLESS=1` or `CI=true`.

Usage:

    awsctl setup

---

### `awsctl doctor`

- **Strategy:** `EXEC`
- **Purpose:** Diagnostics.

Checks:

- Shell integration.
- File permissions.
- Registry hydration.
- Plugin load status.
- AWS CLI presence and version.

Usage:

    awsctl doctor

---

### `awsctl cache-clear` (Alias: `refresh`)

- **Strategy:** `EXEC`
- **Purpose:** Forcefully remove the AWS CLI account list cache.  
  Use this if you have been granted access to a new account, but it is not appearing in the list.

Usage:

    awsctl refresh
    # OR
    awsctl cache-clear
