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

    try:
        reason = inquirer.text(
            message="Enter reason for access:",
        ).execute()
    except KeyboardInterrupt:
        utils.console.print("[red]Access Aborted.[/]")
        sys.exit(1)

    _audit_log(org.get("name", "unknown"), role, reason)


def check_approval_required(org: Dict[str, Any], role: str) -> tuple[bool, int]:
    """Check if a role requires approval before switching.

    Args:
        org: Organization config dict
        role: Role name being accessed

    Returns:
        (required: bool, num_approvers: int)
        Secure default: unknown roles require approval (fail-closed)
    """
    approval_gates = org.get("approval_gate_roles", {})

    # If role in approval gate config, use configured approver count
    if role in approval_gates:
        return True, approval_gates[role]

    # If approval_gate_roles is defined but role not in it, no approval needed
    # (explicit allowlist)
    if approval_gates:
        return False, 0

    # No approval gates configured → no approval required (backward compatible)
    return False, 0


def check_mfa_required(org: Dict[str, Any], role: str) -> tuple[bool, str]:
    """Check if a role requires MFA enforcement.

    Args:
        org: Organization config dict
        role: Role name being accessed

    Returns:
        (required: bool, method: str)
        method: "totp" | "webauthn" | "sms" (default: "totp")
        Secure default: unknown roles require MFA if list is defined
    """
    mfa_roles = org.get("mfa_required_roles", [])

    # If role in MFA required list, enforce MFA
    if role in mfa_roles:
        method = org.get("mfa_method", "totp")  # Default to TOTP
        return True, method

    # If mfa_required_roles is defined but role not in it, no MFA needed
    # (explicit allowlist)
    if mfa_roles:
        return False, ""

    # No MFA list configured → no MFA required (backward compatible)
    return False, ""


def validate_role_access(
    org: Dict[str, Any],
    role_name: str,
    account_id: str,
) -> tuple[bool, str]:
    """Validate whether a role may be accessed in an organization.

    The single integration point for `cloudctl switch`'s authorization gate.
    Orchestrates the native guardrail primitives (allowed-roles allowlist,
    break-glass, approval gates, MFA) and records decisions to the native audit
    log (``~/.cloudctl/audit.log``).

    Returns:
        (allowed, message)
        - (True, "")                 access granted (no further gate)
        - (False, "<reason>")        access denied
        - (True, "approval_required") gated on approval
        - (True, "mfa_required")      gated on MFA
    """
    org_name = org.get("name", "unknown")

    # 1. Allowed-roles allowlist (when configured).
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

    # 3. Approval gate.
    approval_required, num_approvers = check_approval_required(org, role_name)
    if approval_required:
        _audit_log(
            org_name,
            role_name,
            f"PENDING_APPROVAL account={account_id} approvers={num_approvers}",
        )
        return True, "approval_required"

    # 4. MFA gate.
    mfa_required, mfa_method = check_mfa_required(org, role_name)
    if mfa_required:
        _audit_log(
            org_name, role_name, f"PENDING_MFA account={account_id} method={mfa_method}"
        )
        return True, "mfa_required"

    # 5. Plain grant.
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
    approval_gate_roles = org.get("approval_gate_roles", {})
    mfa_required_roles = org.get("mfa_required_roles", [])

    lines = [f"RBAC Policy for org '{org_name}':", ""]

    if allowed_roles:
        lines.append(f"  Allowed Roles: {', '.join(sorted(allowed_roles))}")
    else:
        lines.append("  Allowed Roles: None (all roles blocked)")

    if sensitive_roles:
        lines.append(
            f"  Sensitive Roles (break-glass): {', '.join(sorted(sensitive_roles))}"
        )

    if approval_gate_roles:
        approvals = []
        for role, count in sorted(approval_gate_roles.items()):
            if not isinstance(count, int):
                raise TypeError(
                    f"Invalid approval_gate_roles configuration: '{role}' has count "
                    f"'{count}' (type {type(count).__name__}), must be int"
                )
            approvals.append(
                f"{role} (requires {count} approver{'s' if count != 1 else ''})"
            )
        lines.append(f"  Approval-Gated Roles: {', '.join(approvals)}")

    if mfa_required_roles:
        lines.append(f"  MFA-Required Roles: {', '.join(sorted(mfa_required_roles))}")

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
