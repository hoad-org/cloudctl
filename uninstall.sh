#!/bin/bash
# uninstall.sh - awsctl Clean Uninstaller
set -euo pipefail

echo "🗑️  Starting awsctl uninstallation..."

pip3 uninstall -y awsctl || true

SENTINEL_START="# >>> AWSCTL BLOCK START >>>"
SENTINEL_END="# <<< AWSCTL BLOCK END <<<"

for PROFILE in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$PROFILE" ]; then
        if grep -q "$SENTINEL_START" "$PROFILE"; then
            echo "🧹 Removing integration from $PROFILE..."
            sed -i.bak "/$SENTINEL_START/,/$SENTINEL_END/d" "$PROFILE"
            rm -f "${PROFILE}.bak"
        fi
    fi
done

rm -rf "$HOME/.awsctl"
rm -f "$HOME/.config/awsctl/current_context.json"

echo "✅ Uninstallation complete. Please restart your terminal."
