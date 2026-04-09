# src/awsctl/commands/init.py
from awsctl.commands.base import BaseCommand
from awsctl.wizard import run_wizard


def _install_shell_only() -> int:
    """Install the shell wrapper for the detected shell without running the full wizard."""
    from awsctl.env_detection import detect_shell
    from awsctl import shell, utils

    detected = detect_shell()

    if detected == "powershell":
        target_path = shell.detect_powershell_profile()
        inject_fn = shell.inject_powershell_function
    elif detected == "fish":
        target_path = shell.detect_fish_function_file()
        inject_fn = shell.inject_fish_function
    else:
        target_path = shell.detect_shell_profile()
        inject_fn = shell.inject_shell_function

    if inject_fn(target_path):
        utils.console.print(f"Shell integration installed in {target_path}")
        return 0
    else:
        utils.console.print(f"Shell integration already present in {target_path}")
        return 0


class InitCommand(BaseCommand):
    """Initializes the awsctl configuration and installs shell integration."""

    def configure_parser(self, subparsers):
        subparsers.add_parser("init", help="Run the setup wizard")

    def execute(self, args) -> int:
        shell_only = getattr(args, "shell_only", False)
        if shell_only:
            return _install_shell_only()
        return 0 if run_wizard() else 1
