import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import utils
from InquirerPy import inquirer

try:
    from ._version import __version__
except ImportError:
    __version__ = "1.1.0"

MAX_LOG_SIZE = 10 * 1024 * 1024
AUDIT_LOG = Path.home() / ".awsctl" / "audit.log"


def validate_region(org: Dict[str, Any], region: str) -> None:
    """
    Enforce the allowed_regions allowlist.

    Secure default: empty allowed_regions list = deny all (fail-closed).
    """
    allowed = org.get("allowed_regions", [])
    if not allowed or region not in allowed:
        utils.console.print(
            f"[bold red]Guardrail Violation:[/] Region [yellow]{region}[/] is not "
            f"permitted for org '[cyan]{org.get('name', 'unknown')}[/]'. "
            f"Allowed: {allowed or 'none'}"
        )
        sys.exit(1)


def sort_roles(org: Dict[str, Any], roles: List[str]) -> List[str]:
    """Order roles: preferred first (in config order), then remaining alphabetically."""
    pref = org.get("preferred_roles", [])
    out = [r for r in pref if r in roles]
    out.extend(sorted([r for r in roles if r not in pref]))
    return out


def check_min_version(org: Dict[str, Any]) -> None:
    """
    Enforce the min_client_version gate.
    Exits if the running client is older than the registry requires.
    """
    min_ver = org.get("min_client_version")
    if not min_ver:
        return

    def _parse(v: str):
        try:
            return tuple(int(x) for x in v.split("."))
        except (ValueError, AttributeError):
            return (0,)

    if _parse(__version__) < _parse(min_ver):
        utils.console.print(
            f"[bold red]UPDATE REQUIRED:[/] This org requires awsctl >= {min_ver}. "
            f"You are running {__version__}. Please upgrade."
        )
        sys.exit(1)


def _audit_log(org_name: str, role: str, reason: str) -> None:
    """
    Append an audit log entry. Rotates (via shutil.move) if over size limit.
    OSError during rotation is caught; the entry is still appended.
    """
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size > MAX_LOG_SIZE:
            try:
                backup = Path(str(AUDIT_LOG) + ".bak")
                shutil.move(str(AUDIT_LOG), str(backup))
            except OSError:
                pass  # Rotation failure must not block appending
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"{timestamp} | ORG={org_name} " f"| ROLE={role} | REASON={reason}\n"
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # Audit log failure must not block access


def check_break_glass(org: Dict[str, Any], role: str) -> None:
    """
    Prompt for a justification when accessing a sensitive role.
    Logs the access to AUDIT_LOG and prints a warning.
    Exits if the user cancels.
    """
    sensitive = org.get("sensitive_roles", [])
    if role not in sensitive:
        return

    utils.console.print(
        f"[bold yellow]⚠ SENSITIVE ROLE ACCESS:[/] "
        f"Role [red]{role}[/] requires a justification reason."
    )

    try:
        reason = inquirer.text(
            message="Enter reason for access:",
        ).execute()
    except KeyboardInterrupt:
        utils.console.print("[red]Access Aborted.[/]")
        sys.exit(1)

    _audit_log(org.get("name", "unknown"), role, reason)
