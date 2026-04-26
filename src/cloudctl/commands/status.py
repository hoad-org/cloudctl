# src/cloudctl/commands/status.py
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import load_context
from rich.table import Table


class StatusCommand(BaseCommand):
    """Displays the current active AWS context."""

    def configure_parser(self, subparsers):
        subparsers.add_parser("status", help="Show current AWS context")

    def execute(self, args) -> int:
        ctx = load_context()
        if not ctx:
            self.console.print("[yellow]No active context set.[/]")
            return 0

        table = Table(title="Current cloudctl Context")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Organization", ctx.get("org"))
        table.add_row("Account ID", ctx.get("account"))
        table.add_row("Role Name", ctx.get("role"))
        table.add_row("Region", ctx.get("region"))
        table.add_row("AWS Profile", f"cloudctl-{ctx.get('account')}-{ctx.get('role')}")

        self.console.print(table)
        return 0
