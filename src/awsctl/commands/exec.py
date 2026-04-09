import os
import subprocess
from awsctl.commands.base import BaseCommand
from awsctl.context_manager import load_context
from awsctl.config import get_org


class ExecCommand(BaseCommand):
    """
    Run a command with fresh credentials injected for the active context.

    Retrieves short-lived credentials from the appropriate cloud provider
    (AWS STS, Azure token, or GCP ADC) and passes them as environment
    variables to the child process.  Nothing is written to disk.
    """

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("exec", help="Run a command in context")
        parser.add_argument("cmd", nargs="+", help="Command to execute")

    def execute(self, args) -> int:
        ctx = load_context()
        if not ctx:
            self.console.print("[red]No active context. Run 'awsctl switch' first.[/]")
            return 1

        org_name = ctx.get("current_org", "") or ctx.get("org", "")
        account = ctx.get("account", "")
        role = ctx.get("role", "")
        region = ctx.get("region", "")

        if not all([org_name, account, role]):
            self.console.print(
                "[red]Context is incomplete. Run 'awsctl switch' again.[/]"
            )
            return 1

        try:
            org_data = get_org(org_name)
        except Exception:
            self.console.print(f"[red]Org '{org_name}' not found in config.[/]")
            return 1

        from awsctl.providers import get_provider

        provider = get_provider(org_data)

        try:
            creds = provider.get_credentials(org_data, account, role, region)
        except SystemExit:
            return 1
        except Exception as e:
            self.console.print(f"[red]Failed to get credentials:[/] {e}")
            return 1

        env = os.environ.copy()
        env.update(creds)

        try:
            result = subprocess.run(args.cmd, env=env)
            return result.returncode
        except FileNotFoundError:
            self.console.print(f"[red]Executable not found:[/] {args.cmd[0]}")
            return 127
