# file: src/awsctl/interactive.py
# SPDX-License-Identifier: MIT
"""
awsctl.interactive
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, cast

import InquirerPy.inquirer
from rich.table import Table

from awsctl import context_manager, core, guardrails
from awsctl.accounts import Account, list_accounts, list_roles
from awsctl.sso_cache import OrgRef
from awsctl.utils import ForceStderr, console


def _print_account_table(accounts: List[Account]) -> None:
    table = Table(
        title="Available Accounts", show_header=True, header_style="bold cyan"
    )
    table.add_column("Account Name", style="green")
    table.add_column("Account ID", style="cyan")

    for a in accounts:
        table.add_row(a.account_name, a.account_id)

    console.print(table)
    console.print("")


def select_account(accounts: List[Account], org_name: str) -> str:
    _print_account_table(accounts)

    # Feature #1: Smart History Injection
    history = context_manager.get_history()
    recent_ids = []

    # Filter history for current org
    for h in history:
        if h.get("org") == org_name:
            recent_ids.append(h.get("account"))

    choices: List[Any] = []
    # 1. Add Recents
    seen_ids = set()
    for rid in recent_ids:
        # Find matching account object
        match = next((a for a in accounts if a.account_id == rid), None)
        if match and rid not in seen_ids:
            choices.append(
                {
                    "name": f"🕒 {match.account_name} ({match.account_id})",
                    "value": match.account_id,
                }
            )
            seen_ids.add(rid)

    # [FIX] Removed Separator: InquirerPy fuzzy prompt does not support them.
    # The clock icon in the name is enough visual distinction.

    # 2. Add remaining accounts
    for a in accounts:
        if a.account_id not in seen_ids:
            choices.append(
                {"name": f"{a.account_name} ({a.account_id})", "value": a.account_id}
            )

    with ForceStderr():
        return str(
            InquirerPy.inquirer.fuzzy(  # type: ignore
                message="Select Account:",
                choices=choices,
                match_exact=True,
            ).execute()
        )


def _apply_role_aliases(org: Dict[str, Any], roles: List[str]) -> List[Dict[str, str]]:
    aliases = org.get("role_aliases", {})
    output = []
    seen_names = set()

    for r in roles:
        display_name = r
        for pattern, replacement in aliases.items():
            if re.search(pattern, r):
                display_name = replacement
                break

        if display_name in seen_names:
            display_name = f"{display_name} ({r})"

        seen_names.add(display_name)
        output.append({"name": display_name, "value": r})
    return output


def select_role(org: Dict[str, Any], roles: List[str]) -> str:
    choices = _apply_role_aliases(org, roles)

    with ForceStderr():
        return str(
            InquirerPy.inquirer.fuzzy(  # type: ignore
                message="Select Role:",
                choices=choices,
                match_exact=True,
            ).execute()
        )


def select_region(allowed: List[str], default: str) -> str:
    if allowed is not None and len(allowed) == 0:
        raise RuntimeError("No regions allowed for this organization.")

    if allowed and len(allowed) == 1 and allowed[0] != "*":
        return allowed[0]

    options = allowed or []

    if allowed is None or "*" in allowed:
        options = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-central-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
        ]

    display_options = list(options)

    if default:
        if default in display_options:
            display_options.remove(default)
            display_options.insert(0, default)
        elif allowed is None or "*" in allowed:
            display_options.insert(0, default)

    with ForceStderr():
        return str(
            InquirerPy.inquirer.select(  # type: ignore
                message="Select Region:",
                choices=display_options,
                default=default if default in display_options else None,
            ).execute()
        )


def run_interactive_use(
    org_name: str,
    preselected_role: Optional[str] = None,
    preselected_region: Optional[str] = None,
) -> Tuple[str, str, str]:
    cfg: Dict[str, Any] = core.load_orgs_config()

    org: Optional[Dict[str, Any]] = None
    for o in cfg.get("orgs", []):
        if o["name"] == org_name:
            org = o
            break

    if not org:
        raise RuntimeError(f"Org '{org_name}' not found in config.")

    # Feature #2: Check version before allowing interactive use
    guardrails.check_min_version(org)

    ref = OrgRef(org["name"], org["sso_start_url"], org["sso_region"])

    with console.status("[dim]Fetching accounts from AWS SSO...[/]"):
        try:
            accts = list_accounts(ref)
        except Exception as e:
            raise RuntimeError(f"Error listing accounts: {e}") from e

    if not accts:
        raise RuntimeError("No accounts found.")

    # Pass org_name to enable smart history
    account_id = select_account(accts, org_name)

    if preselected_role:
        role_name = preselected_role
    else:
        with console.status(f"[dim]Fetching roles for account {account_id}...[/]"):
            try:
                roles = list_roles(ref, account_id)
            except Exception as e:
                raise RuntimeError(f"Error listing roles: {e}") from e

        if not roles:
            raise RuntimeError("No roles found for this account.")

        roles = guardrails.sort_roles(org, roles)
        role_name = select_role(org, roles)

    # Feature #3: Break Glass Check
    guardrails.check_break_glass(org, role_name)

    if preselected_region:
        region = preselected_region
    else:
        default_reg = org.get("default_region", "us-east-1")
        allowed_reg = cast(List[str], org.get("allowed_regions"))
        region = select_region(allowed_reg, default_reg)

    return account_id, role_name, region
