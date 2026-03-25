# src/awsctl/commands/doctor.py
from awsctl.commands.base import BaseCommand
from awsctl.doctor import run_checks


class DoctorCommand(BaseCommand):
    """
    Diagnostic command to verify the health of the local
    environment, AWS CLI installation, and configuration.
    """

    def configure_parser(self, subparsers):
        subparsers.add_parser("doctor", help="Run environment diagnostics")

    def execute(self, args) -> int:
        success = run_checks()
        return 0 if success else 1
