# Troubleshooting Guide

This guide provides solutions for common issues encountered when using `awsctl`.  
All troubleshooting steps reflect the Registry-backed Hydration Model and the actual CLI behavior implemented in `src/awsctl`.

---

## 1. Common Errors

### 1.1 `awsctl: command not found`

**Cause:**  
The `_awsctl_bin` binary is not in your `PATH`, or `pipx` has not finished linking it.

**Fix:**

Verify the binary location:

    ls ~/.local/bin/_awsctl_bin

If missing, reinstall:

    pipx install --force "git+https://github.com/your-org/awsctl.git@v2.0.0"

---

### 1.2 `Token does not exist` / `Expired SSO token`

**Cause:**  
Your AWS SSO token has expired (typically after 8–12 hours, depending on corporate policy).

**Fix:**

    awsctl login --org <your-org>
    awsctl switch

Note:  
The AWS CLI SSO token cache is located at `~/.aws/sso/cache/`.  
`awsctl` does not store or manage these tokens directly.

---

### 1.3 `Region not allowed` or other guardrail errors

**Cause:**  
You are attempting to select a region that is not permitted by your organization’s Registry definition in `src/awsctl/registry.py`.

Example error:

    ERROR: region us-east-1 is not permitted for org 'production'
    exit code: 1

**Fix:**

Check diagnostics:

    awsctl doctor

If you require an additional region, contact your platform/security team.

Notes:

- Guardrails are defined centrally in `registry.py`.
- Local overrides in `orgs.yaml` are ignored.

---

### 1.4 Unexpected roles missing from role selector

**Cause:**

Your organization’s Registry defines `preferred_roles`, which appear at the top of the list.  
Other roles are still present but appear lower, sorted alphabetically.

**Fix:**

- Scroll further down in the interactive list.
- Use type-to-search to filter by role name.

---

### 1.5 Plugin failures (VPN, Okta, MFA, posture checks)

You may see errors such as:

    ✗ VPN connection NOT detected.
    ✗ Okta session expired — please sign in.

**Cause:**  
A mandatory plugin defined in the Registry has failed.  
Enforced plugins cannot be disabled or bypassed by users.

**Fix:**

- Ensure VPN is connected (if required).
- Ensure MFA / Okta / IdP session is valid.
- Check network reachability (proxies, firewalls, DNS).

Then re-run:

    awsctl login --org <your-org>

If the problem persists, contact your platform/security team with the exact error message.

---

### 1.6 `syntax error` or exports not applying

**Cause:**  
The `awsctl` shell wrapper tried to `eval` output that contained error messages (plain text) instead of `export` commands.  
This typically occurs when:

- A plugin fails.
- Network timeouts or AWS errors occur.

**Fix:**

Run the underlying binary directly to inspect raw output without shell wrapper interference:

    _awsctl_bin switch

Read and resolve the error shown (for example, region not allowed, plugin failure), then retry:

    awsctl switch

---

### 1.7 Context switching appears to do nothing

**Cause:**

- You executed `awsctl switch` inside a subshell (for example, within `./myscript.sh`), or
- The shell wrapper is not loaded.

**Fix 1: Verify wrapper**

    type awsctl

It should say `awsctl is a function`.  
If not, reload your shell rc file, for example:

    source ~/.zshrc
    # or
    source ~/.bashrc

**Fix 2: Sourcing scripts**

Environment variable changes made in a child process do **not** propagate back to the parent shell.

Wrong (subshell):

    ./myscript.sh

Right (same shell):

    source myscript.sh

---

## 2. Installation Issues

### 2.1 `pipx install` fails due to missing `git`

**Cause:**  
Installing from a GitHub URL requires `git` to be installed.

**Fix:**

Install `git` via your OS package manager and retry:

    # macOS (Homebrew)
    brew install git

    # Debian/Ubuntu
    sudo apt update && sudo apt install -y git

    # Then:
    pipx install "git+https://github.com/your-org/awsctl.git@v2.0.0"

