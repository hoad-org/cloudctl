#!/usr/bin/env bash
# install.sh — awsctl installer for macOS, Linux, and WSL2 (bash / zsh / fish)
# For Windows PowerShell, run install.ps1 instead.
#
# Install order of preference:
#   1. pipx  (recommended — isolated venv, no PEP 668 conflicts, PATH handled automatically)
#   2. pip   (with --user --break-system-packages for Homebrew/Debian managed environments)
#
# To install from Artifactory instead of local source, set:
#   export AWSCTL_INDEX_URL=https://your-org.jfrog.io/artifactory/api/pypi/pypi-local/simple
#
# To install from GitHub Releases (legacy), set:
#   export GITHUB_TOKEN=ghp_your_token
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
_red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
_dim()    { printf '\033[2m%s\033[0m\n'    "$*"; }

_is_wsl() {
    [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null
}

# ---------------------------------------------------------------------------
# 0. Python version guard — require 3.12+
# ---------------------------------------------------------------------------
_check_python() {
    local py
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            local ver major minor
            ver=$("$py" -c "import sys; print(sys.version_info[:2])" 2>/dev/null) || continue
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
    _red "❌ awsctl requires Python 3.12 or newer."
    echo "   Detected: $(python3 --version 2>&1 || echo 'Python not found')"
    echo ""
    echo "   Install Python 3.12+:"
    echo "     macOS (Homebrew):    brew install python@3.12"
    echo "     pyenv:               pyenv install 3.12 && pyenv global 3.12"
    if _is_wsl || [[ "$(uname -s)" == "Linux" ]]; then
        echo "     Ubuntu/Debian WSL:   sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip"
        echo "     (If python3.12 not in apt: sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12)"
    fi
    echo ""
    exit 1
}

echo "   Using: $("$PYTHON_BIN" --version)"

# ---------------------------------------------------------------------------
# WSL notice — browser-based login flows
# ---------------------------------------------------------------------------
if _is_wsl; then
    echo ""
    _yellow "⚠  WSL detected."
    echo "   SSO login flows open a browser. For best results:"
    echo "   • Ensure 'wslu' is installed:  sudo apt install wslu"
    echo "   • Or manually visit the URL printed during 'awsctl login <org>'"
    echo ""
fi

GITHUB_ORG="BT-IT-Infrastructure-CloudOps"
GITHUB_REPO="aws-terraform-infra-cloudops-awsctl"
API_BASE="https://api.github.com/repos/${GITHUB_ORG}/${GITHUB_REPO}"

echo "🚀 Starting awsctl installation..."
echo ""

# ---------------------------------------------------------------------------
# 1. Install the Python package
#    Priority: pipx > Artifactory pip > GitHub Releases pip > local source pip
# ---------------------------------------------------------------------------
echo "📦 Installing package..."

_install_via_pipx() {
    # pipx creates an isolated venv and manages PATH — no PEP 668 conflicts
    echo "   Installing via pipx (recommended)..."

    if [[ -n "${AWSCTL_INDEX_URL:-}" ]]; then
        pipx install awsctl \
            --index-url "${AWSCTL_INDEX_URL}" \
            --pip-args "--extra-index-url https://pypi.org/simple/"
    elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
        _install_from_github_to_tmp
        pipx install "${TMP_WHL}"
        rm -f "${TMP_WHL:-}"
    else
        pipx install --editable .
    fi
}

_install_from_github_to_tmp() {
    echo "   Fetching latest release from GitHub..."
    local release_json tag wheel_url
    release_json=$(curl -sf \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/vnd.github.v3+json" \
        "${API_BASE}/releases/latest")

    tag=$(echo "${release_json}" | "$PYTHON_BIN" -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
    echo "   Latest release: ${tag}"

    wheel_url=$(echo "${release_json}" | "$PYTHON_BIN" -c "
import sys, json
data = json.load(sys.stdin)
whl = next((a for a in data.get('assets', []) if a['name'].endswith('.whl')), None)
if not whl:
    raise SystemExit('No .whl asset found in release ${tag}')
print(whl['url'])
")

    TMP_WHL=$(mktemp --suffix=.whl 2>/dev/null || mktemp -t awsctl.XXXXXX.whl)
    echo "   Downloading wheel..."
    curl -sf \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "Accept: application/octet-stream" \
        -L "${wheel_url}" \
        -o "${TMP_WHL}"
}

_install_via_pip() {
    local pip_args=(install --user)
    # --break-system-packages: required on Homebrew Python and Debian bookworm+
    # (PEP 668 marks the env as externally managed; --user + --break-system-packages
    #  is safe — it only affects the user site-packages, not the system Python)
    if "$PYTHON_BIN" -m pip install --help 2>&1 | grep -q "break-system-packages"; then
        pip_args+=(--break-system-packages)
    fi

    if [[ -n "${AWSCTL_INDEX_URL:-}" ]]; then
        echo "   Installing from Artifactory: ${AWSCTL_INDEX_URL}"
        "$PYTHON_BIN" -m pip "${pip_args[@]}" awsctl \
            --index-url "${AWSCTL_INDEX_URL}" \
            --extra-index-url "https://pypi.org/simple/"
    elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
        _install_from_github_to_tmp
        echo "   Installing from wheel..."
        "$PYTHON_BIN" -m pip "${pip_args[@]}" "${TMP_WHL}" \
            --extra-index-url "https://pypi.org/simple/"
        rm -f "${TMP_WHL:-}"
    else
        echo "   ⚠️  No AWSCTL_INDEX_URL or GITHUB_TOKEN set — installing from local source."
        _dim "   For a release install: export AWSCTL_INDEX_URL=https://your-org.jfrog.io/... and re-run"
        "$PYTHON_BIN" -m pip "${pip_args[@]}" . \
            --extra-index-url "https://pypi.org/simple/"
    fi
}

TMP_WHL=""
if command -v pipx &>/dev/null; then
    _install_via_pipx
else
    _yellow "   pipx not found — falling back to pip."
    _dim "   For a cleaner install: brew install pipx  (macOS) / pip install pipx  (Linux)"
    _install_via_pip

    # Ensure user-bin directory is on PATH for this session
    SCRIPTS_DIR=$("$PYTHON_BIN" -c "
import site, os, sys
base = site.getuserbase()
print(os.path.join(base, 'Scripts' if sys.platform == 'win32' else 'bin'))
")
    case ":${PATH}:" in
        *":${SCRIPTS_DIR}:"*) ;;
        *) export PATH="${SCRIPTS_DIR}:${PATH}" ;;
    esac
fi

# ---------------------------------------------------------------------------
# 2. Install shell integration
# ---------------------------------------------------------------------------
echo ""
echo "🐚 Installing shell integration..."

"$PYTHON_BIN" - <<'PYEOF'
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
# 3. Completion message
# ---------------------------------------------------------------------------
RELOAD_CMD=$("$PYTHON_BIN" - <<'PYEOF'
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
_green "✨ Installation complete!"
echo ""
echo "   Reload your shell:"
echo "     ${RELOAD_CMD}"
echo ""
echo "   Then run:"
echo "     awsctl --version"
echo "     awsctl doctor"
echo "     awsctl init          # run setup wizard"
echo ""
if [[ -n "${AWSCTL_INDEX_URL:-}" ]]; then
    echo "   To upgrade:  awsctl upgrade"
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    echo "   To upgrade:  awsctl upgrade   (requires GITHUB_TOKEN)"
else
    echo "   To upgrade:  export AWSCTL_INDEX_URL=<your-artifactory-url> && awsctl upgrade"
fi
echo ""
echo "💡 Windows (PowerShell) users: run  .\\install.ps1  instead."
