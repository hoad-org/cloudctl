"""
cloudctl list-roles — list the IAM roles the current SSO user can assume.

For AWS IAM Identity Center (SSO), the set of assumable roles is per account and
is returned by `aws sso list-account-roles` using the cached SSO access token —
NOT by enumerating IAM roles with ambient credentials (which an agent/SSO session
does not have). This command therefore loads the active SSO token and asks the
provider for the assumable roles in each account (or a single --account).
"""

from typing import Any, Dict, List, Optional

from rich.table import Table

from cloudctl.commands.base import BaseCommand


class ListRolesCommand(BaseCommand):
    """List assumable IAM roles per account, via the active SSO session."""

    def configure_parser(self, subparsers: Any) -> None:
        lrp = subparsers.add_parser(
            "list-roles", help="List the IAM roles you can assume (per account)"
        )
        lrp.add_argument(
            "org", nargs="?", help="Organization name (optional if a context is set)"
        )
        lrp.add_argument(
            "--org",
            dest="org_flag",
            help="Organization name (flag form; same as positional)",
        )
        lrp.add_argument("--account", help="Limit to a single account ID")
        lrp.add_argument(
            "--assigned",
            action="store_true",
            help="(SSO only ever lists assumable roles; kept for compatibility)",
        )
        lrp.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def _resolve_org(self, args: Any) -> str:
        from cloudctl.context_manager import load_context

        if getattr(args, "org", None):
            return args.org
        if getattr(args, "org_flag", None):
            return args.org_flag
        ctx = load_context() or {}
        org = ctx.get("org") or ctx.get("current_org")
        if not org:
            raise RuntimeError(
                "No organization given and no active context. "
                "Pass an org (e.g. 'cloudctl list-roles bt-avm') or run 'cloudctl switch <org>'."
            )
        return org

    def roles_by_account(
        self, org_name: str, account: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Return {account_id: {"name": str, "roles": [role_name, ...]}} via SSO."""
        from cloudctl.accounts import get_account_list
        from cloudctl.config import get_org
        from cloudctl.providers import get_provider
        from cloudctl.sso_cache import OrgRef, load_active_sso_token

        org_data = get_org(org_name)
        token = load_active_sso_token(
            OrgRef(
                org_data.get("name", org_name),
                org_data.get("sso_start_url", ""),
                org_data.get("sso_region", ""),
            )
        )
        if not token:
            raise RuntimeError(
                f"No active SSO session for '{org_name}'. Run: cloudctl login {org_name}"
            )

        provider = get_provider(org_data)

        if account:
            accounts: List[Dict[str, str]] = [{"Id": account, "Name": account}]
        else:
            accounts = get_account_list(org_data)

        out: Dict[str, Dict[str, Any]] = {}
        for acc in accounts:
            acc_id = acc.get("Id") or acc.get("id")
            if not acc_id:
                continue
            out[acc_id] = {
                "name": acc.get("Name") or acc.get("name") or "",
                "roles": provider.list_roles(org_data, token, acc_id),
            }
        return out

    def execute(self, args: Any) -> int:
        try:
            org_name = self._resolve_org(args)
            data = self.roles_by_account(org_name, getattr(args, "account", None))
        except Exception as e:
            self.console.print(f"[red]✗ Error:[/] {e}")
            return 1

        if getattr(args, "format", "text") == "json":
            import json

            print(
                json.dumps(
                    {
                        "organization": org_name,
                        "accounts": [
                            {"id": acc_id, "name": v["name"], "roles": v["roles"]}
                            for acc_id, v in data.items()
                        ],
                    },
                    indent=2,
                )
            )
            return 0

        table = Table(title=f"Assumable roles in {org_name}")
        table.add_column("Account ID", style="cyan")
        table.add_column("Account Name", style="green")
        table.add_column("Roles", style="magenta")
        total = 0
        for acc_id, v in sorted(data.items(), key=lambda kv: kv[1]["name"]):
            table.add_row(acc_id, v["name"], ", ".join(v["roles"]) or "—")
            total += len(v["roles"])
        self.console.print(table)
        self.console.print(f"[green]✓[/] {total} role(s) across {len(data)} account(s)")
        return 0
