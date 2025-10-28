# 🧭 awsctl

**Beginner-friendly AWS SSO org/account login & profile helper**  
Works on macOS, Linux, and Windows 11 WSL. No boto3. Wraps the official AWS CLI.

---

## 🚀 Features

- One-command SSO login and profile activation  
- Interactive account picker and quick exports  
- Shell helper `awsctl-use` for fast switching  
- Multiple orgs in a single `orgs.yaml`  
- Plugin system with simple enable/disable list (Okta scaffold included)  
- `doctor` command with remediation tips  
- Business rules: optional region allow-list warnings  

---

## 📦 Install

### Global via pipx (recommended)

```bash
# Dependencies you should have:
# macOS: brew install python jq awscli pipx git
# Ubuntu/WSL: sudo apt install -y python3 python3-venv jq awscli pipx git

pipx ensurepath
pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git"
awsctl setup
```

---

### Local development

```bash
git clone https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git
cd awsctl
make setup
```

---

## 🧰 Quick Start

### Create a starter config then edit:
```bash
awsctl init-config > ~/.awsctl/orgs.yaml
```

### Log in to your org:
```bash 
awsctl login --org myorg
```

### List accounts:
```bash
awsctl accounts
```

### Choose and export environment for this shell:
```bash
eval "$(awsctl use)"
# or, after setup:
awsctl-use --account 123456789012 --role AdministratorAccess --region eu-west-2
```

### Diagnose your environment:
```bash
awsctl doctor
```

---

# 📋 Dependencies

## Runtime
- **Python** ≥ 3.9  
- **AWS CLI** v2  
- **jq**  
- **Python packages:**  
  - `colorama`  
  - `PyYAML`  
  - `InquirerPy` *(installed automatically with `awsctl`)*

---

## Development & Tests
- **Testing:**  
  - `pytest`  
  - `pytest-cov`  
  - `pytest-mock`

- **Static Analysis & Formatting:**  
  - `mypy`  
  - `ruff`  
  - `black`  
  - `isort`

- **Security:**  
  - `bandit`  
  - `safety`

- **Build & Packaging:**  
  - `build`  
  - `twine`  
  - `pre-commit`

---

# 🩺 doctor

## Overview
`awsctl doctor` performs environment diagnostics and verifies prerequisites.

### Checks
- `aws`  
- `jq`  
- `python3`  
- `pipx`  
- `git`  
- Readable `~/.awsctl/orgs.yaml`  
- Saved context after login  

It also prints remediation tips for beginners on **macOS**, **Linux**, or **Windows WSL**.

---

# 🔒 Notes on Okta Integration

- Okta can initiate **AWS SSO** or **federation**.  
- Some authentication flows still require **browser confirmation**.  
- The **plugin model** does **not bypass provider-required consent**.  
- Goal: minimize clicks, pre-populate credentials, and validate tokens where permitted.

---

# 🧪 Development

## Run Tests
```bash
make test        # or tox -e py313
pytest -v
```

## Lint and Type Checks
```bash
make lint
```

## Build and Validate
```bash
tox -e build
```

---

# 🗒️ TODO

- **Okta Plugin:**  
  - Add device code flow helpers  
  - Implement token caching rules  

- **Non-interactive Mode:**  
  - Add flags to resolve by account alias  

- **Business Rules Engine:**  
  - Implement per-org enforcement  
  - Add allow/deny set support  

- **Windows Support:**  
  - Add PowerShell helper function

---

# 🧹 Uninstall

```bash
make uninstall
```

Removes pipx package, shell integration lines, and local context.

---

# Summary

## What changed and why
- Beginner-first UX: help, doctor, better init-config.  
- Plugin scaffold with activation list.  
- Business rules engine for region allow-lists.  
- Packaging fixed for pip/pipx with console script.

## How to verify
- `awsctl help`, `awsctl doctor`, `awsctl init-config`, `awsctl login --org myorg`, `eval "$(awsctl use)"`.  
- `pytest -v`, `tox -e py313`.

## How to run tests/validation
- `make test` or `pytest -v`.  
- `make lint` for static checks.  
- `tox -e build` to build wheels.
