import json
from typing import Any, Dict, Optional

from .config import CONFIG_DIR
from .utils import console

CONTEXT_FILE = CONFIG_DIR / "current_context.json"


def load_context() -> Dict[str, Any]:
    """Loads current context with resilient error handling."""
    if not CONTEXT_FILE.exists():
        return {}
    try:
        return json.loads(CONTEXT_FILE.read_text())
    except Exception:
        return {}


def get_previous_context() -> Optional[Dict[str, Any]]:
    """Retrieves the context active prior to the current session."""
    return load_context().get("previous")


def save_context_update(**kwargs: Any) -> None:
    """Updates active context and rotates previous settings into history."""
    existing = load_context()
    new_ctx = {**existing, **kwargs}

    # Use 'current_org' consistently as per test expectations
    if "org" in kwargs:
        new_ctx["current_org"] = kwargs.pop("org")
        new_ctx.pop("org", None)

    if (
        existing
        and kwargs.get("account")
        and kwargs.get("account") != existing.get("account")
    ):
        new_ctx["previous"] = {k: v for k, v in existing.items() if k != "previous"}

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(json.dumps(new_ctx))


def save_context(org_name: str, account: str, role: str, region: str) -> None:
    """
    Persist a completed switch operation to disk.

    Reads the org's provider field and stores it in context so that
    subsequent commands (exec, status, logout) know which cloud provider
    to use without re-reading the org config every time.
    """
    from .config import get_org

    try:
        org_data = get_org(org_name)
        provider = org_data.get("provider", "aws")
    except Exception:
        provider = "aws"

    save_context_update(
        org=org_name,
        account=account,
        role=role,
        region=region,
        provider=provider,
    )


def print_status() -> None:
    """Renders the context dashboard."""
    ctx = load_context()
    if not ctx:
        console.print("[yellow]No active context found.[/]")
        return

    provider_name = ctx.get("provider", "aws")
    org_name = ctx.get("current_org", "")

    # Provider-specific session validity check
    session_status = "Unknown"
    try:
        from .config import get_org
        from .providers import get_provider

        org_data = get_org(org_name) if org_name else {"provider": provider_name}
        provider = get_provider(org_data)
        token = provider.load_token(org_data)
        session_status = "Active" if token else "Expired"
    except Exception:
        session_status = "Unknown"

    provider_label = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}.get(
        provider_name, provider_name.upper()
    )

    console.print(f"--- {provider_label} Active Context ({session_status}) ---")
    console.print(f"Organization: {org_name}")
    console.print(f"Account:      {ctx.get('account')}")
    console.print(f"Role:         {ctx.get('role')}")
    console.print(f"Region:       {ctx.get('region')}")


def clear_context() -> None:
    if CONTEXT_FILE.exists():
        CONTEXT_FILE.unlink()
