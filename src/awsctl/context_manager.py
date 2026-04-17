import json
import os
import tempfile
from typing import Any, Dict, Optional

from .config import CONFIG_DIR
from . import utils

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
    # Atomic write: write to a temp file then replace, so concurrent readers
    # never see a partially-written context file.
    fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_ctx))
        os.replace(tmp_path, CONTEXT_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


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


def _format_expiry(token: Any) -> str:
    """Return a human-readable expiry string for a token object."""
    try:
        from datetime import datetime, timezone

        if not hasattr(token, "expiresAt"):
            return ""
        delta = token.expiresAt - datetime.now(timezone.utc)
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "[red]EXPIRED[/red]"
        if total_seconds < 900:  # < 15 minutes
            mins = total_seconds // 60
            secs = total_seconds % 60
            return f"[red]⚠  expires in {mins}m {secs}s[/red]"
        if total_seconds < 3600:
            return f"[yellow]expires in {total_seconds // 60}m[/yellow]"
        hours = total_seconds // 3600
        mins = (total_seconds % 3600) // 60
        return f"[green]expires in {hours}h {mins}m[/green]"
    except Exception:
        return ""


def print_status() -> None:
    """Renders the context dashboard."""
    ctx = load_context()
    if not ctx:
        utils.console.print("[yellow]No active context found.[/]")
        return

    provider_name = ctx.get("provider", "aws")
    org_name = ctx.get("current_org", "")

    # Provider-specific session validity check + expiry
    session_status = "Unknown"
    expiry_str = ""
    try:
        from .config import get_org
        from .providers import get_provider

        org_data = get_org(org_name) if org_name else {"provider": provider_name}
        provider = get_provider(org_data)
        token = provider.load_token(org_data)
        if token:
            session_status = "Active"
            expiry_str = _format_expiry(token)
        else:
            session_status = "Expired"
    except Exception:
        session_status = "Unknown"

    provider_label = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}.get(
        provider_name, provider_name.upper()
    )
    status_color = {"Active": "green", "Expired": "red"}.get(session_status, "yellow")

    utils.console.print(
        f"\n[bold]── {provider_label} Context[/bold]  "
        f"[{status_color}]{session_status}[/{status_color}]"
        + (f"  {expiry_str}" if expiry_str else "")
    )
    utils.console.print(f"  Organization : [bold]{org_name}[/bold]")
    utils.console.print(f"  Account      : {ctx.get('account', '—')}")
    utils.console.print(f"  Role         : {ctx.get('role', '—')}")
    utils.console.print(f"  Region       : {ctx.get('region', '—')}")

    prev = ctx.get("previous")
    if prev and prev.get("current_org"):
        utils.console.print(
            f"\n  [dim]Previous: {prev.get('current_org')} / "
            f"{prev.get('account', '—')} / {prev.get('role', '—')}[/dim]"
        )
        utils.console.print("  [dim]Run 'awsctl switch -' to go back[/dim]")
    utils.console.print()


def clear_context() -> None:
    if CONTEXT_FILE.exists():
        CONTEXT_FILE.unlink()
