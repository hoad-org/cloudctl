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

    if (
        existing
        and kwargs.get("account")
        and kwargs.get("account") != existing.get("account")
    ):
        new_ctx["previous"] = {k: v for k, v in existing.items() if k != "previous"}

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(json.dumps(new_ctx))


def print_status() -> None:
    """Renders the context dashboard."""
    ctx = load_context()
    if not ctx:
        console.print("[yellow]No active context found.[/]")
        return

    from .sso_cache import OrgRef, load_active_sso_token

    org_ref = OrgRef(ctx.get("current_org", ""), "", ctx.get("region", ""))

    status = "Active" if load_active_sso_token(org_ref) else "Expired"
    console.print(f"--- AWS Active Context ({status}) ---")
    console.print(f"Organization: {ctx.get('current_org')}")
    console.print(f"Account:      {ctx.get('account')}")
    console.print(f"Role:         {ctx.get('role')}")
    console.print(f"Region:       {ctx.get('region')}")


def clear_context() -> None:
    if CONTEXT_FILE.exists():
        CONTEXT_FILE.unlink()
