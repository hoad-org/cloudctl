#!/usr/bin/env bash
# install.sh — awsctl installer for macOS, Linux, and WSL2 (bash / zsh / fish)
# For Windows PowerShell, run install.ps1 instead.
#
# Requires GITHUB_TOKEN (PAT with read:contents or repo scope) to download
# from the private repository. Falls back to a local source install if unset.
set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Python version guard — require 3.12+
# ---------------------------------------------------------------------------
_check_python() {
    local py
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            local ver
            ver=$("$py" -c "import sys; print(sys.version_info[:2])" 2>/dev/null) || continue
            # ver looks like "(3, 12)" — extract major/minor
            local major minor
            major=$(echo "$ver" | tr -d '() ' | cut -d, -f1)
            minor=$(echo "$ver" | tr -d '() ' | cut -d, -f2)
            if [[ "$major" -gt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -ge 12 ]]; }; then
                echo "$py"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN=$(_check_python) || {
    echo "❌ awsctl requires Python 3.12 or newer."
    echo "   Detected Python version is too old (need ≥3.12, got: $(python3 --version 2>&1 || echo 'not found'))."
    echo ""
    echo "   Install Python 3.12+ via pyenv, Homebrew, or your system package manager:"
    echo "     brew install python@3.12          # macOS (Homebrew)"
    echo "     pyenv install 3.12 && pyenv global 3.12  # pyenv"
    echo "     sudo apt install python3.12       # Debian/Ubuntu"
    echo ""
    exit 1
}

PIP_BIN="${PYTHON_BIN} -m pip"
echo "   Using: $("$PYTHON_BIN" --version)"

GITHUB_ORG="BT-IT-Infrastructure-CloudOps"
GITHUB_REPO="aws-terraform-infra-cloudops-awsctl"
API_BASE="https://api.github.com/repos/${GITHUB_ORG}/${GITHUB_REPO}"

echo "🚀 Starting awsctl installation..."

# ---------------------------------------------------------------------------
# 1. Install the Python package
# ---------------------------------------------------------------------------
echo "📦 Installing package..."

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    echo "   Fetching latest release from GitHub..."

    # Query the GitHub Releases API for the latest wheel asset
    RELEASE_JSON=$(curl -sf \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${API_BASE}/releases/latest")

    TAG=$(echo "${RELEASE_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin)['tag_name'])")
    echo "   Latest release: ${TAG}"

    WHEEL_URL=$(echo "${RELEASE_JSON}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
whl = next((a for a in data.get('assets', []) if a['name'].endswith('.whl')), None)
if not whl:
    raise SystemExit('No .whl asset found in release')
print(whl['url'])
")

    # Download the wheel to a temp file and install
    TMP_WHL=$(mktemp --suffix=.whl 2>/dev/null || mktemp -t awsctl.XXXXXX.whl)
    echo "   Downloading wheel..."
    curl -sf \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/octet-stream" \
        -L "${WHEEL_URL}" \
        -o "${TMP_WHL}"

    echo "   Installing from wheel (dependencies from PyPI)..."
    $PIP_BIN install --user "${TMP_WHL}" --extra-index-url "https://pypi.org/simple/"
    rm -f "${TMP_WHL}"
else
    echo "   ⚠️  GITHUB_TOKEN not set — installing from local source."
    echo "   For the latest release: export GITHUB_TOKEN=<your-PAT> and re-run."
    $PIP_BIN install --user . --extra-index-url "https://pypi.org/simple/"
fi

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
# 3. Helpful restart message
# ---------------------------------------------------------------------------
RELOAD_CMD=$(python3 - <<'PYEOF'
from awsctl.env_detection import detect_shell
from awsctl import shell
detected = detect_shell()
if detected == "fish":
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
echo "   To upgrade later:  awsctl upgrade   (requires GITHUB_TOKEN)"
echo "💡 Windows (PowerShell) users: run  .\\install.ps1  instead."
