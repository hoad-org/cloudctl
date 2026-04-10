#!/usr/bin/env bash
# uninstall.sh — awsctl clean uninstaller for macOS, Linux, and WSL
# For Windows PowerShell, run uninstall.ps1 instead.
set -euo pipefail

echo "🗑️  Starting awsctl uninstallation..."

# ---------------------------------------------------------------------------
# 1. Remove shell wrapper from all profiles that contain it
#    Use the Python helpers so removal logic stays in one place.
# ---------------------------------------------------------------------------
echo "🧹 Removing shell integration..."

python3 - <<'PYEOF' 2>/dev/null || true
import re
from pathlib import Path

try:
    from awsctl import shell as _shell
    _remove_shell  = _shell.remove_shell_function
    _remove_fish   = _shell.remove_fish_function
    _remove_ps     = _shell.remove_powershell_function
    _detect_fish   = _shell.detect_fish_function_file
    _detect_ps     = _shell.detect_powershell_profile
except Exception:
    _remove_shell = _remove_fish = _remove_ps = lambda *a: False
    _detect_fish  = lambda: Path.home() / ".config/fish/functions/awsctl.fish"
    _detect_ps    = lambda: Path.home() / "Documents/PowerShell/Microsoft.PowerShell_profile.ps1"

# -----------------------------------------------------------------------
# Legacy wrapper patterns — any version prior to the current v3 format.
# These are identified by a comment+function block starting with one of
# the known header strings and ending at the closing "}" on its own line.
# -----------------------------------------------------------------------
_LEGACY_PATTERNS = [
    # v2.x "SECURE" variants
    r"# AWSCTL SHELL INTEGRATION \(v[\d.]+-[A-Z]+\)\nawsctl\(\) \{.*?\n\}",
    # Any remaining "# AWSCTL SHELL INTEGRATION" block (catches future drift)
    r"# AWSCTL SHELL INTEGRATION[^\n]*\nawsctl\(\) \{.*?\n\}",
    # Old venv PATH lines that awsctl installers used to inject
    r"export PATH=\"\$HOME/repos/AWS/awsctl/\.venv_awsctl/bin[^\n]*\n?",
]

def _remove_legacy(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return False

    new_content = content
    for pattern in _LEGACY_PATTERNS:
        new_content = re.sub(pattern, "", new_content, flags=re.DOTALL)

    # Collapse excessive blank lines left behind
    new_content = re.sub(r"\n{3,}", "\n\n", new_content).rstrip() + "\n"

    if new_content == content:
        return False
    try:
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False

removed = []

for candidate in [
    Path.home() / ".zshrc",
    Path.home() / ".bashrc",
    Path.home() / ".bash_profile",
    Path.home() / ".profile",
]:
    # Try v3 remover first, fall back to legacy pattern scrub
    if _remove_shell(candidate) or _remove_legacy(candidate):
        removed.append(str(candidate))

fish_file = _detect_fish()
if _remove_fish(fish_file):
    removed.append(str(fish_file))

ps_profile = _detect_ps()
if _remove_ps(ps_profile):
    removed.append(str(ps_profile))

if removed:
    for path in removed:
        print(f"  ✓ Removed integration from {path}")
else:
    print("  ℹ️  No shell integration found — nothing to remove")
PYEOF

# ---------------------------------------------------------------------------
# 2. Remove awsctl-managed [sso-session] blocks from ~/.aws/config
# ---------------------------------------------------------------------------
echo "🔑 Cleaning ~/.aws/config SSO sessions..."

python3 - <<'PYEOF' 2>/dev/null || true
import configparser
import pathlib
import yaml

orgs_file = pathlib.Path.home() / ".config" / "awsctl" / "orgs.yaml"
aws_config = pathlib.Path.home() / ".aws" / "config"

if not orgs_file.exists() or not aws_config.exists():
    print("  ℹ️  Nothing to clean")
    exit(0)

try:
    data = yaml.safe_load(orgs_file.read_text()) or {}
except Exception:
    data = {}

orgs = data.get("orgs", [])
aws_org_names = [o["name"] for o in orgs if o.get("provider", "aws") == "aws" and "name" in o]

if not aws_org_names:
    print("  ℹ️  No AWS orgs found — nothing to clean")
    exit(0)

cfg = configparser.RawConfigParser()
cfg.read(aws_config)

removed = []
for name in aws_org_names:
    section = f"sso-session {name}"
    if cfg.has_section(section):
        cfg.remove_section(section)
        removed.append(section)

if removed:
    with open(aws_config, "w") as f:
        cfg.write(f)
    for s in removed:
        print(f"  ✓ Removed [{s}] from ~/.aws/config")
else:
    print("  ℹ️  No awsctl SSO sessions found in ~/.aws/config")
PYEOF

# ---------------------------------------------------------------------------
# 4. Uninstall the Python package
# ---------------------------------------------------------------------------
echo "📦 Uninstalling package..."
pip3 uninstall -y awsctl 2>/dev/null || pip3 uninstall -y awsctl || true

# ---------------------------------------------------------------------------
# 5. Remove local state (context, audit log, config)
# ---------------------------------------------------------------------------
echo "🗂️  Removing local state..."

rm -rf "${HOME}/.awsctl"
rm -f "${HOME}/.config/awsctl/current_context.json"

echo ""
echo "✅ Uninstallation complete. Please restart your terminal."
echo "💡 Windows (PowerShell) users: run  .\\uninstall.ps1  to remove PS integration."
