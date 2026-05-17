"""
cloudctl prompt — emit a formatted string for shell prompt integration.

Usage:
    cloudctl prompt              # plain text: ☁ bt-avm (123456789012/AdminAccess/us-east-1)
    cloudctl prompt --short      # short form: ☁ bt-avm
    cloudctl prompt --json       # JSON for custom tooling
    cloudctl prompt --format ps1 # PS1-safe escape sequences (bash/zsh)
    cloudctl prompt --starship   # print a starship.toml snippet and exit
    cloudctl prompt --p10k       # print a p10k zsh segment snippet and exit

Add to your shell:

  # bash/zsh — append to PS1
  PS1='$(cloudctl prompt --short 2>/dev/null) '"$PS1"

  # Starship — add to ~/.config/starship.toml  (cloudctl prompt --starship)

  # Powerlevel10k — add to ~/.p10k.zsh  (cloudctl prompt --p10k)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from cloudctl.commands.base import BaseCommand

_PROVIDER_ICON = {"aws": "☁", "azure": "⬡", "gcp": "◆"}
_PROVIDER_COLOR = {"aws": "yellow", "azure": "blue", "gcp": "green"}


def _expiry_label(ctx: Dict[str, Any]) -> Optional[str]:
    """Return a short expiry string like '47m' or None if unavailable."""
    try:
        from datetime import datetime, timezone

        provider = ctx.get("provider", "aws")
        if provider != "aws":
            return None

        org_name = ctx.get("current_org", "")
        if not org_name:
            return None

        from cloudctl.config import get_org
        from cloudctl.providers import get_provider

        org_data = get_org(org_name)
        prov = get_provider(org_data)
        token = prov.load_token(org_data)
        if not token or not hasattr(token, "expiresAt"):
            return None

        delta = token.expiresAt - datetime.now(timezone.utc)
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "expired"
        if total_seconds < 3600:
            return f"{total_seconds // 60}m"
        return f"{total_seconds // 3600}h{(total_seconds % 3600) // 60}m"
    except Exception:
        return None


class PromptCommand(BaseCommand):
    """Emit a cloud-context string for shell prompt integration."""

    def configure_parser(self, subparsers):
        p = subparsers.add_parser(
            "prompt",
            help="Emit cloud context for shell prompt (PS1/Starship/p10k)",
        )
        group = p.add_mutually_exclusive_group()
        group.add_argument(
            "--short",
            action="store_true",
            help="Short form: icon + org name only",
        )
        group.add_argument(
            "--json",
            action="store_true",
            help="Output context as JSON",
        )
        group.add_argument(
            "--starship",
            action="store_true",
            help="Print a starship.toml snippet and exit",
        )
        group.add_argument(
            "--p10k",
            action="store_true",
            help="Print a Powerlevel10k zsh segment snippet and exit",
        )
        p.add_argument(
            "--format",
            choices=["plain", "ps1"],
            default="plain",
            help="Output format (default: plain)",
        )
        p.add_argument(
            "--no-icon",
            action="store_true",
            help="Omit the provider icon",
        )
        p.add_argument(
            "--warn-expiry",
            type=int,
            default=15,
            metavar="MINUTES",
            help="Show expiry warning when credentials expire within N minutes (default: 15)",
        )

    def execute(self, args) -> int:
        # ── snippet modes — print and exit ──────────────────────────────────
        if getattr(args, "starship", False):
            _print_starship_snippet()
            return 0
        if getattr(args, "p10k", False):
            _print_p10k_snippet()
            return 0

        # ── context ─────────────────────────────────────────────────────────
        from cloudctl.context_manager import load_context

        ctx = load_context()
        if not ctx:
            # Emit nothing when no context — keeps prompt clean
            return 0

        provider = ctx.get("provider", "aws")
        org = ctx.get("current_org", "?")
        account = ctx.get("account", "")
        role = ctx.get("role", "")
        region = ctx.get("region", "")
        icon = (
            "" if getattr(args, "no_icon", False) else _PROVIDER_ICON.get(provider, "☁")
        )

        # ── JSON mode ────────────────────────────────────────────────────────
        if getattr(args, "json", False):
            expiry = _expiry_label(ctx)
            out = {
                "provider": provider,
                "org": org,
                "account": account,
                "role": role,
                "region": region,
            }
            if expiry:
                out["expires_in"] = expiry
            sys.stdout.write(json.dumps(out) + "\n")
            return 0

        # ── expiry warning ───────────────────────────────────────────────────
        expiry_str = _expiry_label(ctx)
        warn_mins = getattr(args, "warn_expiry", 15)
        expiry_suffix = ""
        if expiry_str and expiry_str != "expired":
            try:
                mins_left = _parse_expiry_minutes(expiry_str)
                if mins_left is not None and mins_left <= warn_mins:
                    expiry_suffix = f" ⚠{expiry_str}"
            except Exception:
                pass
        elif expiry_str == "expired":
            expiry_suffix = " ✗expired"

        # ── short mode ───────────────────────────────────────────────────────
        if getattr(args, "short", False):
            text = f"{icon} {org}{expiry_suffix}".strip()
            sys.stdout.write(text + "\n")
            return 0

        # ── full mode (default) ──────────────────────────────────────────────
        parts = [p for p in [account, role, region] if p]
        detail = "/".join(parts)
        if detail:
            text = f"{icon} {org} ({detail}){expiry_suffix}".strip()
        else:
            text = f"{icon} {org}{expiry_suffix}".strip()

        sys.stdout.write(text + "\n")
        return 0


def _parse_expiry_minutes(expiry_str: str) -> Optional[int]:
    """Parse '47m' or '1h23m' into total minutes."""
    import re

    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", expiry_str)
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return hours * 60 + mins


def _print_starship_snippet() -> None:
    sys.stdout.write(
        """\
