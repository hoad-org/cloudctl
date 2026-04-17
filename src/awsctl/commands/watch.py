"""
awsctl watch — keep credentials alive by auto-refreshing before expiry.

Usage:
    awsctl watch [org]             # refresh active (or named) org every check-interval
    awsctl watch bt-avm --interval 300   # custom check interval in seconds

The command runs in the foreground; press Ctrl+C to stop.

It does NOT export credentials back to the shell (the subprocess boundary
prevents that). Instead it keeps the SSO token cache fresh so that the next
`awsctl switch` is instant. Works best when run in a dedicated terminal pane
or a tmux/screen session alongside long-running Terraform operations.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from awsctl.commands.base import BaseCommand
from awsctl import utils

# Refresh when this many seconds remain on the token
_REFRESH_THRESHOLD_SECS = 900  # 15 minutes
_DEFAULT_CHECK_INTERVAL = 60   # seconds between checks


class WatchCommand(BaseCommand):
    """Keep cloud credentials alive with automatic refresh before expiry."""

    def configure_parser(self, subparsers):
        p = subparsers.add_parser(
            "watch",
            help="Auto-refresh credentials before they expire (run in background pane)",
        )
        p.add_argument(
            "org", nargs="?",
            help="Organisation to watch (defaults to active context)",
        )
        p.add_argument(
            "--interval", type=int, default=_DEFAULT_CHECK_INTERVAL, metavar="SECS",
            help=f"How often to check token expiry in seconds (default: {_DEFAULT_CHECK_INTERVAL})",
        )
        p.add_argument(
            "--threshold", type=int, default=_REFRESH_THRESHOLD_SECS, metavar="SECS",
            help=f"Refresh when this many seconds remain (default: {_REFRESH_THRESHOLD_SECS})",
        )
        p.add_argument(
            "--once", action="store_true",
            help="Check once and exit (useful for scripts)",
        )

    def execute(self, args) -> int:
        from awsctl.context_manager import load_context
        from awsctl.config import get_org
        from awsctl.providers import get_provider

        org_name = getattr(args, "org", None)
        interval = getattr(args, "interval", _DEFAULT_CHECK_INTERVAL)
        threshold = getattr(args, "threshold", _REFRESH_THRESHOLD_SECS)
        once = getattr(args, "once", False)

        # Resolve org from arg or active context
        if not org_name:
            ctx = load_context()
            org_name = ctx.get("current_org") if ctx else None
        if not org_name:
            self.console.print(
                "[red]No org specified and no active context.[/]\n"
                "Run [bold]awsctl switch <org>[/bold] first, or pass org name: "
                "[bold]awsctl watch <org>[/bold]"
            )
            return 1

        try:
            org_data = get_org(org_name)
        except Exception:
            self.console.print(f"[red]Org '{org_name}' not found in config.[/]")
            return 1

        provider = get_provider(org_data)
        pname = org_data.get("provider", "aws").upper()

        self.console.print(
            f"[bold cyan]awsctl watch[/bold cyan]  "
            f"org=[bold]{org_name}[/bold] [{pname}]  "
            f"check-interval={interval}s  refresh-threshold={threshold}s"
        )
        self.console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

        try:
            while True:
                refreshed, msg = _check_and_refresh(
                    org_data, provider, threshold
                )
                ts = datetime.now().strftime("%H:%M:%S")
                if refreshed:
                    self.console.print(f"[green][{ts}] Refreshed — {msg}[/green]")
                else:
                    self.console.print(f"[dim][{ts}] {msg}[/dim]")

                if once:
                    return 0
                time.sleep(interval)

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Watch stopped.[/yellow]")
            return 0


def _check_and_refresh(
    org_data: Dict[str, Any],
    provider: Any,
    threshold_secs: int,
) -> tuple[bool, str]:
    """
    Check token validity and refresh if needed.

    Uses provider.get_token_expiry() which returns a timezone-aware datetime
    (or None).  Falls back to load_token + .expiresAt for backward compat.

    Returns (refreshed: bool, message: str).
    """
    try:
        token = provider.load_token(org_data)
    except Exception as exc:
        return False, f"Could not load token: {exc}"

    if not token:
        # No token — attempt login
        rc = provider.login(org_data)
        if rc == 0:
            return True, "No token found — initiated login"
        return False, "No token and login failed"

    # Resolve expiry: prefer get_token_expiry() (all providers), then .expiresAt (AWS legacy)
    expires_at = None
    if hasattr(provider, "get_token_expiry"):
        try:
            expires_at = provider.get_token_expiry(org_data)
        except Exception:
            pass
    if expires_at is None and hasattr(token, "expiresAt"):
        expires_at = token.expiresAt

    if expires_at is None:
        return False, "Token active (expiry unknown)"

    now = datetime.now(timezone.utc)
    delta = expires_at - now
    remaining = int(delta.total_seconds())

    if remaining <= 0:
        rc = provider.login(org_data)
        if rc == 0:
            return True, "Token expired — re-authenticated"
        return False, "Token expired and re-auth failed"

    if remaining <= threshold_secs:
        mins = remaining // 60
        rc = provider.login(org_data)
        if rc == 0:
            return True, f"Token had {mins}m left — refreshed proactively"
        return False, f"Token has {mins}m left but refresh failed"

    mins = remaining // 60
    hours = mins // 60
    mins_rem = mins % 60
    if hours > 0:
        time_str = f"{hours}h {mins_rem}m"
    else:
        time_str = f"{mins_rem}m"
    return False, f"Token valid — expires in {time_str}"
