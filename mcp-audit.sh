#!/usr/bin/env zsh
set -euo pipefail

echo "== MCP Audit (macOS + zsh) =="

# VS Code CLI
if ! command -v code >/dev/null; then
  echo "VS Code CLI not found."
  echo "Open VS Code → Command Palette → 'Shell Command: Install \"code\" command in PATH'"
  exit 1
fi
echo "-- VS Code --"
code --version | head -n1

# Copilot Chat extension
if code --list-extensions | grep -qi "github.copilot-chat"; then
  echo "Copilot Chat: installed"
else
  echo "Copilot Chat: MISSING (install from VS Code marketplace)"
fi

# Node (for npx filesystem server)
if ! command -v node >/dev/null || ! command -v npx >/dev/null; then
  echo "Node.js/npx: MISSING (brew install node)"
else
  echo "Node.js: $(node -v)"
fi

# uv (for mcp-server-git)
if ! command -v uvx >/dev/null; then
  echo "uv: MISSING -> install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
else
  echo "uv: $(uv --version)"
fi

# Docker for Terraform MCP container
if ! command -v docker >/dev/null; then
  echo "Docker: MISSING (install Docker Desktop for Mac)"
else
  docker --version
fi

# Helpful CLIs for fallback/non-MCP flows
for b in aws jq gh python3 git terraform; do
  if command -v "$b" >/dev/null; then
    echo "$b: OK ($("$b" --version 2>&1 | head -n1))" || true
  else
    echo "$b: MISSING"
  fi
done

# VS Code workspace files
[[ -f ".vscode/mcp.json" ]] && echo ".vscode/mcp.json: present" || echo ".vscode/mcp.json: MISSING"
[[ -f ".vscode/settings.json" ]] && echo ".vscode/settings.json: present" || echo ".vscode/settings.json: MISSING"

# Nudge
echo ""
echo "Next in VS Code:"
echo "  1) Open .vscode/mcp.json and click 'Auth' on the GitHub server row to sign in."
echo "  2) Run: 'MCP: List Servers' → verify github, filesystem, git, terraform are healthy."
echo "== Audit complete =="
