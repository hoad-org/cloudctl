"""
Role validation and suggestion module.

Provides tools for:
- Querying available roles for a given account
- Validating that a requested role exists
- Suggesting correct role names when validation fails
- Handling role name mismatches gracefully
"""

from typing import Any, Dict, List, Optional, Tuple

from . import utils as _utils


class RoleValidationError(Exception):
    """Raised when role validation fails."""

    def __init__(self, message: str, available_roles: Optional[List[str]] = None):
        super().__init__(message)
        self.available_roles = available_roles or []


def get_available_roles(
    org_data: Dict[str, Any], token: Any, account_id: str
) -> List[str]:
    """
    Query available roles for an account.

    Args:
        org_data: Organization configuration dict
        token: SSO token from load_active_sso_token
        account_id: AWS account ID

    Returns:
        List of role names available in this account
    """
    from .providers import get_provider

    provider = get_provider(org_data)
    try:
        return provider.list_roles(org_data, token, account_id)
    except Exception as e:
        _utils.console.print(
            f"[yellow]Warning:[/] Could not query available roles: {e}"
        )
        return []


def find_role_suggestions(
    requested_role: str, available_roles: List[str], max_suggestions: int = 3
) -> List[str]:
    """
    Find role name suggestions using fuzzy matching.

    Tries to match the requested role against available roles using:
    1. Exact case-insensitive match
    2. Substring match
    3. Levenshtein distance (for typos)

    Args:
        requested_role: The role name requested by the user
        available_roles: List of valid roles
        max_suggestions: Max number of suggestions to return

    Returns:
        List of suggested role names (highest confidence first)
    """
    if not available_roles:
        return []

    suggestions: Dict[str, float] = {}

    # 1. Exact case-insensitive match (highest confidence)
    for role in available_roles:
        if role.lower() == requested_role.lower():
            suggestions[role] = 1.0

    # 2. Substring match (medium confidence)
    if not suggestions:
        requested_lower = requested_role.lower()
        for role in available_roles:
            if requested_lower in role.lower() or role.lower() in requested_lower:
                suggestions[role] = 0.8

    # 3. Levenshtein distance (for typos)
    if not suggestions:
        try:
            from difflib import SequenceMatcher

            for role in available_roles:
                ratio = SequenceMatcher(None, requested_role, role).ratio()
                if ratio > 0.6:
                    suggestions[role] = ratio
        except Exception:
            pass

    # Sort by confidence (highest first) and return top N
    sorted_suggestions = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)
    return [role for role, _ in sorted_suggestions[:max_suggestions]]


def validate_role(
    org_data: Dict[str, Any],
    token: Any,
    account_id: str,
    requested_role: str,
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate that a requested role exists for the given account.

    Args:
        org_data: Organization configuration dict
        token: SSO token from load_active_sso_token
        account_id: AWS account ID
        requested_role: The role name requested by the user

    Returns:
        Tuple of:
        - is_valid (bool): True if role exists and is available
        - message (str): Error message if invalid, None if valid
        - available_roles (List[str]): List of available roles in this account
    """
    available_roles = get_available_roles(org_data, token, account_id)

    if not available_roles:
        return (
            False,
            "Could not query available roles for this account",
            [],
        )

    # Check if requested role exists in available roles (case-insensitive)
    for role in available_roles:
        if role.lower() == requested_role.lower():
            return True, None, available_roles

    # Role not found. (find_role_suggestions is invoked elsewhere for the
    # interactive prompt; the result is not folded into this return value.)
    _suggestions = find_role_suggestions(requested_role, available_roles)
    return (
        False,
        f"Role '{requested_role}' not found in this account",
        available_roles,
    )


def show_role_error_and_suggestions(
    requested_role: str,
    available_roles: List[str],
    account_id: str,
    org_name: str,
) -> None:
    """
    Display a helpful error message with role suggestions.

    Args:
        requested_role: The role name that was requested but not found
        available_roles: List of available roles in this account
        account_id: AWS account ID (for context)
        org_name: Organization name (for context)
    """
    _utils.console.print(f"\n[bold red]✗ Role not found:[/] {requested_role}")
    _utils.console.print(f"[dim]Account: {account_id} ({org_name})[/]\n")

    if available_roles:
        suggestions = find_role_suggestions(requested_role, available_roles)
        _utils.console.print("[bold]Available roles:[/]")
        for role in available_roles:
            if role in suggestions:
                _utils.console.print(f"  [green]✓ {role}[/] [dim](suggested)[/]")
            else:
                _utils.console.print(f"  • {role}")
    else:
        _utils.console.print(
            "[yellow]Warning:[/] Could not query available roles for this account"
        )

    _utils.console.print("\n[bold]Next steps:[/]")
    _utils.console.print("[dim]1. Choose a valid role from the list above[/]")
    _utils.console.print(
        "[dim]2. Run: cloudctl switch <org> --account <id> --role <name> --region <region>[/]"
    )
    _utils.console.print("[dim]3. Or run without --role for interactive selection[/]")


def validate_and_prompt_for_role(
    org_data: Dict[str, Any],
    token: Any,
    account_id: str,
    requested_role: str,
) -> Optional[str]:
    """
    Validate a requested role and prompt for correction if needed.

    In interactive mode, if the role is invalid:
    1. Show error message with suggestions
    2. Query available roles
    3. Let user pick from available roles

    Args:
        org_data: Organization configuration dict
        token: SSO token from load_active_sso_token
        account_id: AWS account ID
        requested_role: The role name requested by the user

    Returns:
        The validated role name, or None if user cancelled
    """
    from .interactive import _active_org, select_role

    is_valid, _, available_roles = validate_role(
        org_data, token, account_id, requested_role
    )

    if is_valid:
        return requested_role

    # Role is invalid — show error and suggestions
    org_name = org_data.get("name", "unknown")
    show_role_error_and_suggestions(
        requested_role, available_roles, account_id, org_name
    )

    # If we have an active org context, allow interactive selection
    if _active_org:
        _utils.console.print("\n[dim]Attempting interactive selection...[/]")
        try:
            selected = select_role(org_data, available_roles)
            if selected:
                _utils.console.print(f"[green]✓ Selected: {selected}[/]")
                return selected
        except Exception as e:
            _utils.console.print(f"[yellow]Interactive selection failed:[/] {e}")

    return None
