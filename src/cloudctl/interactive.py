from typing import Any, Dict, List, Optional, Tuple

from InquirerPy import inquirer

from .sso_cache import load_active_sso_token

# Fallback region list shown when an org has no allowed_regions configured.
_COMMON_REGIONS = [
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
    # Azure
    "eastus",
    "eastus2",
    "westus",
    "westus2",
    "westeurope",
    "northeurope",
    "southeastasia",
    "eastasia",
    # GCP
    "us-central1",
    "us-east1",
    "us-west1",
    "europe-west1",
    "europe-west2",
    "asia-east1",
]

# ---- module-level re-exports so tests can monkeypatch these names ----
load_active_sso_token = load_active_sso_token

# _active_org is set by run_interactive_use before calling the seam functions.
# Tests replace list_accounts / list_roles entirely via monkeypatching,
# so _active_org is only relevant in production code paths.
_active_org: Optional[Dict[str, Any]] = None


def list_accounts(token: Any) -> List[Any]:
    """
    Patchable seam — return accounts for the current active org.
    Production code routes through the CloudProvider via _active_org.
    """
    if _active_org is None:
        return []
    from .providers import get_provider

    provider = get_provider(_active_org)
    return provider.list_accounts(_active_org, token)


def list_roles(token: Any, account_id: str) -> List[str]:
    """
    Patchable seam — return roles for the given account.
    Production code routes through the CloudProvider via _active_org.
    """
    if _active_org is None:
        return []
    from .providers import get_provider

    provider = get_provider(_active_org)
    return provider.list_roles(_active_org, token, account_id)


# ----------------------------------------------------------------------


def select_account(
    accounts: List[Any], org_name: Optional[str] = None
) -> Optional[str]:
    """
    Fuzzy-search picker for accounts/subscriptions/projects.
    Accepts {id, name} dicts or Account objects with .id/.name.
    Returns the account id string.
    """
    import cloudctl.utils as _utils

    def _id(a):
        return a.get("id") if isinstance(a, dict) else getattr(a, "id", None)

    def _name(a):
        return a.get("name") if isinstance(a, dict) else getattr(a, "name", None)

    choices = [{"name": f"{_name(a)} ({_id(a)})", "value": _id(a)} for a in accounts]
    _utils.console.print("Available Accounts")
    return inquirer.fuzzy(message="Select Account:", choices=choices).execute()


def select_role(org_data: Dict[str, Any], roles: List[Any]) -> Optional[str]:
    """Role / permission-set picker with preferred-roles ordering."""
    from .guardrails import sort_roles

    role_names = [
        (
            r.get("roleName")
            if isinstance(r, dict)
            else (r.roleName if hasattr(r, "roleName") else r)
        )
        for r in roles
    ]
    sorted_roles = sort_roles(org_data, role_names)
    return inquirer.select(message="Select Role:", choices=sorted_roles).execute()


def select_region(allowed: List[str], default: Optional[str] = None) -> Optional[str]:
    """Region picker. Returns the single item immediately when only one is allowed."""
    if allowed and len(allowed) == 1:
        return allowed[0]
    return inquirer.select(
        message="Select Region:", choices=allowed, default=default
    ).execute()


def run_interactive_use(
    org_or_name: Any,
    account: Optional[str] = None,
    role: Optional[str] = None,
    region: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Full interactive selection flow: account → role → region.

    Accepts either an org name string (looked up from config) or an org
    config dict.  Uses module-level list_accounts / list_roles so that
    tests can monkeypatch them without touching the provider layer.

    Raises RuntimeError on empty account list or provider API failures.
    Returns (account_id, role_name, region).
    """
    global _active_org

    # Resolve org dict.
    # Use core.load_orgs_config() so tests that monkeypatch
    # cloudctl.core.load_orgs_config see the right data.
    if isinstance(org_or_name, str):
        import cloudctl.core as _core

        cfg = _core.load_orgs_config()
        orgs = cfg.get("orgs", []) if isinstance(cfg, dict) else cfg
        org_data = next((o for o in orgs if o.get("name") == org_or_name), None)
        if org_data is None:
            raise ValueError(
                f"Organization '{org_or_name}' not found in configuration."
            )
    else:
        org_data = org_or_name

    _active_org = org_data
    try:
        return _run(org_data, account, role, region)
    finally:
        _active_org = None


def _run(
    org_data: Dict[str, Any],
    account: Optional[str],
    role: Optional[str],
    region: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Inner implementation separated so the finally-block in run_interactive_use fires."""
    import cloudctl.utils as _utils

    token = load_active_sso_token(org_data)
    if not token:
        org_name = org_data.get("name", "")
        _utils.console.print(
            f"[yellow]No active session for org '{org_name}'.[/] " "Attempting login..."
        )
        # Auto-login: import core lazily to avoid circular imports
        import cloudctl.core as _core

        rc = _core.cmd_login(org_name, force=False)
        if rc != 0:
            _utils.console.print(
                f"[red]Login failed for org '{org_name}'.[/] "
                "Run [bold]cloudctl login <org>[/bold] manually."
            )
            return None, None, None
        token = load_active_sso_token(org_data)
        if not token:
            _utils.console.print(
                f"[red]Still no session after login for '{org_name}'.[/]"
            )
            return None, None, None

    # --- Account selection ---
    if not account:
        try:
            accounts = list_accounts(token)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        if not accounts:
            raise RuntimeError(f"No accounts found for org '{org_data.get('name')}'")
        account = select_account(accounts, org_data.get("name"))
    if not account:
        return None, None, None

    # --- Role selection ---
    if not role:
        try:
            roles = list_roles(token, account)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        if not roles:
            _utils.console.print("[red]No roles found for this account.[/]")
            return None, None, None
        role = select_role(org_data, roles)
    if not role:
        return None, None, None

    # --- Region selection ---
    if not region:
        allowed = org_data.get("allowed_regions", [])
        default = org_data.get("default_region")
        if len(allowed) == 1:
            region = allowed[0]
        elif allowed:
            region = select_region(allowed, default)
        elif default:
            # No allowlist but a default is configured — use it directly
            region = default
        else:
            # No allowlist, no default — fall back to partition-specific region list
            from .schema import AWS_PARTITIONS

            partition = org_data.get("partition", "aws")
            provider = org_data.get("provider", "aws")
            if provider == "aws" and partition in AWS_PARTITIONS:
                fallback = AWS_PARTITIONS[partition]["regions"]
            else:
                fallback = _COMMON_REGIONS
            region = select_region(fallback, None)
    if not region:
        return None, None, None

    if org_data.get("allowed_regions"):
        from .guardrails import validate_region

        validate_region(org_data, region)

    return account, role, region
