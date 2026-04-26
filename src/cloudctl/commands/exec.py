import os
import subprocess
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import load_context
from cloudctl.config import get_org


class ExecCommand(BaseCommand):
    """
    Run a command with fresh credentials injected for the active context.

    Retrieves short-lived credentials from the appropriate cloud provider
    (AWS STS, Azure token, or GCP ADC) and passes them as environment
    variables to the child process.  Nothing is written to disk.

    Examples:
        # Use active context (set by cloudctl switch)
        cloudctl exec -- terraform plan

        # Explicit org without changing shell context (safe for scripts)
        cloudctl exec --org prod -- aws s3 ls
        cloudctl exec --org fdr-gvc --account 111111111111 --role ReadOnly -- terraform show
    """

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser(
            "exec",
            help="Run a command with cloud credentials (without changing shell context)",
        )
        parser.add_argument(
            "--org", dest="exec_org",
            help="Organisation to use (defaults to active context)",
        )
        parser.add_argument(
            "--account", dest="exec_account",
            help="Account/subscription/project ID (defaults to context)",
        )
        parser.add_argument(
            "--role", dest="exec_role",
            help="Role/permission-set (defaults to context)",
        )
        parser.add_argument(
            "--region", dest="exec_region",
            help="Region (defaults to context)",
        )
        parser.add_argument("cmd", nargs="+", help="Command to execute")

    def execute(self, args) -> int:
        ctx = load_context()

        # --org flag bypasses active context entirely
        org_name = getattr(args, "exec_org", None) or (
            ctx.get("current_org", "") or ctx.get("org", "") if ctx else ""
        )
        account = getattr(args, "exec_account", None) or (ctx.get("account", "") if ctx else "")
        role    = getattr(args, "exec_role", None)    or (ctx.get("role", "")    if ctx else "")
        region  = getattr(args, "exec_region", None)  or (ctx.get("region", "")  if ctx else "")

        if not org_name:
            self.console.print(
                "[red]No org specified and no active context.[/]\n"
                "Run [bold]cloudctl switch <org>[/bold] first, or use: "
                "[bold]cloudctl exec --org <org> -- <command>[/bold]"
            )
            return 1

        # When --org is given without --account/--role, do interactive selection
        if getattr(args, "exec_org", None) and not all([account, role]):
            try:
                org_data = get_org(org_name)
            except Exception:
                self.console.print(f"[red]Org '{org_name}' not found in config.[/]")
                return 1
            import cloudctl.interactive as _interactive
            account, role, region = _interactive.run_interactive_use(
                org_data, account or None, role or None, region or None
            )
            if not all([account, role, region]):
                return 1

        try:
            org_data = get_org(org_name)
        except Exception:
            self.console.print(f"[red]Org '{org_name}' not found in config.[/]")
            return 1

        from cloudctl.providers import get_provider

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
