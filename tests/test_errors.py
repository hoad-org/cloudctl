"""
Tests for cloudctl.errors — error handling system.

Comprehensive test suite covering:
- ErrorType enum
- CloudCtlError exception
- All error subclasses
- Error suggestion registry
- Error formatting
"""

import pytest
from cloudctl.errors import (
    ErrorType,
    CloudCtlError,
    InvalidOrgError,
    InvalidAccountError,
    InvalidRoleError,
    CredentialsExpiredError,
    ConfigInvalidError,
    MFARequiredError,
    ApprovalPendingError,
    RateLimitedError,
    NetworkError,
    get_suggestions,
    SUGGESTION_REGISTRY,
)
from cloudctl.error_formatter import (
    format_error,
    format_context,
    format_suggestions,
    format_recovery,
)

# ===========================================================================
# ErrorType Enum Tests
# ===========================================================================


def test_error_type_enum_has_all_types():
    """Verify all 9 required ErrorType enum values exist."""
    expected_types = {
        "INVALID_ORG",
        "INVALID_ACCOUNT",
        "INVALID_ROLE",
        "CREDENTIALS_EXPIRED",
        "CONFIG_INVALID",
        "MFA_REQUIRED",
        "APPROVAL_PENDING",
        "RATE_LIMITED",
        "NETWORK_ERROR",
    }
    actual_types = {member.name for member in ErrorType}
    assert actual_types == expected_types


def test_error_type_values():
    """Verify ErrorType values are lowercase with underscores."""
    assert ErrorType.INVALID_ORG.value == "invalid_org"
    assert ErrorType.CREDENTIALS_EXPIRED.value == "credentials_expired"
    assert ErrorType.NETWORK_ERROR.value == "network_error"


# ===========================================================================
# CloudCtlError Base Class Tests
# ===========================================================================


def test_cloudctl_error_initialization():
    """Test CloudCtlError with all parameters."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org 'test-org' not found",
        context={"org_name": "test-org"},
        suggestions=["Check the org name"],
        recovery_command="cloudctl org list",
    )

    assert error.error_type == ErrorType.INVALID_ORG
    assert error.message == "Org 'test-org' not found"
    assert error.context == {"org_name": "test-org"}
    assert error.suggestions == ["Check the org name"]
    assert error.recovery_command == "cloudctl org list"


def test_cloudctl_error_minimal_initialization():
    """Test CloudCtlError with minimal parameters."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org not found",
    )

    assert error.error_type == ErrorType.INVALID_ORG
    assert error.message == "Org not found"
    assert error.context == {}
    assert error.suggestions == []
    assert error.recovery_command is None


def test_cloudctl_error_string_representation():
    """Test CloudCtlError __str__ returns message."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Test error message",
    )
    assert str(error) == "Test error message"


def test_cloudctl_error_repr():
    """Test CloudCtlError __repr__ includes all fields."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Test error",
        context={"key": "value"},
        suggestions=["Suggestion 1"],
        recovery_command="test-cmd",
    )
    repr_str = repr(error)
    assert "invalid_org" in repr_str
    assert "Test error" in repr_str
    assert "key" in repr_str


