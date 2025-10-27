#!/usr/bin/env bash
set -euo pipefail

echo "🚀 awsctl Universal Installer — macOS, Linux, and WSL Compatible"

# Detect OS and package manager
OS="$(uname -s || echo Linux)"
PM=""

case "$OS" in
  Linux*)   PM="$(command -v apt || true)"; [[ -z "$PM" ]] && PM="$(command -v dnf || true)"; [[ -z "$PM" ]] && PM="$(command -v yum || true)";;
  Darwin*)  PM="brew";;
  *) echo "❌ Unsupported OS: $OS"; exit 1;;
esac

echo "🔍 Checking prerequisites..."

need() {
  local bin="$1" install_hint="$2"
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "• Installing $bin ..."
    if [[ "$PM" == "brew" ]]; then
      brew install "$install_hint"
    else
      sudo ${PM:-apt} install -y "$install_hint" || true
    fi
  fi
}

# Python 3, pipx, AWS CLI v2, jq, git
need python3 python3
if ! command -v pipx >/dev/null 2>&1; then
  if [[ "$PM" == "brew" ]]; then brew install pipx; else python3 -m pip install --user pipx || sudo ${PM:-apt} install -y pipx || true; fi
  python3 -m pipx ensurepath
  export PATH="$PATH:$HOME/.local/bin"
fi
if ! command -v aws >/dev/null 2>&1; then
  if [[ "$PM" == "brew" ]]; then
    brew install awscli
  else
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    unzip -q /tmp/awscliv2.zip -d /tmp/
    sudo /tmp/aws/install
  fi
fi
need jq jq
need git git

echo "⚙️ Installing awsctl globally via pipx..."
pipx install --force "$(pwd)" || pipx upgrade awsctl

echo "🔧 Running awsctl setup..."
awsctl setup

echo "✅ Installation complete."
echo "Restart your shell or run 'source ~/.zshrc' (or ~/.bashrc)."
echo "Try: awsctl login --org myorg && awsctl-use"