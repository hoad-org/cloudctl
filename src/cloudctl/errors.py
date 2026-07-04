"""
cloudctl.errors — Comprehensive error handling system with recovery suggestions.

This module provides:
- ErrorType enum for categorizing error conditions
- CloudCtlError exception with context, suggestions, and recovery guidance
- Suggestion registry mapping error types to actionable help text
"""

from enum import Enum
from typing import Dict, List, Optional, Any


class ErrorType(Enum):
    """Enumeration of all possible error types in cloudctl."""

    INVALID_ORG = "invalid_org"
    INVALID_ACCOUNT = "invalid_account"
    INVALID_ROLE = "invalid_role"
    CREDENTIALS_EXPIRED = "credentials_expired"
    CONFIG_INVALID = "config_invalid"
    NETWORK_ERROR = "network_error"


class CloudCtlError(Exception):
    """
    Base exception for all cloudctl errors.

    Attributes:
        error_type: The ErrorType categorizing this error
        message: Human-readable error description
        context: Dict with diagnostic context (no secrets)
        suggestions: List of actionable suggestions
        recovery_command: Optional suggested command to fix the issue
    """

    # Default exit code for base error — can be overridden in subclasses
    exit_code = 1

    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        recovery_command: Optional[str] = None,
    ):
        """
        Initialize a CloudCtlError.

        Args:
            error_type: The ErrorType for this error
            message: Human-readable error description
            context: Diagnostic context dict (secrets filtered)
            suggestions: List of actionable suggestions
            recovery_command: Optional command to recover from this error
        """
        self.error_type = error_type
        self.message = message
        self.context = context or {}
        self.suggestions = suggestions or []
        self.recovery_command = recovery_command

        super().__init__(self.message)

    def __str__(self) -> str:
        """Return the error message."""
        return self.message

    def __repr__(self) -> str:
        """Return a detailed representation."""
        return (
            f"CloudCtlError(error_type={self.error_type.value}, "
            f"message={self.message!r}, context={self.context}, "
            f"suggestions={self.suggestions}, recovery_command={self.recovery_command!r})"
        )


# Suggestion registry: maps ErrorType to list of helpful suggestions
SUGGESTION_REGISTRY: Dict[ErrorType, List[str]] = {
    ErrorType.INVALID_ORG: [
        "Check the organization name is correct: cloudctl org list",
        "Verify the org is configured in ~/.config/cloudctl/orgs.yaml",
        "Use 'cloudctl init' to interactively set up organizations",
        "Contact your CloudOps team if the org is missing from configuration",
    ],
    ErrorType.INVALID_ACCOUNT: [
        "Verify the account ID matches one of your org's configured accounts",
        "Run 'cloudctl switch <org>' to see available accounts",
        "Check your organization's account list in orgs.yaml",
        "Ensure you have access permission for this account (check with admin)",
    ],
    ErrorType.INVALID_ROLE: [
        "Verify the role name is correct and available for this account",
        "Run 'cloudctl switch <org> <account>' to see available roles",
        "Check your RBAC permissions with the account owner",
        "Some roles require approval—contact your administrator",
    ],
    ErrorType.CREDENTIALS_EXPIRED: [
        "Your AWS SSO token has expired—re-authenticate with your identity provider",
        "Run 'cloudctl login <org>' to refresh your credentials",
        "Clear the cached token: cloudctl cache-clear",
        "After login, switch accounts: cloudctl switch <org> <account> <role>",
    ],
    ErrorType.CONFIG_INVALID: [
        "Run 'cloudctl doctor' to diagnose configuration issues",
        "Validate YAML syntax: python3 -c \"import yaml; yaml.safe_load(open('~/.config/cloudctl/orgs.yaml'))\"",
        "Backup your current config and run 'cloudctl init' to recreate it",
        "Check ~/.config/cloudctl/orgs.yaml for schema violations",
    ],
    ErrorType.NETWORK_ERROR: [
        "Check your network connection: ping 8.8.8.8",
        "Verify you can reach the identity provider (check firewall/proxy)",
        "Run 'cloudctl doctor' to diagnose network issues",
        "Try again in a few moments—may be a transient network issue",
    ],
}


def get_suggestions(error_type: ErrorType) -> List[str]:
    """
    Get suggestions for an error type.

    Args:
        error_type: The ErrorType to get suggestions for

    Returns:
        List of suggestion strings, or empty list if no suggestions
    """
    return SUGGESTION_REGISTRY.get(error_type, [])


