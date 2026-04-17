# awsctl v3.1.0 — Enterprise Cloud Identity & Context Manager

[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/1/badge)](https://bestpractices.coreinfrastructure.org/projects/1)
[![SLSA Aligned](https://slsa.dev/images/gh-badge-level2.svg)](https://slsa.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: Zero Trust](https://img.shields.io/badge/Security-Zero%20Trust-blueviolet)](docs/originals/SECURITY.md)
[![NIST 800-53](https://img.shields.io/badge/NIST_800--53-Compliant-blue?style=flat&logo=nist)](docs/originals/SECURITY_APPRAISAL.md)
[![FedRAMP Supporting](https://img.shields.io/badge/FedRAMP-Ready-005288?style=flat&logo=files)](docs/originals/SECURITY_APPRAISAL.md)
[![GovCloud Compatible](https://img.shields.io/badge/AWS_GovCloud-Compatible-232F3E?style=flat&logo=amazon-aws)](docs/originals/USER_GUIDE.md)
[![FIPS 140-3 Compatible](https://img.shields.io/badge/FIPS_140--3-Compatible-green?style=flat&logo=openssl)](docs/originals/SECURITY.md)

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
- **TTY Guard:** Warns and requires explicit opt-in when `--eval` is used outside the validated shell wrapper context.
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

Clones the repo and calls `install.sh`, which downloads the wheel from GitHub Releases
when `GITHUB_TOKEN` is set, then injects the shell wrapper.

```bash
export GITHUB_TOKEN=ghp_your_token_here

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl
bash install.sh
```

`install.sh` downloads the latest release wheel from GitHub Releases, installs it,
adds the user Scripts directory to PATH for the session, and injects the shell wrapper (bash/zsh/fish).

---

### Option C: Windows (PowerShell / pwsh)

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"

git clone https://github.com/BT-IT-Infrastructure-CloudOps/aws-terraform-infra-cloudops-awsctl.git
cd aws-terraform-infra-cloudops-awsctl
.\install.ps1
```

Downloads the latest release wheel from GitHub Releases and injects the PowerShell function wrapper into `$PROFILE`.

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

`awsctl upgrade` queries the GitHub Releases API, downloads the latest wheel, and installs it via pip.

---

### Upgrading via Artifactory (internal PyPI)

Once your team has access to the JFrog Artifactory instance, you can upgrade without a GitHub token:

```bash
# Set once (add to ~/.zshrc / ~/.bashrc to persist)
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/awsctl-pypi/simple/

# Then upgrade like any pip package
awsctl upgrade

# Or pass the URL inline
awsctl upgrade --index-url https://your-org.jfrog.io/artifactory/api/pypi/awsctl-pypi/simple/
```

`install.sh` also reads `AWSCTL_INDEX_URL` for fresh installs:

```bash
export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/awsctl-pypi/simple/
bash install.sh
```

Publishing to Artifactory (maintainers only):

```bash
export ARTIFACTORY_URL=https://your-org.jfrog.io/artifactory/api/pypi/awsctl-pypi/
export ARTIFACTORY_TOKEN=<your-identity-token>
make publish-artifactory
```

---

### Uninstall

```bash
# Interactive — prompts before removing anything
awsctl uninstall

# Preview what would be removed without changing anything
awsctl uninstall --dry-run

# Remove only the package, leave shell integration intact
awsctl uninstall --package-only

# Remove everything but keep ~/.config/awsctl/ (context, config)
awsctl uninstall --keep-config
```

Or use the shell scripts directly:

```bash
bash uninstall.sh   # macOS / Linux / WSL
.\uninstall.ps1     # Windows PowerShell
```

---

## 💻 Command Reference

### Authentication

```bash
awsctl login <org>          # Authenticate (SSO / az login / gcloud auth login)
awsctl login bt-avm --force # Force re-authentication even if token is still valid
awsctl logout               # Clear active session and unset all credential env vars
```

### Context switching

```bash
awsctl switch               # Interactive picker: org → account → role → region
awsctl switch bt-avm        # Skip org picker, go straight to account/role selection
awsctl switch bt-avm --account 111111111111 --role AdminAccess --region us-east-1
awsctl switch @prod         # Restore a named alias (configured in orgs.yaml)
awsctl switch -             # Switch back to the previous context (like cd -)
awsctl use bt-avm           # Alias for switch
```

### Credential injection (without changing shell context)

```bash
# Run any command with fresh credentials for a specific org
awsctl exec --org bt-avm -- terraform plan
awsctl exec --org fdr-gvc --account 222222222222 --role ReadOnly -- aws s3 ls

# Without --org, uses active context
awsctl exec -- aws sts get-caller-identity
```

### Status and identity

```bash
awsctl status               # Show active context: org, account, role, region, expiry
awsctl env                  # Alias for status
awsctl whoami               # Show caller identity via STS (AWS) or provider CLI
```

### Background credential refresh

```bash
# Keep credentials alive in a dedicated terminal pane
awsctl watch                # Watch active context, refresh 15 min before expiry
awsctl watch bt-avm         # Watch a specific org
awsctl watch --interval 30  # Check every 30 seconds instead of 60
awsctl watch --threshold 1800  # Refresh when 30 minutes remain (instead of 15)
awsctl watch --once         # Check once and exit (useful for CI health checks)
```

### Shell prompt integration

```bash
# Print current context for PS1 (outputs nothing when no context active)
awsctl prompt               # ☁ bt-avm (111111111111/AdminAccess/us-east-1)
awsctl prompt --short       # ☁ bt-avm
awsctl prompt --json        # {"provider":"aws","org":"bt-avm","account":"..."}
awsctl prompt --warn-expiry 30  # Show ⚠ when < 30 minutes remain

# Get a ready-to-paste snippet for your prompt tool
awsctl prompt --starship    # Prints ~/.config/starship.toml fragment
awsctl prompt --p10k        # Prints ~/.p10k.zsh segment function

# Add to .zshrc/.bashrc (minimal, no extra dependencies)
PS1='$(awsctl prompt --short 2>/dev/null) '"$PS1"
```

### Configuration management

```bash
awsctl init                 # Full interactive setup wizard
awsctl init --shell-only    # Inject shell wrapper only (no org wizard)
awsctl org add              # Add a new org interactively
awsctl org list             # List all configured orgs
awsctl org remove <name>    # Remove an org from config
awsctl accounts <org>       # List accessible accounts/subscriptions/projects
```

### Shell tab completion

```bash
# Print activation instructions for your shell
awsctl completion           # Auto-detects bash/zsh/fish
awsctl completion --shell zsh
awsctl completion --install # Write activation line to your shell profile automatically
```

After setup, restart your shell and press Tab after any `awsctl` subcommand.

### Maintenance

```bash
awsctl doctor               # Full system health check (tools, shell, permissions, network)
awsctl doctor --fix-path    # Also attempt to repair missing PATH entries
awsctl upgrade              # Upgrade to latest release (GitHub or Artifactory)
awsctl upgrade --index-url <url>   # Upgrade from a specific Artifactory index
awsctl open                 # Open the cloud console for the active org in your browser
```

---

## ❓ FAQ (Frequently Asked Questions)

### 🔑 Token Length & Expiry
**Q:** How long do my credentials last?
**A:** By default, awsctl requests 12-hour session tokens, aligned with AWS Identity Center defaults.

---

### 🛡️ Preventing Authentication Exposure
**In-Memory Enforcement:** Credentials are never persisted to disk.
**TTY Guard:** Warns and requires explicit opt-in when credentials are requested outside the validated shell wrapper context.
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

## 📜 Changelog (v3.1.0)

### New commands
- **FEATURE:** `awsctl prompt` — compact cloud context string for PS1, Starship, and Powerlevel10k. Supports `--short`, `--json`, `--starship`, `--p10k`, `--no-icon`, `--warn-expiry`. Silent when no context is active.
- **FEATURE:** `awsctl watch` — background credential refresh loop; re-authenticates when token falls below `--threshold` (default 15 min). Works for AWS, Azure, and GCP. Supports `--interval`, `--threshold`, `--once`.
- **FEATURE:** `awsctl switch -` — restore the previous context instantly (analogous to `cd -`).
- **FEATURE:** `awsctl exec --org` — run a command with credentials for a specific org without changing the active shell context. Interactive account/role picker when `--account`/`--role` are omitted.
- **FEATURE:** `awsctl env` — alias for `awsctl status`.
- **FEATURE:** `awsctl completion` — print shell tab-completion activation snippet for bash/zsh/fish. `--install` writes the activation line to your shell profile automatically.
- **FEATURE:** `awsctl uninstall` — guided uninstaller with `--dry-run`, `--keep-config`, and `--package-only` flags. Correctly removes the multi-line shell wrapper function from all detected profiles.

### Artifactory support
- **FEATURE:** `awsctl upgrade --index-url <url>` — upgrade from a JFrog Artifactory PyPI repo instead of GitHub Releases. Also reads `AWSCTL_INDEX_URL` env var. Uses `pipx runpip` for isolated-venv installs.
- **FEATURE:** `install.sh` reads `AWSCTL_INDEX_URL` for fresh installs from Artifactory.
- **FEATURE:** `.github/workflows/publish-artifactory.yaml` — manual/tag-triggered workflow to publish the wheel to Artifactory (guarded by `ARTIFACTORY_CONFIGURED` repo variable until access is provisioned).
- **FEATURE:** `make build` and `make publish-artifactory` Makefile targets.
- **CHORE:** `pyproject.toml` — commented `[[tool.poetry.source]]` block ready to uncomment once Artifactory URL is known.

### Provider improvements
- **FEATURE:** `get_token_expiry()` added to `CloudProvider` base class. Azure overrides it via `az account get-access-token` (real expiry). GCP overrides it to return `now + 1h` (tokens are exactly 1hr; gcloud auto-refreshes). AWS uses existing `expiresAt` on the SSO token object.
- **FIX:** `awsctl watch` now supports Azure and GCP with real expiry data, not just "expiry unknown".

### Install / setup
- **FEATURE:** `install.sh` — pipx-first install (PEP 668 safe), falls back to pip with `--break-system-packages` when supported. WSL browser guidance for SSO flows. `AWSCTL_INDEX_URL` support.
- **FEATURE:** `awsctl init` wizard now shows inline field guidance (where to find SSO URL, Tenant ID, Project ID) directly in the prompts.

### Bug fixes
- **FIX:** `awsctl switch -` routing — `cmd_switch` was checking `args.target` but the parser stored the arg as `args.org`; switch-back never triggered.
- **FIX:** `awsctl exec --org` routing — `cmd_exec` dispatched to the old handler that ignored `exec_org`/`exec_account`; now delegates to `ExecCommand`.
- **FIX:** `awsctl env` subparser was missing from `_build_parser()`; argparse would reject the command.
- **FIX:** `awsctl doctor` NTP check — `socket.create_connection("pool.ntp.org", 123)` hangs indefinitely on corporate networks with port 123 filtered. Replaced with `concurrent.futures` + `time.cloudflare.com:443` with a 3-second hard timeout.
- **FIX:** Shell wrapper — previously passed `--eval` to ALL commands; `doctor` output was sourced as shell code. Wrapper now only eval-sources `switch`/`use`/`logout`; all other commands stream directly.
- **FIX:** `awsctl uninstall` shell profile removal — previous implementation only removed the marker line and `awsctl() {` header, leaving the full function body. Replaced with `_remove_awsctl_blocks()`: index-based algorithm that correctly handles multi-line function blocks and single-line eval commands.
- **FIX:** `awsctl upgrade` Artifactory pipx path — `pipx upgrade --pip-args` does not reliably pass index URL; replaced with `pipx runpip awsctl install --upgrade`.
- **CHORE:** Deleted dead `commands/switch.py::SwitchCommand` (never dispatched; `cmd_switch` in `cli.py` is the real implementation).

### Quality
- **TEST:** 89 new tests covering: `awsctl prompt`, `awsctl watch`, `awsctl switch -`, `awsctl exec --org`, token expiry display, `_remove_awsctl_blocks`, `awsctl completion`, `awsctl uninstall`. Total: **431 tests passing**.
- **CHORE:** `argcomplete>=3.0` added as dependency; `_build_parser()` registers completions automatically.

---

## 📜 Changelog (v3.0.4)

- **FIX (security):** Registry signature verification was bypassed — `fetch_registry()` now passes `PUB_KEY` to `fetch_remote_registry()` (previously called without it, silently skipping Minisign validation).
- **FIX:** Shell wrapper (`AWSCTL_WRAPPER`) now propagates `source` exit code — previously a failed `source` was masked by the `--eval` exit code.
- **FIX:** `context_manager.py` now uses atomic `mkstemp + os.replace()` write — eliminates race condition where concurrent readers could see a partial file.
- **FIX:** `install.ps1` now validates Python ≥ 3.12 before installing (matching `install.sh` behaviour).
- **FIX:** CI `pip-audit` step no longer suppresses `poetry export` errors with `2>/dev/null` — failures now surface correctly.
- **CHORE:** Gitleaks updated from 8.18.4 → 8.30.1 with SHA256 checksum verification in CI.
- **TEST:** Added 3 missing tests: `shlex.quote` metacharacter injection, Azure RBAC fallback warning visibility, and audit log 0600 permission assertion.

---

## 📜 Changelog (v3.0.3)

- **FIX:** README badge links corrected from `docs/SECURITY.md` → `docs/originals/SECURITY.md`.
- **CHORE:** `help_text.py` dead stub replaced with backwards-compat docstring.

---

## 📜 Changelog (v3.0.2)

- **FIX (security):** All shell-exported credential variables now sanitized with `shlex.quote()` in both `use_exports.py` (AWS legacy path) and `providers/base.py` (Azure/GCP path).
- **FIX:** Audit log (`~/.awsctl/audit.log`) created with explicit `0600` permissions.
- **FIX:** `cmd_exec` no longer misreports clean `SystemExit(0)` from nested providers as a credential failure.
- **FIX:** Azure RBAC query failure now shows a visible warning when falling back to `Contributor` default.
- **FIX:** `awsctl switch` with no configured orgs now mentions `awsctl org add` as an option.
- **FIX:** `pip install` subprocess in `awsctl upgrade` now has a 300-second timeout.
- **CHORE:** `pyproject.toml` — added PyPI classifiers and URLs.
- **CHORE:** GitHub community files added: `CONTRIBUTING.md`, `PULL_REQUEST_TEMPLATE.md`, issue templates.
- **CHORE:** `CODEOWNERS` extended to cover all security-sensitive source paths.

---

## 📜 Changelog (v3.0.1)

- **FIX:** `install.sh` now validates Python ≥ 3.12 before proceeding; emits a clear error with install guidance if the system `pip3` resolves to Python 3.9.
- **FIX:** `uninstall.sh` now removes legacy v2.x shell wrapper formats (`# AWSCTL SHELL INTEGRATION (v2.2-SECURE)`) and stale venv PATH entries that the v3 remover did not match.

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

### ✅ Validation Summary (v3.1.0)

- ✅ **431 unit tests passing** (doctor, shell, wizard, providers, CLI, prompt, watch, exec --org, switch -, completion, uninstall)
- ✅ Python 3.12, 3.13, 3.14 tested in CI matrix
- ✅ Cross-platform: macOS (zsh/bash/fish), Linux (bash/zsh/fish), Windows (PowerShell/pwsh), WSL2
- ✅ Static analysis: Bandit, `pip-audit`, ruff, black, Gitleaks all passing
- ✅ 0 known CVEs in dependency lockfile (`pip-audit`)
- ✅ CI/CD: tag-driven GitHub Releases + Artifactory publish workflow ready
