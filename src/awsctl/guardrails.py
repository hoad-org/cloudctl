# file: src/awsctl/guardrails.py
# SPDX-License-Identifier: MIT
"""
awsctl.guardrails
-----------------
Enforcement logic for organization policies defined in orgs.yaml.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from awsctl.utils import console


def validate_region(org_config: Dict[str, Any], region: str) -> None:
    """
    Enforce 'allowed_regions' policy.
    Terminates execution if the region is not allowed.
    """
    allowed = org_config.get("allowed_regions")
    # If no list is defined, all regions are allowed.
    if not allowed:
        return

    if region not in allowed:
        console.print(
            f"[bold red]✗ Guardrail Violation[/]\n"
            f"Region [yellow]'{region}'[/] is not permitted for org [cyan]'{org_config.get('name')}'[/].",
        )
        console.print(f"Allowed regions: [green]{', '.join(allowed)}[/]")
        sys.exit(1)


def sort_roles(org_config: Dict[str, Any], roles: List[str]) -> List[str]:
    """
    Sort roles based on 'preferred_roles' policy.
    Preferred roles appear first (in order), followed by the rest alphabetically.
    """
    preferred = org_config.get("preferred_roles") or []

    # Split roles into two buckets
    is_preferred = set(preferred)

    # 1. Extract preferred roles that actually exist in the list (preserving config order)
    top = [r for r in preferred if r in roles]

    # 2. Sort the remaining roles alphabetically
    bottom = sorted([r for r in roles if r not in is_preferred])

    return top + bottom
