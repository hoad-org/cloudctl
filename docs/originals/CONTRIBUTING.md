# Contributing to cloudctl

We welcome contributions from all **BeyondTrust Engineering** teams! Whether you’re adding a new plugin, fixing a bug, or improving documentation, please open a Pull Request (PR) on **GitHub Enterprise**.

All contributions are subject to peer review, CI validation, and security analysis before merging.

---

## 1. Development Environment

### 1.1 Prerequisites

Ensure the following dependencies are installed on your workstation:

- **Python 3.9+** (Required)
- **git**
- **make**
- **AWS CLI v2** (Required for local SSO and STS validation testing)

---

### 1.2 Repository Setup

Clone the repository from the internal GitHub to your local workstation:

```
git clone [https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl.git](https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl.git)
cd cloudctl
```

#### Python Virtual Environment (Recommended)

Set up a virtual environment for isolated development and testing of the Python core logic:

```
python3 -m venv .venv
source .venv/bin/activate
```

#### Installing Development Dependencies

Install all development tools and dependencies:

```
pip install -r requirements-dev.txt
```

---

### ⚠️ CRITICAL ARCHITECTURAL NOTE

`pip install -e .` and `pipx install` are **not supported** for full cloudctl usage.
These methods do **not** install the critical Split-Plane system shim (`/usr/local/bin/cloudctl`) and will cause `switch` and `env` commands to fail.

To test the complete stack (Shim + Python + Shell Integration), always use:

```
make deploy-system
```

This ensures the Bash Shim, shell bridge, and Python runtime coexist in a verified, production-equivalent environment.

---

## 2. Versioning

cloudctl uses **setuptools_scm** for version management.
Versions are automatically derived from annotated Git tags that follow the `v*` naming convention.

### Always Sync Tags Before Work

```
git fetch --tags
```

### Tagging Conventions

| Tag | Type | Example |
|-----|------|----------|
| **v2.8.2** | Patch / Security Fix | Backward-compatible fixes |
| **v2.9.0** | Minor Feature | Adds features or improvements |
| **v3.0.0** | Major | Introduces breaking changes |

> ⚠️ **Do not hardcode version strings** into any code files (e.g., `__init__.py`).
> Let `setuptools_scm` derive them dynamically from Git metadata at build time.

---

## 3. Tests and Quality Gates

All changes must pass the automated **CI pipeline**, which includes unit, integration, and security scanning.
Merges to `main` are blocked automatically if any tests fail.

### 3.1 Testing Matrix

| Environment | OS | Shells Tested | Focus |
|--------------|----|----------------|--------|
| **POSIX** | Linux, macOS | Bash, Zsh | Core logic, TTY guards, eval safety, shim routing |
| **Experimental** | Linux | Fish | Non-traditional shells and manual wrapper testing |
| **Cross-Platform** | Windows (Native) | Python | Path handling, dependency isolation, portability |

### 3.2 Running Tests

Execute the tests and security checks locally before committing:

```
# Run core test suite
make test

# Run security audits (Bandit + pip-audit)
make security
```

### 3.3 Multi-Python Testing

If you have multiple Python versions installed, test compatibility with tox:

```
tox
```

---

## 4. Code Style and Linting

We maintain strict style and quality standards using static analysis and formatting tools.

- **black** — Code formatting
- **ruff** — Linting and import organization
- **mypy** — Static type checking with strict mode enabled

### Local Quality Commands

```
# Auto-format code (black)
make format

# Lint and typecheck (non-destructive)
make lint
make typecheck
```

### Pull Request Quality Checklist

Before submitting your PR, confirm:

- `make format` runs clean.
- `make lint`, `make typecheck`, and `make test` pass with zero warnings or errors.
- All functions and docstrings follow established naming and parameter conventions.

---

## 5. Security-Sensitive Areas

Modifications affecting security-critical sections require explicit review by a designated **Security Champion**.

### High-Sensitivity Modules

| Path | Description |
|------|-------------|
| `src/cloudctl/guardrails.py` | Policy enforcement and behavioral gating |
| `src/cloudctl/registry.py` | Trust anchors and remote registry hydration logic |
| `src/cloudctl/plugins/*` | Plugin sandbox enforcement and dynamic extension management |
| `src/cloudctl/shell.py` | Evaluation bridge and input/environment hygiene |
| `src/cloudctl/config.py` | Local configuration loading and persistence controls |

### Security Contributions Requirements

- Add or update **unit and integration tests** in `tests/` covering the security edge cases introduced by the change.
- Ensure **no new Bandit warnings** are introduced in the modified area.
- Verify and, if necessary, update **`docs/SECURITY_APPRAISAL.md`** to reflect the revised security posture or logic.

PRs modifying any of the above files will be blocked by CI until approved by a reviewer from the **Security Champion group**.

---

## 6. Release Process

Releases are managed under strict governance and require elevated privileges.

Do **not** attempt to cut, tag, or push official release versions unless explicitly authorized under the **Release Maintainers** group.

For the authoritative and auditable release procedure, refer to **[`RELEASE.md`](RELEASE.md)**.

---

## 7. AI Code Generation & Policy Compliance

While portions of this repository have been refined using AI-based assistance tools, integrity and accountability remain strictly human-governed.
To maintain security, compliance, and transparency, the following rules apply to **all contributors**:

### 7.1 Human Review Required
If you use AI outputs for refactoring or code suggestions:
- Review and understand **every line** before submission.
- You are personally responsible for all merged code.

### 7.2 No Secrets
- Never include internal secrets, service keys, customer data, or PII in any AI prompt.
- AI tools used must comply with corporate data protection and confidentiality policy.

### 7.3 Sanitization Standards
When using AI tools for debugging, documentation, or architecture diagrams:
- Replace real URLs or hostnames with placeholders (`example.com`).
- Avoid revealing private infrastructure identifiers.
- Treat AI models as **untrusted third-party services** unless explicitly approved.

---

## 📄 License

**MIT License**
See the `LICENSE` file for full license text and usage terms.

All intellectual property rights for `cloudctl` and its components remain with **BeyondTrust Engineering**.
```