# ── cloudctl Starship integration ───────────────────────────────────────────
# Add this to ~/.config/starship.toml
#
# Displays current cloud context in your prompt:
#   ☁ bt-avm (123456789012/AdminAccess/us-east-1) [warn when <15m left]

[custom.cloudctl]
command = "cloudctl prompt --short 2>/dev/null"
when = "cloudctl prompt --json 2>/dev/null | python3 -c \\"import sys,json; d=json.load(sys.stdin); exit(0 if d.get('org') else 1)\\""
format = "[$output]($style) "
style = "bold yellow"
shell = ["sh", "-c"]
description = "Current cloudctl cloud context"

# ── Optional: show in the right side of the prompt ────────────────────────
# [right_format]
# format = "$custom.cloudctl"
"""
    )


def _print_p10k_snippet() -> None:
    sys.stdout.write(
        """\
# ── cloudctl Powerlevel10k integration ──────────────────────────────────────
# Add this block to ~/.p10k.zsh
#
# 1. Paste the function below into ~/.p10k.zsh
# 2. Add 'cloudctl' to POWERLEVEL9K_LEFT_PROMPT_ELEMENTS or RIGHT
#    e.g.:  typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(... cloudctl)

function prompt_cloudctl() {
  local ctx
  ctx=$(cloudctl prompt --short 2>/dev/null) || return
  [[ -z "$ctx" ]] && return
  p10k segment -f yellow -i '☁' -t "$ctx"
}

function instant_prompt_cloudctl() {
  # Instant prompt: show last known context from cache without running cloudctl
  local ctx_file="${XDG_CONFIG_HOME:-$HOME/.config}/cloudctl/current_context.json"
  [[ -f "$ctx_file" ]] || return
  local org
  org=$(python3 -c "import json,sys; d=json.load(open('$ctx_file')); print(d.get('current_org',''))" 2>/dev/null)
  [[ -z "$org" ]] && return
  p10k segment -f yellow -i '☁' -t "☁ $org"
}

# Optional: style customisation (add to the same file)
# typeset -g POWERLEVEL9K_AWSCTL_FOREGROUND=220
# typeset -g POWERLEVEL9K_AWSCTL_BACKGROUND=236
"""
    )
