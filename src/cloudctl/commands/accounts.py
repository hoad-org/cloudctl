# src/cloudctl/commands/accounts.py
from cloudctl.commands.base import BaseCommand
from cloudctl.accounts import get_account_list
from cloudctl.config import get_org
from cloudctl.output_formatter import get_formatter
from rich.table import Table


class AccountsCommand(BaseCommand):
    """Lists accounts available in an organization."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("accounts", help="List accessible AWS accounts")
        parser.add_argument("org", nargs="?", help="Organization name")
        parser.add_argument(
            "--org",
            dest="org_flag",
            help="Organization name (flag form; same as positional)",
        )
        parser.add_argument(
            "--sync", action="store_true", help="Force refresh account cache"
        )
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )

    def execute(self, args) -> int:
        org_name = getattr(args, "org", None) or getattr(args, "org_flag", None)
        if not org_name:
            self.console.print(
                "[red]No organization given.[/] Usage: cloudctl accounts <org> "
                "(or --org <org>)"
            )
            return 1
        args.org = org_name
        org_data = get_org(org_name)
        accounts = get_account_list(org_data, force_sync=args.sync)

        if args.format == "json":
            # JSON output format
            formatter = get_formatter()
            accounts_list = [
                {
                    "id": acc.get("Id", "N/A"),
                    "name": acc.get("Name", "N/A"),
                    "email": acc.get("Email", "N/A"),
                    "status": acc.get("Status", "ACTIVE"),
                }
                for acc in sorted(accounts, key=lambda x: x.get("Name", ""))
            ]
            formatter.success_json(
                {
                    "organization": args.org,
                    "accounts": accounts_list,
                    "count": len(accounts_list),
                }
            )
        else:
            # Table output format (existing)
            table = Table(title=f"Accounts in {args.org}")
            table.add_column("Account ID", style="cyan")
            table.add_column("Account Name", style="green")
            table.add_column("Email", style="blue")

            for acc in sorted(accounts, key=lambda x: x.get("Name", "")):
                table.add_row(
                    acc.get("Id", "N/A"),
                    acc.get("Name", "N/A"),
                    acc.get("Email", "N/A"),
                )

            self.console.print(table)

        return 0
