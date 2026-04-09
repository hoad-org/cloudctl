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
from pathlib import Path
from awsctl import shell

removed = []

# bash / zsh — check all common profiles, not just the detected one
for candidate in [
    Path.home() / ".zshrc",
    Path.home() / ".bashrc",
    Path.home() / ".bash_profile",
    Path.home() / ".profile",
]:
    if shell.remove_shell_function(candidate):
        removed.append(str(candidate))

# fish function file
fish_file = shell.detect_fish_function_file()
if shell.remove_fish_function(fish_file):
    removed.append(str(fish_file))

# PowerShell profile (cross-platform pwsh)
ps_profile = shell.detect_powershell_profile()
if shell.remove_powershell_function(ps_profile):
    removed.append(str(ps_profile))

if removed:
    for path in removed:
        print(f"  ✓ Removed integration from {path}")
else:
    print("  ℹ️  No shell integration found — nothing to remove")
PYEOF

# ---------------------------------------------------------------------------
# 2. Uninstall the Python package
# ---------------------------------------------------------------------------
echo "📦 Uninstalling package..."
pip3 uninstall -y awsctl 2>/dev/null || pip3 uninstall -y awsctl || true

# ---------------------------------------------------------------------------
# 3. Remove local state (context, audit log, config)
# ---------------------------------------------------------------------------
echo "🗂️  Removing local state..."

rm -rf "${HOME}/.awsctl"
rm -f "${HOME}/.config/awsctl/current_context.json"

echo ""
echo "✅ Uninstallation complete. Please restart your terminal."
echo "💡 Windows (PowerShell) users: run  .\\uninstall.ps1  to remove PS integration."
