#!/usr/bin/env zsh
set -e

echo "== MCP Bootstrap for BeyondTrust macOS + zsh =="

REQ_TOOLS=(git gh jq node npm python3 uv terraform docker make tox pytest)
MCP_PACKAGES=(
  "@modelcontextprotocol/server-github"
  "@modelcontextprotocol/server-filesystem"
  "@modelcontextprotocol/server-terminal"
)
VSCODE_DIR=".vscode"
FIX_CERTS=false

if [[ "$1" == "--fix-certs" ]]; then
  FIX_CERTS=true
fi

log() { print -P "%F{cyan}==>%f $1"; }
ok()  { print -P "%F{green}[OK]%f $1"; }
warn(){ print -P "%F{yellow}[WARN]%f $1"; }
err() { print -P "%F{red}[ERR]%f $1"; }

log "Checking Homebrew environment..."
if ! command -v brew &>/dev/null; then
  err "Homebrew not installed. Installing..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  ok "Homebrew installed: $(brew --version | head -n1)"
fi

log "Auditing core tools..."
for tool in $REQ_TOOLS; do
  if ! command -v $tool &>/dev/null; then
    warn "$tool missing — installing via Homebrew..."
    brew install $tool || warn "Could not install $tool automatically."
  else
    ok "$tool: $($tool --version 2>&1 | head -n1)"
  fi
done

log "Auditing MCP servers..."
for pkg in $MCP_PACKAGES; do
  if ! npm list -g $pkg &>/dev/null; then
    warn "$pkg not found — attempting install..."
    npm install -g $pkg --registry=https://registry.npmjs.org || warn "Could not install $pkg (check registry/proxy)"
  else
    ok "$pkg already installed."
  fi
done

if $FIX_CERTS; then
  log "Exporting corporate CA bundle..."
  security find-certificate -a -p /Library/Keychains/System.keychain > ~/bt-certs.pem
  export NODE_EXTRA_CA_CERTS=~/bt-certs.pem
  export NPM_CONFIG_STRICT_SSL=false
  ok "Corporate CA bundle exported."
fi

log "Ensuring .vscode configuration is present..."
mkdir -p $VSCODE_DIR
ok ".vscode directory ensured."

log "Bootstrap complete. Please reload VS Code and run 'MCP: List Servers'."
