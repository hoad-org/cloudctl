#!/bin/bash
# install.sh - awsctl Precision Installer for macOS/Linux/WSL
set -euo pipefail

echo "🚀 Starting awsctl installation..."

SCRIPTS_DIR=$(python3 -c "import site, os; base=site.getuserbase(); print(os.path.join(base, 'Scripts' if os.name == 'nt' else 'bin'))")
mkdir -p "$SCRIPTS_DIR"

echo "📦 Installing package via pip..."
pip3 install --user .

SENTINEL_START="# >>> AWSCTL BLOCK START >>>"
SENTINEL_END="# <<< AWSCTL BLOCK END <<<"

INTEGRATION_CODE="
$SENTINEL_START
# Managed by awsctl install.sh
export PATH=\"\$PATH:$SCRIPTS_DIR\"
eval \"\$(awsctl --hook-output /dev/stdout 2>/dev/null)\"
$SENTINEL_END"

SHELL_NAME=$(basename "$SHELL")
PROFILE_PATH=""

case "$SHELL_NAME" in
    zsh)  PROFILE_PATH="$HOME/.zshrc" ;;
    bash) PROFILE_PATH="$HOME/.bashrc" ;;
    *)    echo "⚠️  Unsupported shell: $SHELL_NAME. Manual integration required." ;;
esac

if [ -n "$PROFILE_PATH" ]; then
    if [ ! -f "$PROFILE_PATH" ]; then
        touch "$PROFILE_PATH"
    fi
    
    if grep -q "$SENTINEL_START" "$PROFILE_PATH"; then
        echo "🔄 Integration already exists in $PROFILE_PATH. Updating..."
        sed -i.bak "/$SENTINEL_START/,/$SENTINEL_END/d" "$PROFILE_PATH"
        rm -f "${PROFILE_PATH}.bak"
    fi
    echo "$INTEGRATION_CODE" >> "$PROFILE_PATH"
    echo "✅ Shell integration added to $PROFILE_PATH"
fi

echo "✨ Installation complete. Please restart your terminal or run: source $PROFILE_PATH"
