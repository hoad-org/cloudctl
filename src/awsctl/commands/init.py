# src/awsctl/commands/init.py
from awsctl.commands.base import BaseCommand
from awsctl.wizard import run_wizard


class InitCommand(BaseCommand):
    """Initializes the awsctl configuration and installs shell integration."""

    def configure_parser(self, subparsers):
        subparsers.add_parser("init", help="Run the setup wizard")

    def execute(self, args) -> int:
        return 0 if run_wizard() else 1
