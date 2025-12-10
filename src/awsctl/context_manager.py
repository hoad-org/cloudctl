# file: src/awsctl/context_manager.py
# SPDX-License-Identifier: MIT
"""
awsctl.context_manager
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from rich.panel import Panel
from rich.table import Table

from awsctl import config, sso_cache
from awsctl.sso_cache import OrgRef
from awsctl.utils import console

CONTEXT_FILE = Path.home() / ".aws" / "awsctl-context.json"
HISTORY_LIMIT = 5


@contextlib.contextmanager
def _file_lock(path: Path, timeout: float = 2.0) -> Generator[None, None, None]:
    """
    [FIX] PYBH-0018: Cross-platform spinlock using atomic file creation.
    [FIX] PYBH-0059: Added Stale Lock detection (break if >30s old).
    [FIX] PYBH-0058: Raise TimeoutError if lock cannot be acquired.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    start = time.time()
    locked = False

    while (time.time() - start) < timeout:
        try:
            # Atomic creation (O_CREAT | O_EXCL)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
            locked = True
            break
        except FileExistsError:
            # [FIX] PYBH-0059: Check for stale locks (crashed process)
            try:
                if lock_path.stat().st_mtime < (time.time() - 30):
                    try:
                        os.remove(lock_path)
                        continue
                    except OSError:
                        pass
            except OSError:
                pass
            time.sleep(0.05)
        except OSError:
            time.sleep(0.05)

    # [FIX] PYBH-0058: Fail closed if lock not acquired
    if not locked:
        raise TimeoutError(f"Could not acquire lock on {path}")

    try:
        yield
    finally:
        if locked:
            try:
                os.remove(lock_path)
            except OSError:
                pass


def load_context() -> Dict[str, Any]:
    if not CONTEXT_FILE.exists():
        return {}
    try:
        data: Dict[str, Any] = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _update_history(data: Dict[str, Any], new_entry: Dict[str, str]) -> None:
    """Push new entry to history stack, maintaining uniqueness and limit."""
    history: List[Dict[str, str]] = data.get("history", [])

    # Remove duplicates (move to top)
    history = [
        h
        for h in history
        if not (
            h.get("org") == new_entry["org"]
            and h.get("account") == new_entry["account"]
            and h.get("role") == new_entry["role"]
        )
    ]

    # Add to top
    history.insert(0, new_entry)

    # Trim
    data["history"] = history[:HISTORY_LIMIT]


def save_context_update(
    org: Optional[str] = None,
    account: Optional[str] = None,
    role: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # [FIX] PYBH-0018: Acquire lock before Reading-Modifying-Writing
    # [FIX] PYBH-0069: Propagate TimeoutError to caller to prevent Split-Brain state
    with _file_lock(CONTEXT_FILE):
        data: Dict[str, Any] = load_context()

        # Save "Previous" for toggle switch (-)
        if all(k in data for k in ("account", "role", "region")):
            data["previous"] = {
                "account": data.get("account"),
                "role": data.get("role"),
                "region": data.get("region"),
                "org": data.get("current_org"),
            }

        # Update Current
        if org:
            data["current_org"] = org
        if account:
            data["account"] = account
        if role:
            data["role"] = role
        if region:
            data["region"] = region

        data["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Feature #1: Update Smart History
        if data.get("current_org") and data.get("account") and data.get("role"):
            entry = {
                "org": data["current_org"],
                "account": data["account"],
                "role": data["role"],
                "region": data.get("region", "us-east-1"),
            }
            _update_history(data, entry)

        # Atomic Write
        fd, tmp_path = tempfile.mkstemp(dir=CONTEXT_FILE.parent, text=True)
        try:
            if CONTEXT_FILE.exists():
                shutil.copymode(CONTEXT_FILE, tmp_path)
            else:
                os.chmod(tmp_path, 0o600)

            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            os.replace(tmp_path, CONTEXT_FILE)
        except Exception as e:
            console.print(f"[warning]Failed to save context: {e}[/]")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def get_previous_context() -> Optional[Dict[str, str]]:
    data = load_context()
    prev = data.get("previous")
    if isinstance(prev, dict):
        return {k: str(v) for k, v in prev.items()}
    return None


def get_history() -> List[Dict[str, str]]:
    data = load_context()
    raw = data.get("history", [])
    # Type safety filter
    return [
        {k: str(v) for k, v in item.items()} for item in raw if isinstance(item, dict)
    ]


def _get_token_health(org_name: str) -> str:
    try:
        org_conf = config.get_org(org_name)
        ref = OrgRef(
            org_conf["name"], org_conf["sso_start_url"], org_conf["sso_region"]
        )
        token = sso_cache.load_active_sso_token(ref)
        if not token:
            return "[bold red]No valid token (Login required)[/]"

        now = datetime.now(timezone.utc)
        delta = token.expires_at - now

        if delta.total_seconds() < 0:
            return "[bold red]Expired[/]"

        hours = delta.total_seconds() / 3600

        if hours < 1:
            return f"[bold red]Expires in {int(delta.total_seconds() // 60)} mins[/]"
        elif hours < 4:
            return f"[yellow]Expires in {int(hours)}h {int(delta.total_seconds() % 3600 // 60)}m[/]"
        else:
            return f"[green]Valid ({int(hours)}h remaining)[/]"

    except (SystemExit, ValueError, RuntimeError):
        return "[bold red]No valid token (Login required)[/]"
    except Exception:
        return "[dim]Unknown[/]"


def print_status() -> None:
    data = load_context()
    current_org = data.get("current_org")

    if not current_org:
        console.print("[yellow]No active session found.[/] Run `awsctl login`.")
        return

    table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    table.add_column("Key", style="cyan", justify="right")
    table.add_column("Value", style="bold white")

    table.add_row("Organization", current_org)
    table.add_row("Account ID", data.get("account", "-"))
    table.add_row("Active Role", data.get("role", "-"))
    table.add_row("Region", data.get("region", "-"))

    health = _get_token_health(current_org)
    table.add_row("SSO Session", health)

    if "previous" in data:
        prev = data["previous"]
        prev_txt = f"{prev.get('role')} @ {prev.get('account')} ({prev.get('org')})"
        table.add_row("Previous (-)", f"[dim]{prev_txt}[/]")

    console.print(
        Panel(
            table,
            title="[bold green]AWS Active Context[/]",
            subtitle=f"[dim]Updated: {data.get('last_updated', 'N/A')}[/]",
            border_style="green",
            expand=False,
        )
    )
