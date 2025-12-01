# file: src/awsctl/context_manager.py
# SPDX-License-Identifier: MIT
"""
awsctl.context_manager
----------------------
Manages persistent state and provides the "Flight Deck" status dashboard.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from rich.panel import Panel
from rich.table import Table

from awsctl import config, sso_cache
from awsctl.sso_cache import OrgRef
from awsctl.utils import console

CONTEXT_FILE = Path.home() / ".aws" / "awsctl-context.json"


def load_context() -> Dict[str, Any]:
    if not CONTEXT_FILE.exists():
        return {}
    try:
        data: Dict[str, Any] = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {}


def save_context_update(
    org: Optional[str] = None,
    account: Optional[str] = None,
    role: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    """Updates context and rotates history for smart switching."""
    data: Dict[str, Any] = load_context()

    # 1. Capture current state as 'previous' before updating
    if all(k in data for k in ("account", "role", "region")):
        data["previous"] = {
            "account": data.get("account"),
            "role": data.get("role"),
            "region": data.get("region"),
            "org": data.get("current_org"),
        }

    # 2. Update current
    if org:
        data["current_org"] = org
    if account:
        data["account"] = account
    if role:
        data["role"] = role
    if region:
        data["region"] = region

    data["last_updated"] = datetime.now().isoformat()

    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_previous_context() -> Optional[Dict[str, str]]:
    data = load_context()
    prev = data.get("previous")
    if isinstance(prev, dict):
        return {k: str(v) for k, v in prev.items()}
    return None


def _get_token_health(org_name: str) -> str:
    """Calculate token expiry and return a rich-formatted string."""
    try:
        # Hydrate org to get start URL/Region
        org_conf = config.get_org(org_name)
        ref = OrgRef(
            org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"]
        )
        token = sso_cache.load_active_sso_token(ref)

        now = datetime.now(timezone.utc)
        delta = token.expires_at - now
        hours = delta.total_seconds() / 3600

        if hours < 1:
            return f"[bold red]Expires in {int(delta.total_seconds() // 60)} mins[/]"
        elif hours < 4:
            return f"[yellow]Expires in {int(hours)}h {int(delta.total_seconds() % 3600 // 60)}m[/]"
        else:
            return f"[green]Valid ({int(hours)}h remaining)[/]"

    except SystemExit:
        return "[bold red]No valid token (Login required)[/]"
    except Exception:
        return "[dim]Unknown[/]"


def print_status() -> None:
    """Render the 'Flight Deck' dashboard."""
    data = load_context()
    current_org = data.get("current_org")

    if not current_org:
        console.print("[yellow]No active session found.[/] Run `awsctl login`.")
        return

    # 1. Identity Table
    table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    table.add_column("Key", style="cyan", justify="right")
    table.add_column("Value", style="bold white")

    # Context Details
    table.add_row("Organization", current_org)
    table.add_row("Account ID", data.get("account", "-"))
    table.add_row("Active Role", data.get("role", "-"))
    table.add_row("Region", data.get("region", "-"))

    # Token Health
    health = _get_token_health(current_org)
    table.add_row("SSO Session", health)

    # Previous Context (if exists)
    if "previous" in data:
        prev = data["previous"]
        prev_txt = f"{prev.get('role')} @ {prev.get('account')} ({prev.get('org')})"
        table.add_row("Previous (-)", f"[dim]{prev_txt}[/]")

    # 2. Render Panel
    console.print(
        Panel(
            table,
            title="[bold green]AWS Active Context[/]",
            subtitle=f"[dim]Updated: {data.get('last_updated', 'N/A')}[/]",
            border_style="green",
            expand=False,
        )
    )
