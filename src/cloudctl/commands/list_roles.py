"""
cloudctl list-roles — list the IAM roles the current SSO user can assume.

For AWS IAM Identity Center (SSO), the set of assumable roles is per account and
is returned by `aws sso list-account-roles` using the cached SSO access token —
NOT by enumerating IAM roles with ambient credentials (which an agent/SSO session
does not have). This command therefore loads the active SSO token and asks the
provider for the assumable roles in each account (or a single --account).
"""

import json
from typing import Any, Dict, List, Optional

from rich.table import Table

from cloudctl.commands.base import BaseCommand
from cloudctl import exit_codes


class _OrgNotFound(Exception):
    """Raised when the org lookup fails — mapped to a clean NOT_FOUND (3)."""


class ListRolesCommand(BaseCommand):
    """List assumable IAM roles per account, via the active SSO session."""

    def configure_parser(self, subparsers: Any) -> None:
        lrp = subparsers.add_parser(
            "list-roles", help="List the IAM roles you can assume (per account)"
        )
        lrp.add_argument(
            "org", nargs="?", help="Organization name (optional if a context is set)"
        )
        lrp.add_argument(
            "--org",
            dest="org_flag",
            help="Organization name (flag form; same as positional)",
        )
        lrp.add_argument("--account", help="Limit to a single account ID")
        lrp.add_argument(
            "--assigned",
            action="store_true",
            help="(SSO only ever lists assumable roles; kept for compatibility)",
        )
        lrp.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def _resolve_org(self, args: Any) -> str:
        from cloudctl.context_manager import load_context

        if getattr(args, "org", None):
            return args.org
        if getattr(args, "org_flag", None):
            return args.org_flag
        ctx = load_context() or {}
        org = ctx.get("org") or ctx.get("current_org")
        if not org:
            raise RuntimeError(
                "No organization given and no active context. "
                "Pass an org (e.g. 'cloudctl list-roles bt-avm') or run 'cloudctl switch <org>'."
            )
        return org

    def roles_by_account(
        self, org_name: str, account: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Return {account_id: {"name": str, "roles": [role_name, ...]}}.

        Provider-aware dispatch: only AWS gates on an SSO access token (its
        list_roles needs one). GCP/Azure have no SSO-token concept — gating them
        on `load_active_sso_token` gave every non-AWS org a bogus
        "No active SSO session" error and never reached provider.list_roles. For
        non-AWS providers we skip the SSO-token gate and pass token=None
        (mirroring how commands/accounts.py dispatches).
        """
        from cloudctl.accounts import get_account_list
        from cloudctl.config import get_org
        from cloudctl.providers import get_provider
        from cloudctl.providers.base import ProviderCredentialError
        from cloudctl.sso_cache import OrgRef, load_active_sso_token

        # A bad org name is a user typo, not a bug — surface it as NOT_FOUND (3)
        # with a clean message rather than the generic "UNEXPECTED ERROR".
        try:
            org_data = get_org(org_name)
        except Exception as e:
            raise _OrgNotFound(f"Organization '{org_name}' not found: {e}")

        provider_name = (
            org_data.get("provider", "aws") if isinstance(org_data, dict) else "aws"
        )
        provider = get_provider(org_data)

        # Token acquisition is AWS-only. Non-AWS providers do not use an SSO
        # access token; passing None is correct (see gcp/azure list_roles).
        token: Any = None
        if provider_name == "aws":
            token = load_active_sso_token(
                OrgRef(
                    org_data.get("name", org_name),
                    org_data.get("sso_start_url", ""),
                    org_data.get("sso_region", ""),
                )
            )
            if not token:
                raise RuntimeError(
                    f"No active SSO session for '{org_name}'. "
                    f"Run: cloudctl login {org_name}"
                )

        if account:
            accounts: List[Dict[str, str]] = [{"Id": account, "Name": account}]
        else:
            # list_accounts may raise ProviderCredentialError (auth/denied) —
            # let it propagate so execute() maps .code/.message to an exit code.
            accounts = get_account_list(org_data)

        out: Dict[str, Dict[str, Any]] = {}
        for acc in accounts:
            acc_id = acc.get("Id") or acc.get("id")
            if not acc_id:
                continue
            try:
                roles = provider.list_roles(org_data, token, acc_id)
            except ProviderCredentialError:
                # Re-raise so execute() renders a faithful message + exit code.
                raise
            out[acc_id] = {
                "name": acc.get("Name") or acc.get("name") or "",
                "roles": roles,
            }
        return out

    def execute(self, args: Any) -> int:
        from cloudctl.providers.base import ProviderCredentialError

        as_json = getattr(args, "format", "text") == "json"
        try:
            org_name = self._resolve_org(args)
            data = self.roles_by_account(org_name, getattr(args, "account", None))
        except _OrgNotFound as e:
            # Clean, actionable not-found — honor --format (json → stdout).
            if as_json:
                print(json.dumps({"error": str(e), "code": exit_codes.NOT_FOUND}))
            else:
                self.console.print(f"[red]✗ {e}[/]")
            return exit_codes.NOT_FOUND
        except ProviderCredentialError as e:
            # FAITHFUL ERRORS: the provider classified the real cause (auth /
            # denied / not-found) — map its code + message to a clean message and
            # that exit code, json-aware. Never flatten to a generic error.
            if as_json:
                print(json.dumps({"error": e.message, "code": e.code}))
            else:
                self.console.print(f"[red]✗ {e.message}[/]")
            return e.code
        except Exception as e:
            self.console.print(f"[red]✗ Error:[/] {e}")
            return 1

        if as_json:
            print(
                json.dumps(
                    {
                        # Unified org-identifier key across read commands: `org`.
                        "org": org_name,
                        # This command lists roles per account: the top-level
                        # collection key is `roles` (each entry carries its
                        # account id/name plus that account's role list).
                        "roles": [
                            {"id": acc_id, "name": v["name"], "roles": v["roles"]}
                            for acc_id, v in data.items()
                        ],
                    },
                    indent=2,
                )
            )
            return 0

        table = Table(title=f"Assumable roles in {org_name}")
        table.add_column("Account ID", style="cyan")
        table.add_column("Account Name", style="green")
        table.add_column("Roles", style="magenta")
        total = 0
        for acc_id, v in sorted(data.items(), key=lambda kv: kv[1]["name"]):
            table.add_row(acc_id, v["name"], ", ".join(v["roles"]) or "—")
            total += len(v["roles"])
        self.console.print(table)
        self.console.print(f"[green]✓[/] {total} role(s) across {len(data)} account(s)")
        return 0
