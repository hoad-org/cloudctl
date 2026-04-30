# src/cloudctl/commands/gcp_login.py
"""
cloudctl gcp login — Authenticate with GCP and manage credentials.

  cloudctl gcp login [--account EMAIL]

Handles gcloud authentication with smart defaults and helpful messaging.
Automatically opens browser for OAuth2 flow.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

from cloudctl.commands.base import BaseCommand
from cloudctl import utils


class GcpLoginCommand(BaseCommand):
    """Authenticate with GCP via gcloud with automatic browser handling."""

    def __init__(self):
        super().__init__()
        self.args = None

    def configure_parser(self, parser: Any) -> None:
        """Configure argument parser for this command (not used in our dispatch)."""
        pass

    def set_args(self, args: Any) -> None:
        """Set arguments after instantiation."""
        self.args = args

    def _gcloud(self, cmd_args: list[str]) -> dict[str, Any]:
        """Run gcloud command and return result."""
        gcloud_bin = shutil.which("gcloud")
        if not gcloud_bin:
            utils.console.print("[red]gcloud CLI not found in PATH[/red]")
            return {"returncode": 1, "stdout": "", "stderr": "gcloud not found"}

        try:
            result = subprocess.run(
                [gcloud_bin] + cmd_args,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": 1, "stdout": "", "stderr": "Command timeout"}
        except Exception as e:
            return {"returncode": 1, "stdout": "", "stderr": str(e)}

    def execute(self, args: Any = None) -> int:
        """Authenticate with GCP."""
        if args is None:
            args = self.args

        account = getattr(args, "account", None)
        if not account:
            try:
                account = input("Enter GCP email to authenticate as (leave blank for default): ").strip()
                if not account:
                    # Use gcloud auth login without explicit account
                    account = None
            except EOFError:
                # Running non-interactively, require --account
                utils.console.print("[red]Error: --account is required when running non-interactively[/red]")
                utils.console.print("[yellow]Usage: cloudctl gcp login --account admin@example.com[/yellow]")
                return 1

        utils.console.print("[yellow]🔐 Starting GCP authentication...[/yellow]")
        utils.console.print("[yellow]Browser will open automatically for OAuth2 sign-in.[/yellow]")

        # Build gcloud command
        cmd = ["auth", "login"]
        if account:
            cmd.append(account)

        utils.console.print(f"[yellow]Running: gcloud {' '.join(cmd)}[/yellow]")

        result = self._gcloud(cmd)

        # Check result
        if result["returncode"] != 0:
            stderr = result["stderr"]
            # Check for specific errors
            if "You attempted to log in as account" in stderr and "but the received credentials were for" in stderr:
                utils.console.print("[red]❌ Account mismatch![/red]")
                utils.console.print("[red]The browser was logged into a different Google account.[/red]")
                utils.console.print("[yellow]Solution:[/yellow]")
                utils.console.print("[yellow]  Option 1: Sign out from that account in your browser and sign in with the correct one[/yellow]")
                utils.console.print("[yellow]  Option 2: Use an Incognito/Private window[/yellow]")
                utils.console.print("[yellow]  Then run: cloudctl gcp login --account {account}[/yellow]".format(account=account or "EMAIL"))
                return 1
            else:
                utils.console.print(f"[red]❌ Authentication failed[/red]")
                if stderr:
                    utils.console.print(f"[red]{stderr[:200]}[/red]")
                return 1

        # Success
        utils.console.print("[green]✅ Authentication successful![/green]")

        # Show active account
        check = self._gcloud(["auth", "list", "--format=json"])
        if check["returncode"] == 0:
            import json
            try:
                accounts = json.loads(check["stdout"])
                if accounts:
                    active = next((a for a in accounts if a.get("status") == "ACTIVE"), accounts[0])
                    active_email = active.get("account", "unknown")
                    utils.console.print(f"[green]Active account: {active_email}[/green]")
            except (json.JSONDecodeError, StopIteration, KeyError):
                pass

        utils.console.print("\n[bold]Next steps:[/bold]")
        utils.console.print("[cyan]cloudctl gcp grant-iam-roles <org-id> <email> <role1> [role2] ...[/cyan]")
        utils.console.print("[yellow]Example: cloudctl gcp grant-iam-roles 1045595480395 admin@example.com projectCreator folderCreator[/yellow]")

        return 0


def register(parser: Any) -> None:
    """Register the 'gcp login' subcommand."""
    # This is called from the gcp subparser, not the main parser
    pass
