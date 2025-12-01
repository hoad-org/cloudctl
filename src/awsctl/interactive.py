# file: src/awsctl/interactive.py
# SPDX-License-Identifier: MIT
"""
awsctl.interactive
------------------
Interactive TUI for selecting accounts and roles using fuzzy search.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

import InquirerPy.inquirer
from rich.table import Table

from awsctl import core, guardrails
from awsctl.accounts import Account, list_accounts, list_roles
from awsctl.sso_cache import OrgRef
from awsctl.utils import console


# Helper to force menus to stderr so they remain visible during eval $(...)
class ForceStderr:
    def __enter__(self) -> ForceStderr:
        self.original_stdout = sys.stdout
        sys.stdout = sys.stderr
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        sys.stdout = self.original_stdout


def _print_account_table(accounts: List[Account]) -> None:
    """Display accounts as a table before selection (prints to stderr via console)."""
    table = Table(
        title="Available Accounts", show_header=True, header_style="bold cyan"
    )
    table.add_column("Account Name", style="green")
    table.add_column("Account ID", style="cyan")

    for a in accounts:
        table.add_row(a.account_name, a.account_id)

    console.print(table)
    console.print("")  # Spacer


def select_account(accounts: List[Account]) -> str:
    """Prompt user to select an account from a list."""
    _print_account_table(accounts)

    choices = [
        {"name": f"{a.account_name} ({a.account_id})", "value": a.account_id}
        for a in accounts
    ]
    with ForceStderr():
        return str(
            InquirerPy.inquirer.fuzzy(  # type: ignore[attr-defined]
                message="Select Account:",
                choices=choices,
                match_exact=True,
            ).execute()
        )


def select_role(roles: List[str]) -> str:
    """Prompt user to select a role."""
    with ForceStderr():
        return str(
            InquirerPy.inquirer.fuzzy(  # type: ignore[attr-defined]
                message="Select Role:",
                choices=roles,
                match_exact=True,
            ).execute()
        )


def select_region(allowed: List[str], default: str) -> str:
    """
    Prompt for region if multiple are allowed.
    Auto-select if only one is allowed.
    """
    if allowed and len(allowed) == 1:
        return allowed[0]

    options = (
        allowed
        if allowed
        else [
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
    )

    # Make a copy to avoid modifying the passed list if it's mutable
    display_options = list(options)

    # Ensure default is at the top if present
    if default in display_options:
        display_options.remove(default)
        display_options.insert(0, default)
    elif default:
        # If default isn't in the options (e.g. not in allowed list),
        # we shouldn't insert it blindly, but we keep it for now
        # if the list was generated from defaults.
        if not allowed:
            display_options.insert(0, default)

    with ForceStderr():
        return str(
            InquirerPy.inquirer.select(  # type: ignore[attr-defined]
                message="Select Region:",
                choices=display_options,
                default=default,
            ).execute()
        )


def run_interactive_use(
    org_name: str,
) -> Tuple[str, str, str]:
    """
    Orchestrates the interactive selection flow.
    Returns (account_id, role_name, region).
    Raises SystemExit or RuntimeError on failure.
    """
    cfg: Dict[str, Any] = core.load_orgs_config()

    org: Optional[Dict[str, Any]] = None
    for o in cfg.get("orgs", []):
        if o["name"] == org_name:
            org = o
            break

    if not org:
        console.print(f"[error]Error: Org '{org_name}' not found in config.[/]")
        sys.exit(1)

    ref = OrgRef(org["name"], org["sso_start_url"], org["sso_region"])

    with console.status("[dim]Fetching accounts from AWS SSO...[/]"):
        try:
            accts = list_accounts(ref)
        except Exception as e:
            console.print(f"[error]Error listing accounts: {e}[/]")
            sys.exit(1)

    if not accts:
        console.print("[warning]No accounts found.[/]")
        sys.exit(1)

    account_id = select_account(accts)

    with console.status(f"[dim]Fetching roles for account {account_id}...[/]"):
        try:
            roles = list_roles(ref, account_id)
        except Exception as e:
            console.print(f"[error]Error listing roles: {e}[/]")
            sys.exit(1)

    if not roles:
        console.print("[warning]No roles found for this account.[/]")
        sys.exit(1)

    roles = guardrails.sort_roles(org, roles)
    role_name = select_role(roles)

    default_reg = org.get("default_region", "us-east-1")
    allowed_reg = org.get("allowed_regions") or []
    region = select_region(allowed_reg, default_reg)

    return account_id, role_name, region
