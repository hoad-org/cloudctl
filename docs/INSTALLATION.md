# CloudCtl Installation Guide

## Prerequisites

- **Python 3.12** (required, not 3.11 or 3.13)
- **pip** (Python package manager)
- **git** (for cloning the repository)
- Network connectivity to AWS SSO

## Installation Methods

### Method 1: From PyPI (Recommended)

```bash
# Install for current user
python3.12 -m pip install cloudctl

# Verify installation
python3.12 -m cloudctl --version
```

### Method 2: From Source (Development)

```bash
# Clone the repository
git clone https://github.com/BT-IT-Infrastructure-CloudOps/cloudctl.git
cd cloudctl

# Install in editable mode
python3.12 -m pip install -e .

# Verify
python3.12 -m cloudctl --version
```

### Method 3: Upgrade Existing Installation

```bash
# Upgrade to latest version
python3.12 -m pip install --upgrade cloudctl

# Verify
python3.12 -m cloudctl --version
```

## Verify Installation

```bash
# Run health check
python3.12 -m cloudctl doctor
```

Expected output:
```
✅ Python 3.12 available
✅ CloudCtl package installed
✅ Network connectivity OK
```

## System Requirements

| Component | Requirement | Purpose |
|-----------|-------------|---------|
| Python | 3.12+ | Runtime |
| Memory | 256MB+ | Operation |
| Disk | 50MB | Package + cache |
| Network | <1s latency | SSO communication |

## Troubleshooting Installation

### Error: `python3.12: command not found`

**Solution:**
```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12

# RedHat/CentOS
sudo yum install python3.12
```

### Error: `ModuleNotFoundError: No module named 'cloudctl'`

**Solution:**
```bash
# Reinstall
python3.12 -m pip install --force-reinstall cloudctl

# Verify
python3.12 -m pip show cloudctl
```

### Error: `Permission denied` during installation

**Solution:**
```bash
# Install for current user only
python3.12 -m pip install --user cloudctl

# Or use virtual environment
python3.12 -m venv ~/cloudctl-env
source ~/cloudctl-env/bin/activate
pip install cloudctl
```

## Next Steps

1. [Configure CloudCtl](CONFIGURATION.md) — Set up your orgs.yaml
2. [Quick Start](QUICK_START.md) — Your first commands
3. [Command Reference](COMMAND_REFERENCE.md) — All available commands
