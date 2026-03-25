# src/awsctl/commands/login.py
from awsctl.commands.base import BaseCommand
from awsctl.core import cmd_login


class LoginCommand(BaseCommand):
    """Handles AWS SSO authentication."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("login", help="Authenticate with AWS SSO")
        parser.add_argument("org", help="Organization name to log in to")
        parser.add_argument(
            "--force", action="store_true", help="Force re-authentication"
        )

    def execute(self, args) -> int:
        return cmd_login(args.org, args.force)
