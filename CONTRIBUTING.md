# file: CONTRIBUTING.md
# Contributing to awsctl

Thank you for considering a contribution to `awsctl`.
This project is intended to be production-grade, security-conscious, and pleasant to work with.

---

## 1. Development Environment

### 1.1 Prerequisites

- Python **3.9+**
- `git`
- `make`
- AWS CLI v2 (for local testing of login flows)

### 1.2 Setup

    git clone https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git
    cd awsctl

    # Create and activate a virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # Install awsctl in editable mode with dev dependencies
    pip install -e ".[dev]"

---

## 2. Versioning

`awsctl` uses `setuptools_scm` for versioning.
The version is derived automatically from Git tags.

Always fetch tags:

    git fetch --tags

Releases are tagged in the form:

- `v2.7.0`
- `v2.2.1`

Do not hard-code the version string in the code – let `setuptools_scm` handle it.

---

## 3. Tests and Quality Gates

We aim for high confidence in behavior across platforms.

### 3.1 The Testing Matrix

We run a comprehensive matrix to validate shell-specific security and compatibility:

| Environment | OS | Shells Tested | Focus |
| :--- | :--- | :--- | :--- |
| **POSIX** | Linux, macOS | Bash, Zsh, Fish | Core logic, TTY guards, `eval` fidelity |
| **Cross-Platform** | **Windows** | **PowerShell/Python** | `os.path` stability, dependency isolation |

### 3.2 Running Tests

    # Run unit tests
    make test

    # Run security audit (Bandit + Pip-audit)
    make security

### 3.3 Multi-Python Testing

    tox

---

## 4. Code Style and Linting

We use:

- `black` for formatting.
- `ruff` for linting and import sorting.

    # Auto-format code
    make format

    # Lint (read-only)
    make lint

Before submitting a PR, make sure:

- `make format` produces no changes.
- `make lint`, `make typecheck`, and `make test` all pass.

---

## 5. Security-Sensitive Areas

Extra care should be taken when editing:

- `src/awsctl/guardrails.py`
- `src/awsctl/registry.py`
- `src/awsctl/plugins/*`
- `src/awsctl/shell.py`
- `src/awsctl/config.py`

If your change touches these:

- Add or update tests under `tests/`.
- Ensure no new `bandit` warnings are introduced.
- Verify `docs/SECURITY_APPRAISAL.md` remains accurate.

---

## 6. Release Process (High Level)

1. Ensure `main` is green in CI (tests, lint, security scans).
2. Tag the release:

       git tag -a v2.7.0 -m "awsctl 2.7.0"
       git push origin v2.7.0

3. CI will build and publish artifacts as configured.
