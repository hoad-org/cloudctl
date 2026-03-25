# src/awsctl/commands/accounts.py
from awsctl.commands.base import BaseCommand
from awsctl.accounts import get_account_list
from awsctl.config import get_org
from rich.table import Table


class AccountsCommand(BaseCommand):
    """Lists accounts available in an organization."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("accounts", help="List accessible AWS accounts")
        parser.add_argument("org", help="Organization name")
        parser.add_argument(
            "--sync", action="store_true", help="Force refresh account cache"
        )

    def execute(self, args) -> int:
        org_data = get_org(args.org)
        accounts = get_account_list(org_data, force_sync=args.sync)

        table = Table(title=f"Accounts in {args.org}")
        table.add_column("Account ID", style="cyan")
        table.add_column("Account Name", style="green")
        table.add_column("Email", style="blue")

        for acc in sorted(accounts, key=lambda x: x.get("Name", "")):
            table.add_row(
                acc.get("Id", "N/A"), acc.get("Name", "N/A"), acc.get("Email", "N/A")
            )

        self.console.print(table)
        return 0
