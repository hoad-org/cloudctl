# src/awsctl/commands/switch.py
from awsctl.commands.base import BaseCommand
from awsctl.config import get_org
from awsctl.use_exports import emit_exports
from awsctl.context_manager import save_context


class SwitchCommand(BaseCommand):
    """Interactive command to switch cloud accounts, roles, and regions."""

    def configure_parser(self, subparsers):
        parser = subparsers.add_parser(
            "switch", help="Switch cloud context interactively"
        )
        parser.add_argument("org", nargs="?", help="Organization name")
        parser.add_argument("--account", help="Specific account ID")
        parser.add_argument("--role", help="Specific role name")
        parser.add_argument("--region", help="Specific region")

    def execute(self, args) -> int:
        org_name = getattr(args, "org", None)
        if not org_name:
            from awsctl.config import load_config

            cfg = load_config()
            orgs = [o["name"] for o in cfg.get("orgs", [])]
            if not orgs:
                self.console.print(
                    "[red]No organizations configured. Run 'awsctl init'[/]"
                )
                return 1
            if len(orgs) == 1:
                org_name = orgs[0]
            else:
                from InquirerPy import inquirer

                org_name = inquirer.select(
                    message="Select Organization:", choices=orgs
                ).execute()

        org_data = get_org(org_name)

        # Interactive selection — works for AWS, Azure, and GCP
        # Import lazily so tests can patch awsctl.interactive.run_interactive_use
        import awsctl.interactive as _interactive

        account, role, region = _interactive.run_interactive_use(
            org_data,
            getattr(args, "account", None),
            getattr(args, "role", None),
            getattr(args, "region", None),
        )

        if not all([account, role, region]):
            return 1

        # Emit 'export K=V' lines to stdout so the shell wrapper can source them
        export_str = emit_exports(org_data, account, role, region)

        if hasattr(args, "hook_output") and args.hook_output:
            with open(args.hook_output, "w") as f:
                f.write(export_str)
        else:
            print(export_str)

        # Persist context (stores provider field too)
        save_context(org_name, account, role, region)

        self.console.print(
            f"[bold green]✔ Switched to {account} / {role} / {region}[/]"
        )
        return 0
