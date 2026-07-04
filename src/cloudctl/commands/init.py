# src/cloudctl/commands/init.py
from cloudctl.commands.base import BaseCommand


def _install_shell_only() -> int:
    """Install the shell wrapper for the detected shell (no interactive prompts)."""
    from cloudctl.env_detection import detect_shell
    from cloudctl import shell, utils

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
    """Non-interactive config initializer + shell integration installer.

    ``cloudctl init`` NEVER prompts. It:
      1. Creates/merges ``~/.config/cloudctl/orgs.yaml`` from the sample template
         (via ``core.cmd_setup`` — the same merge-defaults path as ``setup``).
      2. Installs the shell integration for the detected shell.
      3. Prints a short message telling the user to edit orgs.yaml.

    ``--shell-only`` installs just the shell integration and skips config setup.
    """

    def configure_parser(self, subparsers):
        p = subparsers.add_parser(
            "init", help="Initialize configuration (non-interactive)"
        )
        p.add_argument(
            "--shell-only",
            action="store_true",
            dest="shell_only",
            help="Install shell integration only (skip config setup)",
        )

    def execute(self, args) -> int:
        from cloudctl import config, core, utils

        if getattr(args, "shell_only", False):
            return _install_shell_only()

        # 1. Create/merge orgs.yaml from the sample template (idempotent).
        rc = core.cmd_setup()

        # 2. Install shell integration.
        _install_shell_only()

        # 3. Point the user at the config to edit. Never prompt.
        orgs_path = config.get_orgs_path(ensure=False)
        utils.console.print(
            f"Configuration ready at [bold]{orgs_path}[/bold].\n"
            f"Edit it to add your organisations, then run "
            f"[bold]cloudctl login <org>[/bold]."
        )
        return rc
