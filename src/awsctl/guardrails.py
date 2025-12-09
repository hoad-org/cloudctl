# file: src/awsctl/guardrails.py
# SPDX-License-Identifier: MIT
"""
awsctl.guardrails
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from InquirerPy import inquirer
from packaging import version

from awsctl import context_manager
from awsctl._version import __version__
from awsctl.utils import ForceStderr, console, ensure_dir

AUDIT_LOG = Path.home() / ".awsctl" / "audit.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB


def validate_region(org_config: Dict[str, Any], region: str) -> None:
    """
    Enforce 'allowed_regions' policy.
    """
    allowed = org_config.get("allowed_regions")

    if allowed is not None and not isinstance(allowed, list):
        console.print("[bold red]✗ Configuration Error[/]\n'allowed_regions' must be a list.")
        sys.exit(1)

    if allowed is None:
        console.print("[bold red]✗ Configuration Error[/]\nNo 'allowed_regions' defined.")
        sys.exit(1)

    # Empty list = Deny All
    if not allowed:
        console.print("[bold red]✗ Guardrail Violation[/]\nNo regions are permitted.")
        sys.exit(1)

    if "*" in allowed:
        return

    if region not in allowed:
        console.print(
            f"[bold red]✗ Guardrail Violation[/]\n" f"Region [yellow]'{region}'[/] is not permitted for org [cyan]'{org_config.get('name')}'[/].",
        )
        console.print(f"Allowed regions: [green]{', '.join(allowed)}[/]")
        sys.exit(1)


def sort_roles(org_config: Dict[str, Any], roles: List[str]) -> List[str]:
    """Sort roles based on 'preferred_roles' policy."""
    preferred = org_config.get("preferred_roles") or []
    is_preferred = set(preferred)
    top = [r for r in preferred if r in roles]
    bottom = sorted([r for r in roles if r not in is_preferred])
    return top + bottom


def check_min_version(org_config: Dict[str, Any]) -> None:
    """
    Feature #2: Enforce Minimum Client Version.
    """
    min_ver = org_config.get("min_client_version")
    if not min_ver:
        return

    try:
        # Robust comparison using 'packaging'
        if version.parse(__version__) < version.parse(min_ver):
            console.print(f"\n[bold white on red] CRITICAL UPDATE REQUIRED [/]\n" f"Your version ({__version__}) is older than the minimum required ({min_ver}).\n" f"Security guardrails may be out of date.\n")
            console.print("Run: [bold green]pipx upgrade awsctl[/]\n")
            sys.exit(1)
    except version.InvalidVersion:
        # [FIX] PYBH-0067: Fail closed on version tampering/corruption
        console.print(f"\n[bold red]Security Error:[/bold red] Application version string '{__version__}' is invalid.\n" "This may indicate tampering or a corrupted installation.")
        sys.exit(1)


def check_break_glass(org_config: Dict[str, Any], role: str) -> None:
    """
    Feature #3: Break Glass Audit.
    If role is sensitive, force user to provide justification.
    """
    sensitive = org_config.get("sensitive_roles", [])
    if role not in sensitive:
        return

    console.print(f"\n[bold yellow]⚠️  SENSITIVE ROLE ACCESS: {role}[/]")
    console.print("[dim]This action will be logged for security audit.[/]")

    reason = ""
    with ForceStderr():
        try:
            # [FIX] MyPy: Ignore dynamic attr access on inquirer
            reason = inquirer.text(  # type: ignore
                message="Justification (Ticket # / Reason):",
                validate=lambda result: len(result) > 4,
                invalid_message="Please provide a valid reason (min 5 chars).",
            ).execute()
        except KeyboardInterrupt:
            console.print("[red]Access Aborted.[/]")
            sys.exit(1)

    # Log to local audit file
    _audit_log(org_config.get("name", "unknown"), role, reason)


def _audit_log(org: str, role: str, reason: str) -> None:
    ensure_dir(AUDIT_LOG.parent)

    # [FIX] Race Condition: Lock file before rotate/write
    with context_manager._file_lock(AUDIT_LOG):
        # [FIX] PYBH-0057: Log Rotation
        try:
            if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size > MAX_LOG_SIZE:
                backup = AUDIT_LOG.with_suffix(".log.1")
                shutil.move(AUDIT_LOG, backup)
        except OSError:
            pass  # Best effort rotation

        ts = datetime.now(timezone.utc).isoformat()

        # 🛡️ SECURITY FIX (PYBH-0030): Sanitize input to prevent log injection
        # 1. Strip ANSI escape sequences (colors, cursor moves)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        safe_reason = ansi_escape.sub("", reason)

        # [FIX] PYBH-0053: Strip Unicode Control characters (Category Cf)
        safe_reason = re.sub(r"[\x00-\x1f\x7f-\x9f|]", " ", safe_reason)

        # 3. Collapse multiple spaces
        safe_reason = re.sub(r"\s+", " ", safe_reason).strip()

        entry = f"{ts} | ORG={org} | ROLE={role} | USER={sys.argv} | REASON={safe_reason}\n"

        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
