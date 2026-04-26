# file: docs/USER_GUIDE.md
# cloudctl User Guide (v2.8.1)

`cloudctl` is a security-focused helper for AWS IAM Identity Center (SSO).
It allows you to obtain short-lived credentials for your shell without ever storing sensitive keys on your disk.

---

## 1. Installation

The recommended method is `pipx`, which installs the tool in an isolated environment and links the binary to your `PATH`.

### Prerequisites (typical workstation setup)

- AWS CLI v2 installed and configured for IAM Identity Center (SSO).
- A supported shell (bash or zsh).

### Install `cloudctl` pinned to v2.8.1

> pipx install "git+https://github.com/hoad-org/cloudctl.git@v2.8.1"

### Verify installation

> cloudctl --version

You should see a version string containing `2.8.1`.

---

## 2. First-Time Setup

> cloudctl setup

**Pilot Phase Notice:**
During the pilot, `cloudctl` does not contain embedded configuration.
The wizard will pause and ask you to copy the configuration from our internal documentation.

1.  Follow the link printed by the wizard.
2.  Copy the YAML block.
3.  Paste it into `~/.cloudctl/orgs.yaml`.
4.  Confirm to proceed.

The wizard will then:
- Inject the shell wrapper.
- Sync your AWS CLI profiles.

⚠️ **Critical Step:** The setup wizard modifies your shell configuration (`~/.bashrc` or `~/.zshrc`).
You must reload your shell for these changes to take effect:

> source ~/.zshrc
> # or
> source ~/.bashrc

After reloading, `cloudctl` should be a **shell function**, not just a binary.
Confirm with:

> type cloudctl

You should see output similar to:

> cloudctl is a function

If you instead see a path (for example, `/usr/local/bin/cloudctl`), the wrapper is not loaded correctly and `switch` will not update your shell environment.

---

## 3. How cloudctl Works (Execution Wrapper Overview)

At a high level:

- `cloudctl` installs a shell **function** which wraps an internal binary (`_cloudctl_bin`).
- When you run interactive commands (like `cloudctl switch`), the function intercepts the call.
- The function receives a sanitized payload of `export AWS_...` statements.
- It uses `eval` to apply those variables to your **current shell**.

This “Context Bridge” pattern allows `cloudctl` to update your shell environment safely.
**Credentials are held only in memory.**

**CRITICAL SECURITY WARNING (TTY Guard):**
You must **always** run the `cloudctl` function.
Running the underlying binary (`_cloudctl_bin`) directly for `switch` or `exec` commands is **blocked** and will trigger a security error.

---

## 4. Daily Workflow

The typical daily workflow consists of four steps.

### Step 1: Login

Authenticate with your Identity Provider (Okta, Azure AD, etc.):

> cloudctl login --org btavm

This will:

- Open your browser for SSO authentication.
- Store the SSO token in the AWS CLI v2 SSO cache, typically under `~/.aws/sso/cache/`.

Once this token exists, `cloudctl` can obtain short-lived AWS credentials on demand.

---

### Step 2: Switch Context

Select your AWS Account, Role, and Region interactively:

> cloudctl switch

#### 🕒 Smart History

`cloudctl` remembers your last 5 contexts.
They appear at the very top of the list with a clock icon:

> > 🕒 Production (123456789012)
>   🕒 Sandbox (112233445566)
>   --- All Accounts ---
>   Analytics
>   ...

Behind the scenes:

- `cloudctl` consults the central registry (maintained by your platform team) for allowed regions and role ordering.
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

Any tool that respects standard AWS environment variables will run in the context you selected with `cloudctl switch`.

---

### Step 4: Toggle Back (Smart Switching)

Need to jump back to the previous account you were working in?

> cloudctl switch -

This behaves similarly to `cd -` in your shell:
it toggles back to the previously active context (account/role/region).

---

## 5. Advanced Usage

### 5.1 Quick Aliases

Define shortcuts in `~/.cloudctl/orgs.yaml`:

> aliases:
>   prod:
>     org: btavm
>     account: "123456789012"
>     role: ViewOnlyAccess
>     region: eu-west-1

Use them instantly:

> cloudctl switch @prod

### 5.2 Non-Interactive Switching

For scripts or when you know the exact target context, you can bypass the interactive selector:

> cloudctl switch --account 123456789012 --role AdministratorAccess --region us-east-1

Notes:

- All three flags (`--account`, `--role`, `--region`) are typically required for deterministic behavior.
- Guardrails still apply. If the region or role is not allowed, the switch will fail.

### 5.3 Exec (One-Shot Commands)

Run a command in a specific context without altering your current shell environment.

Implicit (use last known context):

> cloudctl exec -- aws s3 ls

Explicit (override context):

> cloudctl exec --account 123456789012 --role ReadOnly --region eu-west-1 -- aws s3 ls

In both cases:

