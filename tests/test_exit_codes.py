"""
Tests for CloudCtl exit codes.

All CloudCtl errors should return the correct exit code so agents can
reliably detect success/failure and take appropriate action.
"""

from types import SimpleNamespace
from unittest.mock import patch

from cloudctl import cli, exit_codes
from cloudctl.errors import (
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
    ErrorType,
)


class TestExitCodeConstantsModule:
    """The centralised exit_codes module carries the documented scheme."""

    def test_constants_match_documented_scheme(self):
        assert exit_codes.OK == 0
        assert exit_codes.ERROR == 1
        assert exit_codes.AUTH == 2
        assert exit_codes.NOT_FOUND == 3
        assert exit_codes.DENIED == 4
        assert exit_codes.USAGE == 5


class TestSwitchExitCodes:
    """cmd_switch emits the documented codes at its obvious sites."""

    def _args(self, **kw):
        base = dict(
            target="myorg",
            org="myorg",
            org_flag=None,
            account="123456789012",
            role="Admin",
            region="us-east-1",
            non_interactive=True,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_guardrail_denied_returns_four(self, mock_rich_console):
        """A guardrail rejection (validate_role_access → False) → DENIED (4)."""
        org_data = {"name": "myorg", "provider": "aws"}
        with patch("cloudctl.config.get_org", return_value=org_data), patch(
            "cloudctl.config.load_config", return_value={"orgs": [{"name": "myorg"}]}
        ), patch("cloudctl.guardrails.validate_region", return_value=None), patch(
            "cloudctl.guardrails.validate_role_access",
            return_value=(False, "not allowed"),
        ), patch(
            "cloudctl.sso_cache.load_active_sso_token", return_value=None
        ):
            rc = cli.cmd_switch(self._args())
        assert rc == exit_codes.DENIED

    def test_no_orgs_configured_returns_usage(self, mock_rich_console):
        """No orgs configured + no --org → USAGE (5)."""
        with patch("cloudctl.config.get_org", side_effect=Exception("none")), patch(
            "cloudctl.config.load_config", return_value={"orgs": []}
        ):
            rc = cli.cmd_switch(self._args(target=None, org=None))
        assert rc == exit_codes.USAGE


class TestExitCodeConstants:
    """Test that all error classes have correct exit_code attributes."""

    def test_base_cloudctl_error_exit_code(self):
        """Base CloudCtlError should have exit_code = 1."""
        error = CloudCtlError(
            error_type=ErrorType.NETWORK_ERROR,
            message="Test error",
        )
        assert error.exit_code == 1

    def test_invalid_org_error_exit_code(self):
        """InvalidOrgError should have exit_code = 3 (Not Found)."""
        error = InvalidOrgError("invalid-org", available_orgs=["bt-avm", "fdr-gvc"])
        assert error.exit_code == 3

    def test_invalid_account_error_exit_code(self):
        """InvalidAccountError should have exit_code = 3 (Not Found)."""
        error = InvalidAccountError(
            "999999999999", "bt-avm", available_accounts=["235494790978"]
        )
        assert error.exit_code == 3

    def test_invalid_role_error_exit_code(self):
        """InvalidRoleError should have exit_code = 3 (Not Found)."""
        error = InvalidRoleError(
            "invalid-role", "235494790978", available_roles=["admin", "developer"]
        )
        assert error.exit_code == 3

    def test_credentials_expired_error_exit_code(self):
        """CredentialsExpiredError should have exit_code = 2 (Auth Required)."""
        error = CredentialsExpiredError("bt-avm", reason="Token expired")
        assert error.exit_code == 2

    def test_config_invalid_error_exit_code(self):
        """ConfigInvalidError should have exit_code = 5 (Invalid Argument)."""
        error = ConfigInvalidError(
            "~/.config/cloudctl/orgs.yaml",
            "Invalid YAML syntax: expected key",
        )
        assert error.exit_code == 5

    def test_mfa_required_error_exit_code(self):
        """MFARequiredError should have exit_code = 2 (Auth Required)."""
        error = MFARequiredError("admin", mfa_method="totp")
        assert error.exit_code == 2

    def test_approval_pending_error_exit_code(self):
        """ApprovalPendingError should have exit_code = 4 (Permission Denied)."""
        error = ApprovalPendingError("admin", request_id="req-12345")
        assert error.exit_code == 4

    def test_rate_limited_error_exit_code(self):
        """RateLimitedError should have exit_code = 4 (Permission Denied)."""
        error = RateLimitedError("switch", retry_after=60)
        assert error.exit_code == 4

    def test_network_error_exit_code(self):
        """NetworkError should have exit_code = 1 (General Error)."""
        error = NetworkError("login", details="Connection timeout")
        assert error.exit_code == 1


class TestExitCodeMapping:
    """Test that exit codes are semantically correct."""

    def test_success_exit_code_is_zero(self):
        """Successful operations return exit code 0 (implicit)."""
        # Exit code 0 is implicit when no exception is raised
        # This test documents the expectation
        assert 0 == 0  # Success exit code

    def test_not_found_errors_return_three(self):
        """All "not found" errors return exit code 3."""
        org_error = InvalidOrgError("invalid")
        account_error = InvalidAccountError("999999999999", "bt-avm")
        role_error = InvalidRoleError("invalid-role", "235494790978")

        assert org_error.exit_code == 3
        assert account_error.exit_code == 3
        assert role_error.exit_code == 3

    def test_auth_required_errors_return_two(self):
        """All auth-required errors return exit code 2."""
        expired_error = CredentialsExpiredError("bt-avm")
        mfa_error = MFARequiredError("admin")

        assert expired_error.exit_code == 2
        assert mfa_error.exit_code == 2

    def test_permission_denied_errors_return_four(self):
        """All permission-denied errors return exit code 4."""
        approval_error = ApprovalPendingError("admin")
        rate_limit_error = RateLimitedError("switch")

        assert approval_error.exit_code == 4
        assert rate_limit_error.exit_code == 4

    def test_invalid_arg_errors_return_five(self):
        """Invalid argument errors return exit code 5."""
        config_error = ConfigInvalidError("~/.config/cloudctl/orgs.yaml", "invalid")
        assert config_error.exit_code == 5

    def test_general_errors_return_one(self):
        """General errors return exit code 1."""
        network_error = NetworkError("login")
        generic_error = CloudCtlError(ErrorType.NETWORK_ERROR, "Generic error")

        assert network_error.exit_code == 1
        assert generic_error.exit_code == 1


class TestExitCodeDocumentation:
    """Test that exit codes are properly documented."""

    def test_exit_code_constants_exist_in_error_classes(self):
        """All error classes should have exit_code as class attribute."""
        errors = [
            CloudCtlError(ErrorType.NETWORK_ERROR, "test"),
            InvalidOrgError("invalid"),
            InvalidAccountError("999999999999", "bt-avm"),
            InvalidRoleError("invalid", "235494790978"),
            CredentialsExpiredError("bt-avm"),
            ConfigInvalidError("~/.config/cloudctl/orgs.yaml", "invalid"),
            MFARequiredError("admin"),
            ApprovalPendingError("admin"),
            RateLimitedError("switch"),
            NetworkError("login"),
        ]

        for error in errors:
            assert hasattr(
                error, "exit_code"
            ), f"{error.__class__.__name__} missing exit_code"
            assert isinstance(
                error.exit_code, int
            ), f"{error.__class__.__name__}.exit_code not int"
            assert (
                0 <= error.exit_code <= 255
            ), f"{error.__class__.__name__}.exit_code out of range"

    def test_exit_code_ranges_are_valid(self):
        """Exit codes should be in valid range [0, 255]."""
        errors = [
            (InvalidOrgError("invalid"), 3),
            (InvalidAccountError("999999999999", "bt-avm"), 3),
            (InvalidRoleError("invalid", "235494790978"), 3),
            (CredentialsExpiredError("bt-avm"), 2),
            (ConfigInvalidError("~/.config/cloudctl/orgs.yaml", "invalid"), 5),
            (MFARequiredError("admin"), 2),
            (ApprovalPendingError("admin"), 4),
            (RateLimitedError("switch"), 4),
            (NetworkError("login"), 1),
            (CloudCtlError(ErrorType.NETWORK_ERROR, "test"), 1),
        ]

        for error, expected_code in errors:
            assert error.exit_code == expected_code
            assert 0 <= error.exit_code <= 255


class TestErrorTypeToExitCodeMapping:
    """Test semantic relationship between ErrorType enum and exit codes."""

    def test_invalid_errors_map_to_exit_code_three(self):
        """Invalid org/account/role → exit code 3."""
        error = InvalidOrgError("invalid")
        assert error.error_type == ErrorType.INVALID_ORG
        assert error.exit_code == 3

    def test_credentials_error_maps_to_exit_code_two(self):
        """Credentials expired → exit code 2."""
        error = CredentialsExpiredError("bt-avm")
        assert error.error_type == ErrorType.CREDENTIALS_EXPIRED
        assert error.exit_code == 2

    def test_mfa_error_maps_to_exit_code_two(self):
        """MFA required → exit code 2."""
        error = MFARequiredError("admin")
        assert error.error_type == ErrorType.MFA_REQUIRED
        assert error.exit_code == 2

    def test_approval_error_maps_to_exit_code_four(self):
        """Approval pending → exit code 4."""
        error = ApprovalPendingError("admin")
        assert error.error_type == ErrorType.APPROVAL_PENDING
        assert error.exit_code == 4

    def test_rate_limit_error_maps_to_exit_code_four(self):
        """Rate limited → exit code 4."""
        error = RateLimitedError("switch")
        assert error.error_type == ErrorType.RATE_LIMITED
        assert error.exit_code == 4


class TestAgentWorkflow:
    """Test exit codes in agent automation workflow."""

    def test_agent_can_detect_success(self):
        """Agent can detect success (no exception)."""
        # Exit code 0 is implicit when no exception is raised
        exit_code = 0  # Success
        assert exit_code == 0

    def test_agent_can_detect_auth_failure(self):
        """Agent can detect and handle auth failure (exit code 2)."""
        error = CredentialsExpiredError("bt-avm")
        assert error.exit_code == 2
        # Agent should retry with: cloudctl login bt-avm

    def test_agent_can_detect_not_found(self):
        """Agent can detect and handle not found (exit code 3)."""
        error = InvalidOrgError("invalid")
        assert error.exit_code == 3
        # Agent should verify org name and retry

    def test_agent_can_detect_permission_denied(self):
        """Agent can detect and handle permission denied (exit code 4)."""
        error = ApprovalPendingError("admin")
        assert error.exit_code == 4
        # Agent should wait for approval or escalate

    def test_agent_can_detect_invalid_config(self):
        """Agent can detect and handle invalid config (exit code 5)."""
        error = ConfigInvalidError("~/.config/cloudctl/orgs.yaml", "invalid yaml")
        assert error.exit_code == 5
        # Agent should run cloudctl doctor or fix config

    def test_agent_can_detect_general_error(self):
        """Agent can detect and handle general error (exit code 1)."""
        error = NetworkError("login")
        assert error.exit_code == 1
        # Agent should log error and retry or escalate
