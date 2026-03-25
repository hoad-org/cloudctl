# src/awsctl/commands/init.py
from awsctl.commands.base import BaseCommand
from awsctl.wizard import run_setup_wizard


class InitCommand(BaseCommand):
    """Initializes the awsctl configuration."""

    def configure_parser(self, subparsers):
        subparsers.add_parser("init", help="Initialize configuration wizard")

    def execute(self, args) -> int:
        return run_setup_wizard()
