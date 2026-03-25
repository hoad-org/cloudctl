import os
import subprocess
from awsctl.commands.base import BaseCommand
from awsctl.context_manager import load_context
from awsctl.sso_cache import load_active_sso_token
from awsctl.config import get_org


class ExecCommand(BaseCommand):
    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("exec", help="Run a command in context")
        parser.add_argument("cmd", nargs="+", help="Command to execute")

    def execute(self, args) -> int:
        ctx = load_context()
        if not ctx:
            self.console.print("[red]No active context. Run 'awsctl switch' first.[/]")
            return 1

        org_data = get_org(ctx["org"])
        # Validate session exists
        load_active_sso_token(org_data, raise_error=True)

        env = os.environ.copy()
        env["AWS_PROFILE"] = f"awsctl-{ctx['account']}-{ctx['role']}"
        env["AWS_REGION"] = ctx["region"]

        for var in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]:
            env.pop(var, None)

        try:
            result = subprocess.run(args.cmd, env=env)
            return result.returncode
        except FileNotFoundError:
            self.console.print(f"[red]Executable not found:[/] {args.cmd[0]}")
            return 127
