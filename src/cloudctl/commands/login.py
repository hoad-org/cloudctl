# src/cloudctl/commands/login.py
from cloudctl.commands.base import BaseCommand
from cloudctl.core import cmd_login


class LoginCommand(BaseCommand):
    """Authenticate with the cloud provider for a configured org (AWS, Azure, or GCP)."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser(
            "login", help="Authenticate with the cloud provider for an org"
        )
        parser.add_argument("org", help="Organization name to log in to")
        parser.add_argument(
            "--force", action="store_true", help="Force re-authentication"
        )

    def execute(self, args) -> int:
        return cmd_login(args.org, args.force)
