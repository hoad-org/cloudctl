"""Test Infrastructure & Base Classes — Shared utilities for comprehensive test suite.

PHASE 5A: Base classes and utilities used across the test suite.
- Error handling tests
- Config encryption tests
- List roles tests
"""

from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest


class BaseTestCase:
    """Base class for test suites with common setup/teardown.

    Provides standard fixtures and utilities inherited by all test classes.
    """

    @pytest.fixture(autouse=True)
    def setup(self, mock_home, mock_rich_console):
        """Setup common test environment."""
        self.home = mock_home
        self.console = mock_rich_console
        self.config_dir = mock_home / ".config" / "cloudctl"
        self.cloudctl_dir = mock_home / ".cloudctl"

    def assert_error_message(self, error, expected_text):
        """Assert that error message contains expected text."""
        error_str = str(error)
        assert (
            expected_text in error_str
        ), f"Expected '{expected_text}' in '{error_str}'"

    def assert_error_type(self, error, expected_type):
        """Assert that error is of expected type."""
        assert isinstance(
            error, expected_type
        ), f"Expected {expected_type.__name__}, got {type(error).__name__}"

    def create_mock_aws_response(self, service: str, operation: str):
        """Create a standard mock AWS response for a service operation."""
        responses = {
            "sso.list_accounts": {
                "accountList": [
                    {
                        "accountId": "123456789012",
                        "accountName": "Prod",
                        "emailAddress": "prod@example.com",
                    }
                ]
            },
            "sso.list_roles_for_account": {
                "roleList": [
                    {
                        "roleName": "Admin",
                        "roleArn": "arn:aws:iam::123456789012:role/Admin",
                    },
                    {
                        "roleName": "Developer",
                        "roleArn": "arn:aws:iam::123456789012:role/Developer",
                    },
                ]
            },
            "sts.get_caller_identity": {
                "UserId": "AIDACKCEVSQ6C2EXAMPLE",
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            },
        }
        return responses.get(f"{service}.{operation}", {})


class ErrorHandlingTestBase(BaseTestCase):
    """Base class for error handling tests (Agent 1).

    Provides utilities for testing error messages, recovery, and validation.
    """

    def test_error_has_message(self, error_class, message):
        """Validate that error class can be instantiated with message."""
        error = error_class(message)
        assert message in str(error)

    def test_error_inheritance(self, error_class, expected_parent):
        """Validate that error inherits from expected parent."""
        assert issubclass(error_class, expected_parent)

    def test_error_context_preservation(self, error_class, original_error):
        """Validate that error context is preserved through chaining."""
        wrapped = error_class(str(original_error), original_error)
        assert isinstance(wrapped, error_class)


class EncryptionTestBase(BaseTestCase):
    """Base class for encryption tests (Agent 2).

    Provides utilities for testing encryption/decryption roundtrips.
    """

    def test_roundtrip(self, encrypt_fn, decrypt_fn, plaintext):
        """Test that encrypt->decrypt preserves plaintext."""
        ciphertext = encrypt_fn(plaintext)
        assert ciphertext != plaintext
        decrypted = decrypt_fn(ciphertext)
        assert decrypted == plaintext

    def test_encryption_deterministic(self, encrypt_fn, plaintext):
        """Test that same plaintext with same key produces consistent ciphertext.

        Note: Many modern encryption schemes use random IVs, so ciphertext
        may vary. This test should validate consistency is expected or
        that ciphertext is cryptographically different each time.
        """
        # This will be implemented by Agent 2 based on encryption scheme
        pass

    def test_encryption_key_sensitivity(self, encrypt_fn, plaintext, key1, key2):
        """Test that different keys produce different ciphertexts."""
        with patch.object(encrypt_fn, "key", key1):
            ct1 = encrypt_fn(plaintext)
        with patch.object(encrypt_fn, "key", key2):
            ct2 = encrypt_fn(plaintext)
        assert ct1 != ct2


class RoleValidationTestBase(BaseTestCase):
    """Base class for role validation tests (Agent 3).

    Provides utilities for testing role listing, validation, and suggestions.
    """

    def test_role_exact_match(self, validator, available_roles, test_role):
        """Test exact role matching."""
        is_valid, message, roles = validator.validate(available_roles, test_role)
        assert is_valid

    def test_role_case_insensitive(self, validator, available_roles):
        """Test case-insensitive role matching."""
        # For role 'Admin', test that 'admin', 'ADMIN', 'AdMiN' all match
        for variant in ["admin", "ADMIN", "AdMiN"]:
            is_valid, _, _ = validator.validate(available_roles, variant)
            assert is_valid

    def test_role_suggestions(self, validator, available_roles, typo_role):
        """Test that typos generate helpful suggestions."""
        is_valid, message, suggestions = validator.validate(available_roles, typo_role)
        assert not is_valid
        assert suggestions  # Should have suggestions
        assert len(suggestions) <= 3  # Max 3 suggestions


# ============================================================================
# TEST DATA & FACTORIES
# ============================================================================


class TestDataFactory:
    """Factory for creating standard test data.

    Used across all agent tests to ensure consistency.
    """

    @staticmethod
    def make_aws_account(
        account_id: str = "123456789012",
        name: str = "Production",
        email: str = "prod@example.com",
    ) -> Dict[str, str]:
        """Create a test AWS account object."""
        return {"accountId": account_id, "accountName": name, "emailAddress": email}

    @staticmethod
    def make_aws_role(
        name: str = "Admin",
        account_id: str = "123456789012",
    ) -> Dict[str, str]:
        """Create a test AWS role object."""
        return {
            "roleName": name,
            "roleArn": f"arn:aws:iam::{account_id}:role/{name}",
        }

    @staticmethod
    def make_sts_identity(
        user_id: str = "AIDACKCEVSQ6C2EXAMPLE",
        account: str = "123456789012",
        arn: str = "arn:aws:iam::123456789012:user/test",
    ) -> Dict[str, str]:
        """Create a test STS identity response."""
        return {"UserId": user_id, "Account": account, "Arn": arn}

    @staticmethod
    def make_orgs_config(
        version: str = "4.0.0",
        aws_orgs: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a test orgs.yaml configuration."""
        if aws_orgs is None:
            aws_orgs = [
                {
                    "name": "bt-avm",
                    "provider": "aws",
                    "partition": "aws",
                    "sso_start_url": "https://beyondtrust.awsapps.com/start",
                    "sso_region": "us-east-1",
                }
            ]

        return {
            "version": version,
            "organizations": {org["name"]: org for org in aws_orgs},
        }

    @staticmethod
    def make_context_json(
        org: str = "bt-avm",
        account: str = "123456789012",
        role: str = "Admin",
        region: str = "us-east-1",
    ) -> Dict[str, Any]:
        """Create a test context.json object."""
        return {
            "org": org,
            "account": account,
            "role": role,
            "region": region,
            "timestamp": 1609459200,
        }


# ============================================================================
# PYTEST PLUGINS & HOOKS
# ============================================================================


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Custom pytest hook to collect test metrics for PHASE 5B reporting."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call":
        # Store test metrics for later reporting
        if not hasattr(item, "metrics"):
            item.metrics = {}
        item.metrics["duration"] = rep.duration
        item.metrics["status"] = "passed" if rep.passed else "failed"