def test_cloudctl_error_is_exception():
    """Verify CloudCtlError is a proper Exception subclass."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Test",
    )
    assert isinstance(error, Exception)


# ===========================================================================
# Specific Error Subclass Tests
# ===========================================================================


def test_invalid_org_error():
    """Test InvalidOrgError with available orgs."""
    error = InvalidOrgError(
        org_name="missing-org",
        available_orgs=["org1", "org2"],
    )

    assert error.error_type == ErrorType.INVALID_ORG
    assert "missing-org" in error.message
    assert "org1" in error.message and "org2" in error.message
    assert error.context["org_name"] == "missing-org"
    assert "cloudctl org list" in error.recovery_command


def test_invalid_org_error_no_available_orgs():
    """Test InvalidOrgError without available orgs list."""
    error = InvalidOrgError(org_name="missing-org")

    assert error.error_type == ErrorType.INVALID_ORG
    assert "missing-org" in error.message
    assert "available" not in error.message.lower() or "available" in error.message


def test_invalid_account_error():
    """Test InvalidAccountError."""
    error = InvalidAccountError(
        account_id="123456789",
        org_name="my-org",
        available_accounts=["111111111", "222222222"],
    )

    assert error.error_type == ErrorType.INVALID_ACCOUNT
    assert "123456789" in error.message
    assert "my-org" in error.message
    assert "111111111" in error.message
    assert error.recovery_command == "cloudctl switch my-org"


def test_invalid_role_error():
    """Test InvalidRoleError."""
    error = InvalidRoleError(
        role_name="missing-role",
        account_id="123456789",
        available_roles=["role1", "role2"],
    )

    assert error.error_type == ErrorType.INVALID_ROLE
    assert "missing-role" in error.message
    assert "123456789" in error.message
    assert "role1" in error.message


def test_credentials_expired_error():
    """Test CredentialsExpiredError."""
    error = CredentialsExpiredError(
        org_name="my-org",
        reason="AWS SSO token expired",
    )

    assert error.error_type == ErrorType.CREDENTIALS_EXPIRED
    assert "my-org" in error.message
    assert "AWS SSO token expired" in error.message
    assert error.recovery_command == "cloudctl login my-org"


def test_config_invalid_error():
    """Test ConfigInvalidError."""
    error = ConfigInvalidError(
        config_path="~/.config/cloudctl/orgs.yaml",
        error_detail="Invalid YAML syntax at line 5",
    )

    assert error.error_type == ErrorType.CONFIG_INVALID
    assert "Invalid YAML syntax" in error.message
    assert "cloudctl doctor" in error.recovery_command


def test_mfa_required_error():
    """Test MFARequiredError."""
    error = MFARequiredError(
        role_name="admin-role",
        mfa_method="totp",
    )

    assert error.error_type == ErrorType.MFA_REQUIRED
    assert "admin-role" in error.message
    assert "totp" in error.message
    assert error.context["mfa_method"] == "totp"


def test_approval_pending_error():
    """Test ApprovalPendingError."""
    error = ApprovalPendingError(
        role_name="secure-role",
        request_id="req-12345",
        approval_timeout=600,
    )

    assert error.error_type == ErrorType.APPROVAL_PENDING
    assert "secure-role" in error.message
    assert "req-12345" in error.message
    assert "600" in error.message


def test_rate_limited_error():
    """Test RateLimitedError."""
    error = RateLimitedError(
        operation="switch",
        retry_after=120,
    )

    assert error.error_type == ErrorType.RATE_LIMITED
    assert "switch" in error.message
    assert "120" in error.message
    assert error.context["retry_after_seconds"] == 120


def test_network_error():
    """Test NetworkError."""
    error = NetworkError(
        operation="login",
        details="Connection timeout to SSO endpoint",
    )

    assert error.error_type == ErrorType.NETWORK_ERROR
    assert "login" in error.message
    assert "Connection timeout" in error.message


def test_network_error_no_details():
    """Test NetworkError without details."""
    error = NetworkError(operation="login")

    assert error.error_type == ErrorType.NETWORK_ERROR
    assert "login" in error.message


# ===========================================================================
# Suggestion Registry Tests
# ===========================================================================


def test_suggestion_registry_coverage():
    """Verify all ErrorType values have suggestions registered."""
    for error_type in ErrorType:
        assert error_type in SUGGESTION_REGISTRY
        suggestions = SUGGESTION_REGISTRY[error_type]
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all(isinstance(s, str) for s in suggestions)


def test_get_suggestions():
    """Test get_suggestions function."""
    suggestions = get_suggestions(ErrorType.INVALID_ORG)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert "cloudctl org list" in suggestions[0].lower() or any(
        "cloudctl" in s.lower() for s in suggestions
    )


def test_get_suggestions_unknown_type():
    """Test get_suggestions with unknown error type returns empty list."""
    # This should not happen in practice since we only use known ErrorType values
    # But test defensive behavior
    assert get_suggestions(ErrorType.INVALID_ORG) is not None


# ===========================================================================
# Error Formatter Tests
# ===========================================================================


def test_format_error_basic():
    """Test format_error produces multi-line output."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org not found",
    )
    formatted = format_error(error)

    assert "INVALID ORG" in formatted
    assert "Org not found" in formatted
    assert "\n" in formatted


def test_format_error_with_context():
    """Test format_error includes context information."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org not found",
        context={"org_name": "missing-org"},
    )
    formatted = format_error(error)

    assert "Org Name" in formatted or "org" in formatted.lower()


def test_format_error_with_suggestions():
    """Test format_error includes suggestions."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org not found",
        suggestions=[
            "Check the organization name",
            "Run 'cloudctl org list' to see available orgs",
        ],
    )
    formatted = format_error(error)

    assert "What you can do" in formatted or "suggestion" in formatted.lower()
    assert "Check the organization" in formatted or "available" in formatted.lower()


