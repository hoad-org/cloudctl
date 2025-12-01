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

    git clone https://github.com/your-org/awsctl.git
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

- `v2.0.0`
- `v2.0.1`
- `v2.1.0` (minor feature release)

Do not hard-code the version string in the code – let `setuptools_scm` handle it.

---

## 3. Tests and Quality Gates

We aim for high confidence in behavior across platforms.

### 3.1 Running Tests

    # Run unit tests
    make test

    # Or run pytest directly
    pytest

    # Run a single test file
    pytest tests/test_cli.py

### 3.2 Multi-Python Testing

If you have multiple Python versions available:

    tox

This will execute the test suite across the configured environments (for example, `py39`, `py310`, `py311`).

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
- `make lint` and `make test` both pass.

---

## 5. Adding Dependencies

All dependencies are declared in `pyproject.toml`.

- Runtime dependencies → `project.dependencies`
- Dev/Test dependencies → `project.optional-dependencies.dev`

Steps:

1. Add the package to the appropriate section.
2. Run `pip install -e ".[dev]"` again to sync your environment.
3. Update any relevant docs if the dependency changes user-visible behavior.

---

## 6. Pull Request Checklist

Before opening a PR:

- Code is formatted (`make format`).
- Linting passes (`make lint`).
- Tests pass locally (`make test` / `tox` where applicable).
- New functionality is covered by tests.
- Any user-visible changes are reflected in:
  - `README.md`
  - Relevant `docs/*.md`
- Security-relevant changes (auth flows, plugins, guardrails) are called out in the PR description.

---

## 7. Security-Sensitive Areas

Extra care should be taken when editing:

- `src/awsctl/guardrails.py`
- `src/awsctl/registry.py`
- `src/awsctl/plugins/*`
- `src/awsctl/shell.py`
- `src/awsctl/config.py`

If your change touches these:

- Add or update tests under `tests/` to prove behavior.
- Update:
  - `docs/GUARDRAILS.md`
  - `docs/SECURITY_APPRAISAL.md`
  - `docs/ADMIN_GUIDE.md` (if Registry semantics change)

---

## 8. Release Process (High Level)

1. Ensure `main` is green in CI (tests, lint, security scans).
2. Update any release notes / changelog (if used).
3. Tag the release:

       git tag -a v2.0.0 -m "awsctl 2.0.0"
       git push origin v2.0.0

4. CI will build and publish artifacts as configured.
5. Verify installation from a clean environment:

       pipx install "git+https://github.com/your-org/awsctl.git@v2.0.0"
       awsctl --version

If you are unsure about any part of the process, open a draft PR and ask for feedback.
