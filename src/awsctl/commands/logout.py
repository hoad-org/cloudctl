# src/awsctl/commands/logout.py
import subprocess
from awsctl.commands.base import BaseCommand
from awsctl.aws import _resolve_aws_cli
from awsctl.context_manager import clear_context


class LogoutCommand(BaseCommand):
    """
    Handles termination of AWS SSO sessions and clears
    the local awsctl context to prevent accidental usage.
    """

    def configure_parser(self, subparsers):
        subparsers.add_parser("logout", help="Log out of AWS SSO and clear context")

    def execute(self, args) -> int:
        self.console.print("[bold blue]Logging out of AWS SSO sessions...[/]")

        # 1. Trigger AWS CLI logout
        aws_bin = _resolve_aws_cli()
        result = subprocess.run(
            [aws_bin, "sso", "logout"], capture_output=True, text=True
        )

        # 2. Clear internal context
        clear_context()

        if result.returncode == 0:
            self.console.print(
                "[bold green]✔ Successfully logged out and context cleared.[/]"
            )
        else:
            # SSO logout might fail if no session exists; we still clear context
            self.console.print(
                "[yellow]! No active AWS SSO session found, but local context was cleared.[/]"
            )

        return 0
