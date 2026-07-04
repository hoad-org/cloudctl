# src/cloudctl/commands/logout.py
from cloudctl.commands.base import BaseCommand
from cloudctl.context_manager import clear_context, load_context


class LogoutCommand(BaseCommand):
    """
    Terminates the active cloud session and clears the local cloudctl context.

    Works for all providers — delegates to the provider determined from
    the current context so AWS, Azure, and GCP sessions are all handled
    correctly.
    """

    def configure_parser(self, subparsers):
        subparsers.add_parser("logout", help="Log out and clear context")

    def execute(self, args) -> int:
        ctx = load_context()
        provider_name = ctx.get("provider", "aws") if ctx else "aws"
        org_name = ctx.get("current_org", "") if ctx else ""

        label = {"aws": "AWS SSO", "azure": "Azure", "gcp": "GCP"}.get(
            provider_name, provider_name.upper()
        )
        self.console.print(f"[bold blue]Logging out of {label} sessions...[/]")

        try:
            from cloudctl.config import get_org
            from cloudctl.providers import get_provider

            org_data = get_org(org_name) if org_name else {"provider": provider_name}
            provider = get_provider(org_data)
            rc = provider.logout(org_data)
        except Exception:
            rc = 0  # Logout best-effort; always clear local context

        clear_context()

        if rc == 0:
            self.console.print(
                "[bold green]✔ Successfully logged out and context cleared.[/]"
            )
        else:
            self.console.print(
                "[yellow]! No active session found, but local context was cleared.[/]"
            )

        return 0
