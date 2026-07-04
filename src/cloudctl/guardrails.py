import os
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
AUDIT_LOG = Path.home() / ".cloudctl" / "audit.log"


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

    # Additionally enforce partition boundaries even when no allowed_regions is set
    if org.get("provider", "aws") == "aws":
        partition = org.get("partition", "aws")
        if partition:
            from .schema import AWS_PARTITIONS

            if partition in AWS_PARTITIONS:
                valid_regions = set(AWS_PARTITIONS[partition]["regions"])
                if valid_regions and region not in valid_regions:
                    utils.console.print(
                        f"[bold red]Region '{region}' is not available in "
                        f"partition '{partition}'.[/]\n"
                        f"Valid regions: {', '.join(sorted(valid_regions))}"
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
            f"[bold red]UPDATE REQUIRED:[/] This org requires cloudctl >= {min_ver}. "
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
        if not AUDIT_LOG.exists():
            AUDIT_LOG.touch(mode=0o600)
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

    # Never hang on a prompt without a TTY. An agent supplies the required
    # justification via CLOUDCTL_BREAK_GLASS_REASON; absent that, fail fast
    # (exit 2 = auth/authorization gate) rather than blocking forever.
    _no_tty = os.environ.get("CI") or os.environ.get("CLAUDECODE")
    try:
        _no_tty = _no_tty or not sys.stdin.isatty()
    except Exception:
        _no_tty = True
    if _no_tty:
        reason = os.environ.get("CLOUDCTL_BREAK_GLASS_REASON")
        if not reason:
            utils.console.print(
                "[red]Sensitive role requires a justification but no TTY is "
                "available.[/] Set [bold]CLOUDCTL_BREAK_GLASS_REASON[/bold]."
            )
            sys.exit(2)
        _audit_log(org.get("name", "unknown"), role, reason)
        return

    try:
        reason = inquirer.text(
            message="Enter reason for access:",
        ).execute()
    except KeyboardInterrupt:
        utils.console.print("[red]Access Aborted.[/]")
        sys.exit(1)

    _audit_log(org.get("name", "unknown"), role, reason)


def validate_role_access(
    org: Dict[str, Any],
    role_name: str,
    account_id: str,
) -> tuple[bool, str]:
    """Validate whether a role may be accessed in an organization.

    The single integration point for `cloudctl switch`'s authorization gate.
    This is the *honest* contract: cloudctl enforces exactly two native
    controls and claims no more.

    1. **Allowed-roles allowlist.** When ``org["allowed_roles"]`` is set and the
       requested role is not in it, access is DENIED. This actually blocks.
    2. **Break-glass audit** for ``org["sensitive_roles"]``. Accessing a
       sensitive role requires a justification (TTY prompt or
       ``CLOUDCTL_BREAK_GLASS_REASON``) and records a real entry to the native
       audit log (``~/.cloudctl/audit.log``). This actually records.

    There is no MFA or approval enforcement: cloudctl has no approver system and
    no MFA flow, so it does not pretend to gate on them.

    Returns:
        (allowed, message)
        - (True, "")            access granted (allowed and audited)
        - (False, "<reason>")   access denied (allowlist rejection or bad config)
    """
    org_name = org.get("name", "unknown")

    # 1. Allowed-roles allowlist (when configured). This is a real, blocking gate.
    allowed_roles = org.get("allowed_roles", [])
    if allowed_roles is None:
        allowed_roles = []
    elif not isinstance(allowed_roles, (list, tuple, set)):
        return (
            False,
            f"Invalid allowed_roles configuration for org '{org_name}' "
            f"(must be list, not {type(allowed_roles).__name__})",
        )

    if allowed_roles and role_name not in allowed_roles:
        _audit_log(
            org_name, role_name, f"DENIED account={account_id} not_in_allowed_roles"
        )
        return False, f"Role '{role_name}' is not allowed for org '{org_name}'"

    # 2. Break-glass justification for sensitive roles (prompts + audits).
    sensitive = org.get("sensitive_roles", [])
    if role_name in sensitive:
        check_break_glass(org, role_name)
        _audit_log(org_name, role_name, f"GRANTED account={account_id} break_glass")
        return True, ""

    # 3. Plain grant (audited).
    _audit_log(org_name, role_name, f"GRANTED account={account_id}")
    return True, ""


def validate_multi_cloud_access(
    org: Dict[str, Any],
    provider: str,
    role_name: str,
    resource_id: str,
) -> tuple[bool, str]:
    """Validate access to a multi-cloud resource (AWS/Azure/GCP).

    Extends :func:`validate_role_access` with provider-specific role-format
    checks (e.g. GCP roles must start with ``roles/``) before delegating.
    """
    provider = provider.lower()
    allowed_roles = org.get("allowed_roles", [])

    # Enforce GCP role format only when there is no explicit allowlist.
    if not allowed_roles and provider == "gcp":
        if not role_name.startswith("roles/"):
            return (
                False,
                f"Invalid GCP role format: '{role_name}' (must start with 'roles/')",
            )

    return validate_role_access(org, role_name, resource_id)


def get_rbac_policy_summary(org: Dict[str, Any]) -> str:
    """Return a human-readable summary of an organization's RBAC policy."""
    org_name = org.get("name", "unknown")
    allowed_roles = org.get("allowed_roles", [])
    sensitive_roles = org.get("sensitive_roles", [])

    lines = [f"RBAC Policy for org '{org_name}':", ""]

    if allowed_roles:
        lines.append(f"  Allowed Roles: {', '.join(sorted(allowed_roles))}")
    else:
        lines.append("  Allowed Roles: None (all roles blocked)")

    if sensitive_roles:
        lines.append(
            f"  Sensitive Roles (break-glass): {', '.join(sorted(sensitive_roles))}"
        )

    lines.append("")
    return "\n".join(lines)


def get_audit_log_path() -> Path:
    """Return the path to the native cloudctl RBAC audit log."""
    return AUDIT_LOG


def audit_log_entries(org_name: str | None = None, limit: int = 50) -> List[str]:
    """Read recent entries from the native audit log (most recent first)."""
    if not AUDIT_LOG.exists():
        return []
    try:
        content = AUDIT_LOG.read_text(encoding="utf-8").strip()
        if not content:
            return []
        lines = [line for line in content.split("\n") if line.strip()]
        if org_name:
            lines = [line for line in lines if f"ORG={org_name}" in line]
        return list(reversed(lines[-limit:]))
    except OSError:
        return []
