# src/cloudctl/commands/accounts.py
import json

from cloudctl.commands.base import BaseCommand
from cloudctl.accounts import get_account_list
from cloudctl.config import get_org
from cloudctl.output_formatter import get_formatter
from cloudctl.providers.base import ProviderCredentialError
from cloudctl import exit_codes
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

    def _fail_lookup(self, args, message: str) -> int:
        """Emit a clean not-found failure honoring --format, return NOT_FOUND (3).

        In json mode a single-line ``{"error": ..., "code": 3}`` object is
        printed to STDOUT (so an agent parses it off the normal output stream);
        otherwise a red prose line goes to STDERR.
        """
        if getattr(args, "format", None) == "json":
            print(json.dumps({"error": message, "code": exit_codes.NOT_FOUND}))
        else:
            self.console.print(f"[red]✗ {message}[/]")
        return exit_codes.NOT_FOUND

    def _fail_provider(self, args, err: "ProviderCredentialError") -> int:
        """Emit a faithful provider-credential failure honoring --format.

        Maps the raised error's classified ``.code``/``.message`` (auth/denied/
        not-found) to a clean message and that exit code — never flattened to a
        generic error. json → single-line object on STDOUT; else red prose.
        """
        if getattr(args, "format", None) == "json":
            print(json.dumps({"error": err.message, "code": err.code}))
        else:
            self.console.print(f"[red]✗ {err.message}[/]")
        return err.code

    def execute(self, args) -> int:
        org_name = getattr(args, "org", None) or getattr(args, "org_flag", None)
        if not org_name:
            self.console.print(
                "[red]No organization given.[/] Usage: cloudctl accounts <org> "
                "(or --org <org>)"
            )
            return 1
        args.org = org_name
        # A bad org name is a user typo, not a bug: fail with a clean,
        # actionable NOT_FOUND (3) — never let it bubble to the generic
        # "UNEXPECTED ERROR" handler in cli.py.
        try:
            org_data = get_org(org_name)
        except Exception as e:
            return self._fail_lookup(args, f"Organization '{org_name}' not found: {e}")
        # list_accounts now RAISES ProviderCredentialError on failure (auth /
        # denied / etc.) instead of masking it as an empty list. Map the real
        # code + message to a clean, format-aware failure.
        try:
            accounts = get_account_list(org_data, force_sync=args.sync)
        except ProviderCredentialError as e:
            return self._fail_provider(args, e)

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
                    # Unified org-identifier key across read commands: `org`.
                    "org": args.org,
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
