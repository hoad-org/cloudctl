# file: docs/DEVELOPER_ONBOARDING_AND_INTERNAL_ARCHITECTURE.md
# Developer Onboarding & Internal Architecture

**Target Audience:** Maintainers, Contributors, and Platform Engineers inheriting `cloudctl`.
**Version:** v2.8.1

---

## 1. Architecture Overview

`cloudctl` is not a standard CLI tool; it is a **shell-integrated identity broker**.
It bridges the gap between Python (where logic lives) and the Shell (where credentials must be exported).

### 1.1 The "Context Bridge" Pattern
Standard CLIs cannot modify the parent shell's environment variables.
`cloudctl` solves this using a **function wrapper** + **evaluation strategy**:

1.  **Wrapper (`cloudctl` function):** Intercepts user commands.
2.  **Binary (`_cloudctl_bin`):** Calculates the state change.
3.  **Strategy Output:** The binary emits a "Strategy" line (`EXEC` or `EVAL`).
4.  **Execution:**
    * `EXEC`: The binary runs a subprocess (e.g., `status`, `login`).
    * `EVAL`: The binary outputs `export VAR=VAL` commands, which the wrapper `eval`s.

### 1.2 Module Breakdown

| Module | Responsibility | Key Security Control |
| :--- | :--- | :--- |
| `cloudctl.cli` | Entry point & Dispatch | Global Exception Handler (Redaction) |
| `cloudctl.core` | Orchestration (Login/Switch) | Token verification |
| `cloudctl.use_exports` | AWS CLI Subprocess Calls | **TTY Guard** (Prevents leaks) |
| `cloudctl.registry` | Policy Definitions | **Pinned Trust Anchor** (Tier 3) |
| `cloudctl.shell` | Wrapper Injection | Fail-closed logic |
| `cloudctl.plugins` | Extension Runner | Namespace isolation & Timeouts |

---

## 2. State Management

`cloudctl` is effectively stateless, relying on the ecosystem for persistence.

* **Identity:** `~/.aws/sso/cache/*.json` (Managed by AWS CLI v2).
* **Context:** `~/.aws/cloudctl-context.json` (Stores current selection for "Smart History").
* **Config:** `~/.cloudctl/orgs.yaml` (User enablement preference & **Manual Definitions** during Pilot).
* **Policy:** **Immutable.** Hardcoded in `registry.py` (Placeholder) or loaded from signed Remote Registry.

---

## 3. Development Workflow

### 3.1 Prerequisites
* Python 3.9+
* `make`
* `pre-commit`

#### 🔐 Corporate Proxy / SSL Setup
If you are behind a corporate proxy (Zscaler, Netskope), Python tools like `pip`, `requests`, and `pip-audit` will fail with SSL errors.
You **must** configure Python to trust your system certificates by exporting them from all keychains:

**macOS:**

> rm ~/macos_certs.pem
> security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain >> ~/macos_certs.pem
> security find-certificate -a -p /Library/Keychains/System.keychain >> ~/macos_certs.pem
> security find-certificate -a -p "$HOME/Library/Keychains/login.keychain-db" >> ~/macos_certs.pem
>
> export REQUESTS_CA_BUNDLE="$HOME/macos_certs.pem"

**Add the `export` line to your `~/.zshrc` to make it permanent.**

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
We enforce a **strict >75% coverage floor**.

* **Unit Tests (`tests/`):** Validate logic in isolation.
* **Integration (`tests/test_integration_full.py`):** "God Mode" mock of AWS CLI and File System.
* **Smoke Test (`tools/comprehensive_smoke.sh`):** A Bash script that creates a fake `_cloudctl_bin` environment to validate the shell wrapper logic and `eval` behavior.

---

## 4. Release Process

Releases are automated via GitHub Actions (`.github/workflows/release.yaml`).

1.  **Verify:** Ensure `make test` and `make security` pass locally.
2.  **Tag:** Create a semantic version tag (e.g., `v2.8.1`).

    > git tag -a v2.8.1 -m "Fix: handled edge case X"
    > git push origin v2.8.1

3.  **Build:** GitHub Actions builds the wheel and sdist.
4.  **Publish:** Artifacts are attached to the GitHub Release. **We do not publish to PyPI public index.**

---

## 5. Security & Maintenance Responsibilities

### 5.1 Registry Updates
Guardrails are defined in the central registry. The update process depends on the operational phase:

**Pilot Phase (Manual Mode):**
1.  Update the **Internal Confluence Page** with new Org details or Guardrails.
2.  Notify users to re-copy the configuration block into `~/.cloudctl/orgs.yaml`.

**Future State (Tier 3 - Automated):**
1.  Edit `registry.json` in the `cloudctl-registry` repo.
2.  Merge to `main` (triggers Signing & S3 Upload).
3.  Clients update automatically on next run.

### 5.2 Signing Key Rotation (Tier 3)
If the Remote Registry private key is compromised:
1.  Generate new Minisign keys.
2.  Update `_TRUSTED_ROOT_KEY` in `src/cloudctl/registry.py`.
3.  Release a critical patch (`v2.x.x`).
4.  The new client will reject old signatures immediately.

### 5.3 Dependency Audits
`pip-audit` runs on every CI build.
* **Alert:** If a CVE is found, update `pyproject.toml` immediately.
* **Lock:** We use `urllib3>=2.2.2` to mitigate specific known vulnerabilities.
