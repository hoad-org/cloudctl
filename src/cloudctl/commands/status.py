# src/cloudctl/commands/status.py
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import load_context
from cloudctl.output_formatter import OutputFormatter
from rich.table import Table


class StatusCommand(BaseCommand):
    """Displays the current active AWS context."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser("status", help="Show current AWS context")
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (default: table)",
        )

    def execute(self, args) -> int:
        ctx = load_context()
        if not ctx:
            if hasattr(args, "format") and args.format == "json":
                formatter = OutputFormatter()
                formatter.success_json(
                    {
                        "organization": None,
                        "account": None,
                        "role": None,
                        "region": None,
                        "provider": None,
                        "status": "no_context",
                    }
                )
            else:
                self.console.print("[yellow]No active context set.[/]")
            return 0

        # Prepare context data
        context_data = {
            "organization": ctx.get("org"),
            "account": ctx.get("account"),
            "role": ctx.get("role"),
            "region": ctx.get("region"),
            "provider": ctx.get("provider", "aws"),
            "status": "active",
        }

        # Check if JSON format is requested
        if hasattr(args, "format") and args.format == "json":
            formatter = OutputFormatter()
            formatter.success_json(context_data)
            return 0

        # Default: table format
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
