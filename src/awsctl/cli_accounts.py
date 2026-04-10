"""
awsctl.cli_accounts — account/role listing helpers.

These functions are called by the CLI dispatcher and also by tests directly.
"""

import json
import sys
from typing import Any, Dict, List

from rich.table import Table

from . import accounts as _accounts_mod
from . import utils

# Patchable console reference (tests monkeypatch this)
stdout_console = utils.stdout_console

# Re-export so tests can monkeypatch awsctl.cli_accounts.list_accounts
list_accounts = _accounts_mod.list_accounts


def list_roles(org_data: Any, account_id: str) -> List[str]:
    """List roles for a given account."""
    from .sso_cache import OrgRef, load_active_sso_token

    if isinstance(org_data, dict):
        token = load_active_sso_token(
            OrgRef(
                org_data.get("name", ""),
                org_data.get("sso_start_url", ""),
                org_data.get("sso_region", ""),
            )
        )
        from .providers import get_provider

        provider = get_provider(org_data)
        if not token:
            return []
        return provider.list_roles(org_data, account_id, token)
    return []


def _org_from_cfg(cfg: Dict[str, Any], org_name: str) -> Dict[str, Any]:
    """
    Extract org dict from cfg by name. Raises SystemExit if not found.
    """
    orgs = cfg.get("orgs", []) if isinstance(cfg, dict) else []
    for org in orgs:
        if org.get("name") == org_name:
            return org
    sys.exit(1)


def cmd_accounts(
    cfg: Dict[str, Any],
    org_name: str,
    as_json: bool = False,
) -> int:
    """
    List accounts for org_name.

    cfg    - raw config dict ({"orgs": [...]})
    org_name - org slug
    as_json  - if True, print JSON to stdout; else print Rich table via stdout_console
    """
    org = _org_from_cfg(cfg, org_name)
    acct_list = list_accounts(org)

    if as_json:
        data = {
            "accountList": [
                {"accountId": a.id, "accountName": a.name, "email": a.email}
                for a in acct_list
            ]
        }
        print(json.dumps(data))
        return 0

    if not acct_list:
        stdout_console.print("[yellow]No accounts found[/]")
        return 0

    table = Table(title=f"Accounts for {org_name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    for a in acct_list:
        table.add_row(a.id, a.name)

    stdout_console.print(table)
    return 0


def cmd_roles(
    cfg: Dict[str, Any],
    org_name: str,
    account_id: str,
    as_json: bool = False,
) -> int:
    """
    List roles for account_id within org_name.
    """
    org = _org_from_cfg(cfg, org_name)
    roles = list_roles(org, account_id)

    if as_json:
        data = {"roles": roles}
        print(json.dumps(data))
        return 0

    if not roles:
        stdout_console.print("[yellow]No roles found[/]")
        return 0

    table = Table(title=f"Roles for {account_id} in {org_name}")
    table.add_column("Role", style="cyan")
    for r in roles:
        table.add_row(r)

    stdout_console.print(table)
    return 0
