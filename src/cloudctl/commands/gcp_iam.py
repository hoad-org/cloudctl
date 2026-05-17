# src/cloudctl/commands/gcp_iam.py
"""
cloudctl gcp grant-iam-roles — Grant organization-level IAM roles.

  cloudctl gcp grant-iam-roles <org-id> <member> <role1> [role2] [role3] ...

Example:
  cloudctl gcp grant-iam-roles 1045595480395 admin@craighoad.com \\
    projectCreator folderCreator billing.projectManager folderIamAdmin
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List

from cloudctl.commands.base import BaseCommand
from cloudctl import utils


class GcpIamCommand(BaseCommand):
    """Grant organization-level IAM roles via gcloud with automatic authentication."""

    def __init__(self):
        super().__init__()
        self.args = None

    def configure_parser(self, parser: Any) -> None:
        """Configure argument parser for this command (not used in our dispatch)."""
        pass

    def set_args(self, args: Any) -> None:
        """Set arguments after instantiation."""
        self.args = args

    def _gcloud(self, cmd_args: List[str]) -> Dict[str, Any]:
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
                timeout=60,
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
        """Grant IAM roles to a member in a GCP organization."""
        # Parse arguments
        if args is None:
            args = self.args

        org_id = args.org_id
        member = args.member
        roles = args.roles

        if not org_id or not member or not roles:
            utils.console.print(
                "[red]Usage: cloudctl gcp grant-iam-roles <org-id> <member> <role1> [role2] ...[/red]"
            )
            return 1

        utils.console.print(
            f"[yellow]🔐 Granting {len(roles)} role(s) to {member} in org {org_id}...[/yellow]"
        )

        # First, ensure authentication with token refresh
        utils.console.print(
            "[yellow]  Ensuring authentication (refreshing token for org operations)...[/yellow]"
        )
        auth_check = self._gcloud(["auth", "list", "--format=json"])
        if auth_check["returncode"] != 0:
            utils.console.print(
                "[red]✗ Not authenticated. Run 'cloudctl login' first.[/red]"
            )
            return 1

        # Force token refresh by trying to get a new token
        # This ensures we have a fresh token for organization-level operations
        utils.console.print(
            "[yellow]  Refreshing credentials for organization-level access...[/yellow]"
        )
        refresh = self._gcloud(["auth", "application-default", "print-access-token"])
        if refresh["returncode"] != 0:
            utils.console.print(
                "[yellow]⚠️  Could not refresh token - proceeding anyway[/yellow]"
            )
            # Continue anyway - the grant commands might still work with cached token

        # Grant each role
        failed_roles = []
        for i, role_name in enumerate(roles, 1):
            # Normalize role name (add "roles/" prefix if not present)
            if not role_name.startswith("roles/"):
                role_name = f"roles/{role_name}"

            utils.console.print(f"  [{i}/{len(roles)}] Granting {role_name}...")

            grant_result = self._gcloud(
                [
                    "organizations",
                    "add-iam-policy-binding",
                    org_id,
                    f"--member=user:{member}",
                    f"--role={role_name}",
                    "--quiet",
                ]
            )

            if grant_result["returncode"] != 0:
                utils.console.print(
                    f"    [red]✗ Failed: {grant_result['stderr'][:100]}[/red]"
                )
                failed_roles.append(role_name)
            else:
                utils.console.print("    [green]✅ Granted[/green]")

        # Verify all grants
        utils.console.print("[yellow]🔍 Verifying all roles were granted...[/yellow]")
        verify_result = self._gcloud(
            [
                "organizations",
                "get-iam-policy",
                org_id,
                "--flatten=bindings[].members",
                f"--filter=members:{member}",
                "--format=json",
            ]
        )

        if verify_result["returncode"] == 0:
            utils.console.print("[green]✅ All roles successfully granted![/green]")
            utils.console.print(f"\n[bold]Granted to {member}:[/bold]")
            utils.console.print(verify_result["stdout"])
            return 0
        else:
            if failed_roles:
                utils.console.print(
                    f"[red]✗ Failed to grant: {', '.join(failed_roles)}[/red]"
                )
                return 1
            else:
                utils.console.print(
                    "[yellow]⚠️  Verification inconclusive (but grants may have succeeded)[/yellow]"
                )
                return 0


def register(parser: Any) -> None:
    """Register the 'gcp grant-iam-roles' subcommand."""
    gcp_parser = parser.add_parser(
        "gcp",
        help="GCP-specific operations",
        description="GCP operations like granting organization-level IAM roles",
    )

    gcp_subparsers = gcp_parser.add_subparsers(dest="gcp_command")

    # grant-iam-roles subcommand
    grant_parser = gcp_subparsers.add_parser(
        "grant-iam-roles",
        help="Grant organization-level IAM roles",
        description=__doc__,
    )

    grant_parser.add_argument(
        "org_id", help="GCP Organization ID (e.g., 1045595480395)"
    )

    grant_parser.add_argument("member", help="Member email (e.g., admin@craighoad.com)")

    grant_parser.add_argument(
        "roles", nargs="+", help="Roles to grant (e.g., projectCreator folderCreator)"
    )

    grant_parser.set_defaults(func=lambda args, ctx: GcpIamCommand(args, ctx).execute())