# Specific exception subclasses for common error patterns


class InvalidOrgError(CloudCtlError):
    """Raised when the specified organization is invalid or not found."""

    exit_code = 3

    def __init__(self, org_name: str, available_orgs: Optional[List[str]] = None):
        """
        Initialize InvalidOrgError.

        Args:
            org_name: The organization name that was not found
            available_orgs: List of available organization names
        """
        context = {"org_name": org_name}
        if available_orgs:
            context["available_orgs"] = available_orgs

        message = f"Organization '{org_name}' not found"
        if available_orgs:
            message += f" (available: {', '.join(available_orgs)})"

        super().__init__(
            error_type=ErrorType.INVALID_ORG,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.INVALID_ORG),
            recovery_command="cloudctl org list",
        )


class InvalidAccountError(CloudCtlError):
    """Raised when the specified account is invalid or not found."""

    exit_code = 3

    def __init__(
        self,
        account_id: str,
        org_name: str,
        available_accounts: Optional[List[str]] = None,
    ):
        """
        Initialize InvalidAccountError.

        Args:
            account_id: The account ID that was not found
            org_name: The organization name for context
            available_accounts: List of available account IDs
        """
        context = {"account_id": account_id, "org_name": org_name}
        if available_accounts:
            context["available_accounts"] = available_accounts

        message = f"Account '{account_id}' not found in organization '{org_name}'"
        if available_accounts:
            message += f" (available: {', '.join(available_accounts)})"

        super().__init__(
            error_type=ErrorType.INVALID_ACCOUNT,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.INVALID_ACCOUNT),
            recovery_command=f"cloudctl switch {org_name}",
        )


class InvalidRoleError(CloudCtlError):
    """Raised when the specified role is invalid or not found."""

    exit_code = 3

    def __init__(
        self,
        role_name: str,
        account_id: str,
        available_roles: Optional[List[str]] = None,
    ):
        """
        Initialize InvalidRoleError.

        Args:
            role_name: The role name that was not found
            account_id: The account ID for context
            available_roles: List of available role names
        """
        context = {"role_name": role_name, "account_id": account_id}
        if available_roles:
            context["available_roles"] = available_roles

        message = f"Role '{role_name}' not found for account '{account_id}'"
        if available_roles:
            message += f" (available: {', '.join(available_roles)})"

        super().__init__(
            error_type=ErrorType.INVALID_ROLE,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.INVALID_ROLE),
            recovery_command=f"cloudctl switch {account_id}",
        )


class CredentialsExpiredError(CloudCtlError):
    """Raised when credentials have expired and need to be refreshed."""

    exit_code = 2

    def __init__(self, org_name: str, reason: str = "Token expired"):
        """
        Initialize CredentialsExpiredError.

        Args:
            org_name: The organization for which credentials expired
            reason: Detailed reason for expiration
        """
        context = {"org_name": org_name, "reason": reason}

        message = f"Credentials expired for organization '{org_name}': {reason}"

        super().__init__(
            error_type=ErrorType.CREDENTIALS_EXPIRED,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.CREDENTIALS_EXPIRED),
            recovery_command=f"cloudctl login {org_name}",
        )


class ConfigInvalidError(CloudCtlError):
    """Raised when the configuration file is invalid."""

    exit_code = 5

    def __init__(self, config_path: str, error_detail: str):
        """
        Initialize ConfigInvalidError.

        Args:
            config_path: Path to the invalid configuration file
            error_detail: Details about what's invalid
        """
        context = {"config_path": config_path, "error_detail": error_detail}

        message = f"Configuration file '{config_path}' is invalid: {error_detail}"

        super().__init__(
            error_type=ErrorType.CONFIG_INVALID,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.CONFIG_INVALID),
            recovery_command="cloudctl doctor",
        )


class NetworkError(CloudCtlError):
    """Raised when a network error occurs."""

    exit_code = 1

    def __init__(self, operation: str, details: str = ""):
        """
        Initialize NetworkError.

        Args:
            operation: The operation that failed due to network error
            details: Additional details about the network error
        """
        context = {"operation": operation}
        if details:
            context["details"] = details

        message = f"Network error during '{operation}'"
        if details:
            message += f": {details}"

        super().__init__(
            error_type=ErrorType.NETWORK_ERROR,
            message=message,
            context=context,
            suggestions=get_suggestions(ErrorType.NETWORK_ERROR),
        )
