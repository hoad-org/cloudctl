from typing import Any, Dict, List, Optional
from InquirerPy import inquirer
from .accounts import list_accounts
from .utils import console

list_accounts = list_accounts


def select_account(
    accounts: List[Any], org_name: Optional[str] = None
) -> Optional[str]:
    def _v(a, k):
        return a.get(k) if isinstance(a, dict) else getattr(a, k, None)

    choices = [
        {
            "name": f"{_v(a, 'accountName')} ({_v(a, 'accountId')})",
            "value": _v(a, "accountId"),
        }
        for a in accounts
    ]
    console.print("Available Accounts")
    return inquirer.fuzzy(message="Select Account:", choices=choices).execute()


def select_role(org_data: Dict[str, Any], roles: List[Any]) -> Optional[str]:
    from .guardrails import sort_roles

    role_names = [
        r.get("roleName") if isinstance(r, dict) else r.roleName for r in roles
    ]
    sorted_roles = sort_roles(role_names, org_data.get("preferred_roles", []))
    return inquirer.select(message="Select Role:", choices=sorted_roles).execute()


def select_region(allowed: List[str], default: Optional[str] = None) -> Optional[str]:
    return inquirer.select(
        message="Select Region:", choices=allowed, default=default
    ).execute()
