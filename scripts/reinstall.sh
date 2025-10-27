#!/usr/bin/env bash
set -euo pipefail
echo "🔄 Cleaning and reinstalling awsctl..."

# --- Detect shell and rc file ---
SHELL_NAME="$(basename "$SHELL" 2>/dev/null || echo "bash")"
if [[ "$SHELL_NAME" == "zsh" ]]; then
  RC_FILE="$HOME/.zshrc"
else
  RC_FILE="$HOME/.bashrc"
fi

# --- Deactivate and remove venv if present ---
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "➡ Deactivating current virtualenv..."
  deactivate || true
fi

if [[ -d "venv" ]]; then
  echo "🧹 Removing existing venv..."
  rm -rf venv
fi

# --- Remove existing pip installs (venv or user/global) ---
pip uninstall -y awsctl 2>/dev/null || true
pipx uninstall awsctl 2>/dev/null || true

# --- Clean old shell integration ---
if [[ -f "$RC_FILE" ]]; then
  echo "🧽 Cleaning old shell integration in $RC_FILE..."
  sed -i.bak '/AWSCTL SHELL INTEGRATION (auto-installed)/,/END AWSCTL SHELL INTEGRATION/d' "$RC_FILE" || true
fi

# --- Remove stale config/context ---
rm -f ~/.aws/awsctl-context.json 2>/dev/null || true
rm -f ~/.awsctl/orgs.yaml 2>/dev/null || true

# --- Recreate venv and reinstall editable ---
echo "📦 Creating new virtualenv..."
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo "⬆ Upgrading pip/setuptools/wheel..."
pip install -U pip setuptools wheel

echo "📥 Installing awsctl (editable)..."
pip install -e .

# --- Run setup to inject shell integration + auto-source ---
echo "⚙️ Running preflight and shell integration..."
awsctl setup

# --- Verify integration block exists ---
if grep -q "AWSCTL SHELL INTEGRATION" "$RC_FILE"; then
  echo "✅ Shell integration present in $RC_FILE"
else
  echo "❌ Shell integration not found in $RC_FILE. Please check manually."
fi

# --- Auto-source profile ---
echo "🔁 Sourcing $RC_FILE..."
# shellcheck disable=SC1090
source "$RC_FILE" || true

echo
echo "✅ Reinstall complete!"
echo "Try running:"
echo "  awsctl login --org myorg"
echo "  awsctl-use"
echo "  aws s3 ls"
