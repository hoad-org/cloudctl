# cloudctl Installation

`cloudctl` is a personal project (github user `rhyscraig`, repo
`hoad-org/cloudctl`), version `1.0.0b0` (beta). It is installed editable from a
clone of this repository.

## Prerequisites

- **Python 3.12+**
- **pip**
- **git**
- Network connectivity to your cloud provider's SSO / identity endpoint

## Install (editable, from a clone)

```bash
git clone https://github.com/hoad-org/cloudctl.git
cd cloudctl
python3.12 -m pip install -e .
```

Verify:

```bash
cloudctl --version
cloudctl doctor        # checks the install and config
```

Optional: install into an isolated virtualenv:

```bash
python3.12 -m venv ~/.venvs/cloudctl
source ~/.venvs/cloudctl/bin/activate
python3.12 -m pip install -e .
```

## What gets created / read

| Path | Purpose |
|------|---------|
| `~/.config/cloudctl/orgs.yaml` | Org configuration (created by `init`/`setup`) |
| `~/.config/cloudctl/current_context.json` | Active context (single source of truth) |
| `~/.aws/sso/cache/` | Standard AWS SSO token cache |

## Troubleshooting installation

### `python3.12: command not found`

```bash
# macOS
brew install python@3.12
# Debian/Ubuntu
sudo apt install python3.12
```

### `ModuleNotFoundError: No module named 'cloudctl'`

Re-run the editable install from the repo root:

```bash
python3.12 -m pip install -e .
python3.12 -m pip show cloudctl
```

### `Permission denied` during install

Use a virtualenv (see above) or `--user`:

```bash
python3.12 -m pip install --user -e .
```

## Next steps

1. [Quick Start](QUICK_START.md) — your first commands
2. [Configuration](CONFIGURATION.md) — set up `orgs.yaml`
3. [Command Reference](COMMAND_REFERENCE.md) — all commands