- `cloudctl` obtains credentials for the chosen context.
- It runs the provided command in a subprocess.
- Your existing shell environment remains unchanged after the command completes.

This is useful for:

- One-off diagnostic commands.
- Scripts that should not permanently change the caller’s environment.

### 5.4 Dotfile Export (.env Files)

Generate a `.env` file with the current credentials for use in Docker or other tools.
The output is POSIX export compliant (text, not JSON).

> cloudctl env > .env

You can then use tools that support environment file loading, for example:

> docker compose --env-file .env up

This still benefits from short-lived credentials.

---

## 6. Security Overview (v2.8.1)

`cloudctl` is designed for secure workstation use with AWS IAM Identity Center.

Key properties:

- **No long-term access keys on disk.**
- **Short-lived credentials in memory.**
- **TTY Guard:** Running the binary directly for context commands is blocked for security.
- **Central Guardrails:** Regions and roles are controlled by a central registry.
- **Break Glass Audit:** Sensitive roles trigger a mandatory justification prompt.
- **Namespace Isolation:** Plugins must use approved naming conventions (`cloudctl.plugins.*`) to prevent code injection via config files.

See `docs/SECURITY_APPRAISAL.md` for a deeper security assessment.

---

## 7. Guardrails & Registry Model

`cloudctl` separates policy (admin-controlled) from preference (user-controlled).

### High-Level Model

**Corporate Registry (Policy)**
Lives in the cloudctl source code (or a remote signed HTTPS endpoint).

Defines:
- Organizations (org names such as `btavm`)
- SSO start URLs and SSO regions
- Allowed AWS regions per org
- Preferred role ordering
- Sensitive Roles (triggering Break Glass)
- Plugin Namespace Allowlist (maintained by your platform/security team)

**User Enablement File (Preference)**
Typically: `~/.cloudctl/orgs.yaml`.

- Allows users to declare which orgs are enabled on their machine.
- Does not allow overriding guardrails, start URLs, or SSO regions.

**CRITICAL PLUGIN NOTE:**
If you use custom plugins, ensure they are enabled using the full namespace, for example:

> cloudctl.plugins.okta
> # not just okta

---

## 8. Working with Multiple Orgs

If your company uses multiple AWS organizations, your platform team may configure several org entries in the registry and enable them for you.

**General usage pattern:**

Login to a specific org:

> cloudctl login --org btavm

Switch within that org:

> cloudctl switch

You can repeat the login/switch workflow for another org if your workstation is allowed to access it.

---

## 9. Diagnostics and Debugging

When something goes wrong, start with built-in diagnostics.

### 9.1 Doctor Command

Run:

> cloudctl doctor

Typical checks include:

- Registry availability (can cloudctl see the configured orgs?).
- Basic configuration sanity (e.g., presence of `~/.cloudctl`).
- Environment checks (AWS CLI v2 availability).

Review the output for misconfiguration hints (missing orgs, bad paths, strict policy blocks).

---

## 10. Troubleshooting

### 10.1 “Security Error: Refusing to print credentials to TTY”

**Symptom:** Immediate security error and exit when running a command that exports credentials.

**Cause:**
- The tool detected that you ran the internal binary (`_cloudctl_bin`) directly, or
- An automation script is not properly invoking the `cloudctl` function.

**What to do:**
- Always run the shell function `cloudctl`.
- Never run `_cloudctl_bin` directly for `switch` or `exec`.

---

### 10.2 “Command not found: _cloudctl_bin”

**Symptom:** `command not found: _cloudctl_bin`
**Cause:** The internal binary is not on your PATH.
`pipx` may have installed it into `~/.local/bin`, which is not in your PATH.

**What to do:**

> pipx ensurepath

Then re-open your terminal (or source your shell config).

If needed, reinstall:

> pipx install --force "git+https://github.com/hoad-org/cloudctl.git@v2.8.1"

---

### 10.3 “Switch doesn’t change my variables”

**Symptom:** `cloudctl switch` appears to run, but `env | grep AWS_` shows no updates.

**Cause:**
- The shell wrapper is not loaded, or
- You invoked the underlying binary directly (blocked by TTY Guard).

**What to do:**

> type cloudctl

If it prints `cloudctl is a function`, the wrapper is loaded.
If it prints a path (e.g., `/usr/local/bin/cloudctl`), the wrapper is missing.

Reload your shell config:

> source ~/.zshrc
> # or
> source ~/.bashrc

If it still doesn’t appear, re-run:

> cloudctl setup

and reload.

---

### 10.4 “New account not showing up”

**Symptom:** A newly granted account/role doesn’t appear in the selector.

**Cause:** AWS CLI v2 caches account and role lists.

**What to do:**

> cloudctl refresh

If the account still doesn’t appear:
- Confirm the account/role is granted to your SSO identity.
- Log out of your browser SSO and log back in.

Then run:

> cloudctl login