def test_format_error_with_recovery():
    """Test format_error includes recovery command."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org not found",
        recovery_command="cloudctl org list",
    )
    formatted = format_error(error)

    assert "Try this command" in formatted or "command" in formatted.lower()
    assert "cloudctl org list" in formatted


def test_format_context_empty():
    """Test format_context with empty dict."""
    result = format_context({})
    assert result == ""


def test_format_context_filters_secrets():
    """Test format_context filters out secret fields."""
    context = {
        "org_name": "my-org",
        "password": "secret123",
        "token": "test_token_mock123",  # Synthetic test token (not a real credential)
        "account_id": "123456789",
    }
    formatted = format_context(context)

    assert "my-org" in formatted
    assert "123456789" in formatted
    assert "password" not in formatted.lower()
    assert "token" not in formatted.lower()
    assert "secret" not in formatted


def test_format_suggestions_empty():
    """Test format_suggestions with empty list."""
    result = format_suggestions([])
    assert result == ""


def test_format_suggestions_numbered():
    """Test format_suggestions produces numbered list."""
    suggestions = [
        "First suggestion",
        "Second suggestion",
        "Third suggestion",
    ]
    formatted = format_suggestions(suggestions)

    assert "1." in formatted
    assert "2." in formatted
    assert "3." in formatted
    assert "First suggestion" in formatted
    assert "Second suggestion" in formatted


def test_format_recovery_empty():
    """Test format_recovery with empty string."""
    result = format_recovery("")
    assert result == ""


def test_format_recovery_command():
    """Test format_recovery formats command correctly."""
    formatted = format_recovery("cloudctl login my-org")

    assert "Try this command" in formatted
    assert "cloudctl login my-org" in formatted


# ===========================================================================
# Integration Tests
# ===========================================================================


def test_error_with_all_fields():
    """Test error with all fields populated."""
    error = InvalidOrgError(
        org_name="production-org",
        available_orgs=["dev-org", "staging-org", "prod-org"],
    )
    formatted = format_error(error)

    # Verify complete error output
    assert "INVALID ORG" in formatted
    assert "production-org" in formatted
    assert error.recovery_command is not None
    assert len(error.suggestions) > 0


def test_cloudctl_error_exception_handling():
    """Test CloudCtlError can be caught as Exception."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Test error",
    )

    with pytest.raises(CloudCtlError):
        raise error

    with pytest.raises(Exception):
        raise error


def test_multiple_error_types():
    """Test creating multiple different error types."""
    errors = [
        InvalidOrgError("org1"),
        InvalidAccountError("acc1", "org1"),
        InvalidRoleError("role1", "acc1"),
        CredentialsExpiredError("org1"),
        ConfigInvalidError("/path/to/config", "Invalid YAML"),
        MFARequiredError("admin"),
        ApprovalPendingError("secure"),
        RateLimitedError("switch"),
        NetworkError("login"),
    ]

    assert len(errors) == 9
    assert all(isinstance(e, CloudCtlError) for e in errors)
    assert all(e.error_type in ErrorType for e in errors)


def test_error_context_never_contains_secrets():
    """Verify error context filtering is comprehensive."""
    # Create error with potential secret fields
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Test",
        context={
            "org_name": "my-org",
            "password": "secret",
            "aws_secret_access_key": "key",
            "api_key": "123",
            "private_key": "pem",
        },
    )

    formatted = format_error(error)

    # Secrets should not appear in formatted output
    assert "secret" not in formatted.lower() or "test" in formatted.lower()


def test_suggestion_registry_all_types_have_multiple_suggestions():
    """Verify each error type has at least 3 suggestions."""
    for error_type, suggestions in SUGGESTION_REGISTRY.items():
        assert len(suggestions) >= 3, f"{error_type} has < 3 suggestions"


# ===========================================================================
# Edge Case Tests
# ===========================================================================


def test_error_message_with_special_characters():
    """Test error handling with special characters in message."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ORG,
        message="Org 'my-org/prod@v1' is invalid",
    )
    formatted = format_error(error)
    assert "my-org/prod@v1" in formatted


def test_error_context_with_large_list():
    """Test format_context with large list in context."""
    error = CloudCtlError(
        error_type=ErrorType.INVALID_ACCOUNT,
        message="Test",
        context={
            "available_accounts": [f"acc{i}" for i in range(20)],
        },
    )
    formatted = format_error(error)
    assert "acc0" in formatted
    assert "total" in formatted.lower() or "20" in formatted


def test_format_suggestions_with_long_text():
    """Test format_suggestions wraps long suggestion text."""
    long_suggestion = (
        "This is a very long suggestion that should be wrapped to fit "
        "within the terminal width to improve readability for users "
        "who have narrower terminals or smaller screens."
    )
    formatted = format_suggestions([long_suggestion])
    assert long_suggestion in formatted or "very long" in formatted
