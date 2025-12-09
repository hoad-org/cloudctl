# SPDX-License-Identifier: MIT
"""
CLI glue: `awsctl accounts` and `awsctl roles`
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from rich.markup import escape
from rich.table import Table

from awsctl.utils import console, stdout_console

from .accounts import list_accounts, list_roles
from .sso_cache import OrgRef


def _org_from_cfg(cfg: Dict[str, Any], name: Optional[str]) -> Any:
    if not cfg.get("orgs"):
        raise SystemExit("No orgs configured. Run `awsctl setup`.")
    if name:
        for o in cfg["orgs"]:
            if o.get("name") == name:
                return o
        raise SystemExit(f"Org not found: {name}")
    return cfg["orgs"][0]


def cmd_accounts(cfg: Dict[str, Any], org: Optional[str], as_json: bool) -> int:
    o = _org_from_cfg(cfg, org)
    ref = OrgRef(o["name"], o["sso_start_url"], o["sso_region"])

    accts = list_accounts(ref)

    if as_json:
        print(json.dumps({"accountList": [a.__dict__ for a in accts]}, indent=2))
        return 0

    if not accts:
        console.print("[warning]No accounts found.[/]")
        return 0

    table = Table(title=f"Accounts in {ref.name}", show_header=True)
    table.add_column("Account Name", style="green")
    table.add_column("Account ID", style="cyan")
    table.add_column("Email", style="dim")

    for a in accts:
        table.add_row(escape(a.account_name), escape(a.account_id), escape(a.email))

    stdout_console.print(table)
    return 0


def cmd_roles(
    cfg: Dict[str, Any],
    org: Optional[str],
    account_id: str,
    as_json: bool,
) -> int:
    o = _org_from_cfg(cfg, org)
    ref = OrgRef(o["name"], o["sso_start_url"], o["sso_region"])

    roles = list_roles(ref, account_id)

    if as_json:
        print(json.dumps({"roles": roles}, indent=2))
        return 0

    if not roles:
        console.print("[warning]No roles found.[/]")
        return 0

    table = Table(title=f"Roles in {account_id}", show_header=True)
    table.add_column("Role Name", style="yellow")
    table.add_column("Alias", style="dim cyan")

    # [FIX] PYBH-0055: Apply aliases for display
    aliases = o.get("role_aliases", {})

    for r in roles:
        alias = ""
        for pattern, replacement in aliases.items():
            if re.match(pattern, r):
                alias = replacement
                break

        table.add_row(escape(r), escape(alias))

    stdout_console.print(table)
    return 0
