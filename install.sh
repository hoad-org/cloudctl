#!/usr/bin/env bash
# install.sh — awsctl installer for macOS, Linux, and WSL (bash / zsh / fish)
# For Windows PowerShell, run install.ps1 instead.
set -euo pipefail

echo "🚀 Starting awsctl installation..."

# ---------------------------------------------------------------------------
# 1. Install the Python package
# ---------------------------------------------------------------------------
echo "📦 Installing package via pip..."
pip3 install --user .

# Ensure the user-bin directory is on PATH for this session so we can call
# awsctl immediately without reopening the terminal.
SCRIPTS_DIR=$(python3 -c "
import site, os, sys
base = site.getuserbase()
scripts = os.path.join(base, 'Scripts' if sys.platform == 'win32' else 'bin')
print(scripts)
")

case ":${PATH}:" in
    *":${SCRIPTS_DIR}:"*) ;;
    *) export PATH="${PATH}:${SCRIPTS_DIR}" ;;
esac

# ---------------------------------------------------------------------------
# 2. Inject the shell wrapper using the same Python logic awsctl init uses
#    (this avoids duplicating shell-detection logic in bash)
# ---------------------------------------------------------------------------
echo "🐚 Installing shell integration..."

python3 - <<'PYEOF'
import sys
from awsctl.env_detection import detect_shell
from awsctl import shell

detected = detect_shell()

if detected == "fish":
    target = shell.detect_fish_function_file()
    ok = shell.inject_fish_function(target)
    kind = f"fish function file ({target})"
elif detected == "powershell":
    # Shouldn't reach here via bash, but handle gracefully.
    target = shell.detect_powershell_profile()
    ok = shell.inject_powershell_function(target)
    kind = f"PowerShell profile ({target})"
else:
    target = shell.detect_shell_profile()
    ok = shell.inject_shell_function(target)
    kind = f"shell profile ({target})"

if ok:
    print(f"✅ Shell integration installed in {kind}")
else:
    print(f"ℹ️  Shell integration already present in {kind} — no changes made")
PYEOF

# ---------------------------------------------------------------------------
# 3. Print a helpful restart message
# ---------------------------------------------------------------------------
RELOAD_CMD=$(python3 - <<'PYEOF'
from awsctl.env_detection import detect_shell
from awsctl import shell
detected = detect_shell()
if detected == "fish":
    # fish reloads functions automatically; no source needed
    print("fish: functions are reloaded automatically")
else:
    profile = shell.detect_shell_profile()
    print(f"source {profile}")
PYEOF
)

echo ""
echo "✨ Installation complete!"
echo "   Reload your shell:"
echo "     ${RELOAD_CMD}"
echo ""
echo "   Then verify:"
echo "     awsctl --version"
echo "     awsctl doctor"
echo ""
echo "💡 Windows (PowerShell) users: run  .\\install.ps1  instead."
