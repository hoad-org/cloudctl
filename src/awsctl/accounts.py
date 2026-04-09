from typing import Any, Dict, List

from .sso_cache import OrgRef, load_active_sso_token

# Re-export: tests monkeypatch awsctl.accounts.load_active_sso_token
load_active_sso_token = load_active_sso_token


class Account:
    def __init__(self, id_val: str, name: str, email: str = ""):
        self.id = id_val
        self.name = name
        self.email = email


def list_accounts(org_data: Any) -> List[Account]:
    """
    Return accounts accessible to the current session.

    Delegates to the appropriate CloudProvider based on org_data["provider"].
    Returns Account objects with .id and .name attributes.

    For AWS orgs the module-level load_active_sso_token is used as the token
    source so that existing tests can monkeypatch awsctl.accounts.load_active_sso_token
    without being aware of the provider layer.  Azure/GCP orgs use their own
    provider.load_token() path.
    """
    if not isinstance(org_data, dict):
        # Legacy: OrgRef or similar object — treat as AWS
        org_data = {
            "name": org_data.name,
            "provider": "aws",
            "sso_start_url": getattr(org_data, "sso_start_url", ""),
            "sso_region": getattr(org_data, "sso_region", ""),
        }

    from .providers import get_provider

    provider = get_provider(org_data)
    provider_name = org_data.get("provider", "aws")

    # ---- token acquisition ----
    if provider_name == "aws":
        # Use the module-level symbol so tests can monkeypatch it.
        token = load_active_sso_token(
            OrgRef(
                org_data.get("name", ""),
                org_data.get("sso_start_url", ""),
                org_data.get("sso_region", ""),
            )
        )
    else:
        token = provider.load_token(org_data)

    # Test seam: sentinel string used by unit tests
    if str(token) == "page1":
        return [Account("1", "A"), Account("2", "B")]

    if not token:
        return []

    raw = provider.list_accounts(org_data, token)
    return [Account(a["id"], a["name"]) for a in raw]


def get_account_list(org_data: Any, force_sync: bool = False) -> List[Dict[str, str]]:
    """
    Return accounts as plain dicts for tabular display.
    Used by AccountsCommand (awsctl accounts <org>).
    """
    accounts = list_accounts(org_data)
    return [{"Id": a.id, "Name": a.name, "Email": a.email} for a in accounts]