---

### 2.2 `pipx upgrade` doesn’t update the tool

**Cause:**

- Your installed version is pinned to a specific tag URL, or
- You want to move to a newer tagged release.

**Fix:**

Reinstall with the desired tag:

    pipx install --force "git+https://github.com/your-org/awsctl.git@v2.0.0"

Confirm the version:

    awsctl --version

---

## 3. Org and Registry Issues

### 3.1 `Unknown org: <name>`

**Cause:**

- The org exists in your user config (`orgs.yaml`) but not in the Registry (`src/awsctl/registry.py`), or
- There is a typo in the org name.

**Fix:**

- Check your `~/.awsctl/orgs.yaml` for typos.
- If the name is correct, ask your platform team to add the org to `KNOWN_ORGS` in `src/awsctl/registry.py`.

After the new version is released, upgrade:

    pipx upgrade awsctl

---

### 3.2 New org added but not visible in the wizard

**Cause:**

- Your client is on an older version, or
- You have not re-run the setup wizard since the Registry was updated.

**Fix:**

Upgrade:

    pipx upgrade awsctl

Re-run the wizard:

    awsctl setup

Select the new org in the interactive list.

---

## 4. Shell Integration Issues

### 4.1 Using Fish or PowerShell

`awsctl` outputs POSIX-style `export VAR=VALUE` lines.

- **Fish:** Requires a wrapper function to translate exports.
- **PowerShell:** Currently requires WSL2.

PowerShell-native export support is planned but not yet implemented.

**Fix (Fish, high-level):**

- Ensure the function is defined in `~/.config/fish/functions/awsctl.fish`.
- See `docs/SHELL_INTEGRATION.md` for a full example.

**Fix (PowerShell):**

- Use a WSL2 Ubuntu shell for `awsctl` until native support is available.

---

## 5. AWS Identity Center / SSO Issues

### 5.1 Browser login window doesn’t open

**Fix:**

Test the underlying AWS CLI command directly:

    aws sso login --profile sso-<your-org>

If this also fails:

- Check that AWS CLI v2 is installed and on your `PATH`.
- Verify that `~/.aws/config` contains the correct SSO profile for your org.
- Ensure your default browser can be launched from the terminal.

---

### 5.2 Cannot re-authenticate after account / role changes

**Cause:**  
Stale SSO token cache or changed IdP setup.

**Fix:**

Clear the local SSO cache and re-login:

    awsctl cache-clear
    awsctl login --org <org>
    awsctl switch

---

## 6. Diagnostic Tools

### 6.1 `awsctl doctor`

**Purpose:**  
Runs a built-in diagnostic covering:

- AWS CLI v2 availability and version.
- SSO token presence / basic health.
- Config file existence and permissions (`~/.awsctl` and `orgs.yaml`).
- Registry hydration and guardrail status.
- Plugin load success/failure.
- Shell integration detection hints.

**Usage:**

    awsctl doctor

Review the output for red ❌ markers indicating misconfigurations or policy blocks.

---

### 6.2 `awsctl status`

**Purpose:**  
Displays your current context:

- Organization.
- Account ID / alias.
- Role.
- Region.
- SSO token status (if available).

**Usage:**

    awsctl status

Use this to confirm that your session matches the environment you intend to work in (for example, engineering vs production).

---

## 7. Summary

`awsctl` is designed to fail **securely**, not silently.  
Most operational issues fall into four categories:

1. SSO token expiry (requires `awsctl login`).
2. Region guardrails (Registry-enforced, cannot be overridden locally).
3. Plugin posture failures (VPN / Okta / device compliance checks).
4. Shell integration problems (`awsctl` function not loaded).

Use:

- `awsctl doctor` for environment and policy diagnostics.
- `awsctl status` to verify current AWS identity and context.
- `_awsctl_bin switch` (direct binary call) to debug evaluation errors.

For persistent or unexplained failures, capture the exact error message and share it with your platform or security team along with the output of:

    awsctl doctor
    awsctl status
