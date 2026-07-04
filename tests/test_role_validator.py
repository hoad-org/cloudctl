"""Tests for role_validator module."""

import pytest

from cloudctl.role_validator import (
    find_role_suggestions,
    get_available_roles,
    validate_role,
)


class MockProvider:
    """Mock provider for testing."""

    def __init__(self, roles=None):
        self.roles = roles or []

    def list_roles(self, org_data, token, account_id):
        return self.roles


@pytest.fixture
def mock_org_data():
    return {
        "name": "test-org",
        "provider": "aws",
        "sso_start_url": "https://example.com",
        "sso_region": "us-east-1",
    }


@pytest.fixture
def mock_token():
    return "mock-token-12345"


class TestFindRoleSuggestions:
    """Test find_role_suggestions function."""

    def test_exact_case_insensitive_match(self):
        """Should find exact match case-insensitively."""
        available = ["AdministratorAccess", "ReadOnlyAccess", "PowerUserAccess"]
        suggestions = find_role_suggestions("administratoraccess", available)
        assert suggestions[0] == "AdministratorAccess"

    def test_substring_match(self):
        """Should find substring matches."""
        available = ["PowerUserAccess", "SecurityAuditAccess", "ReadOnlyAccess"]
        suggestions = find_role_suggestions("Security", available)
        assert "SecurityAuditAccess" in suggestions

    def test_typo_correction(self):
        """Should find similar names for typos."""
        available = ["AdministratorAccess", "ReadOnlyAccess", "DeveloperAccess"]
        suggestions = find_role_suggestions("AdminAccess", available)
        # Should suggest AdministratorAccess as it's most similar
        assert suggestions  # Non-empty

    def test_no_matches(self):
        """Should return empty list when no matches."""
        available = ["AdministratorAccess", "ReadOnlyAccess"]
        suggestions = find_role_suggestions("XyzInvalidRole", available)
        assert len(suggestions) == 0

    def test_max_suggestions_limit(self):
        """Should respect max_suggestions parameter."""
        available = [
            "AdminAccess",
            "Administrator",
            "AdminRole",
            "AdminUser",
            "AdminRead",
        ]
        suggestions = find_role_suggestions("Admin", available, max_suggestions=2)
        assert len(suggestions) <= 2

    def test_empty_available_roles(self):
        """Should handle empty role list gracefully."""
        suggestions = find_role_suggestions("Admin", [])
        assert suggestions == []


class TestValidateRole:
    """Test validate_role function."""

    def test_role_exists_exact_match(self, mock_org_data, mock_token, monkeypatch):
        """Should validate role when exact match exists."""
        available_roles = ["AdministratorAccess", "ReadOnlyAccess"]

        def mock_get_available_roles(org, token, account):
            return available_roles

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "123456789", "AdministratorAccess"
        )

        assert is_valid is True
        assert message is None
        assert roles == available_roles

    def test_role_not_found(self, mock_org_data, mock_token, monkeypatch):
        """Should fail validation when role doesn't exist."""
        available_roles = ["AdministratorAccess", "ReadOnlyAccess"]

        def mock_get_available_roles(org, token, account):
            return available_roles

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "123456789", "InvalidRole"
        )

        assert is_valid is False
        assert "not found" in message.lower()
        assert roles == available_roles

    def test_role_case_insensitive_match(self, mock_org_data, mock_token, monkeypatch):
        """Should match role case-insensitively."""
        available_roles = ["AdministratorAccess", "ReadOnlyAccess"]

        def mock_get_available_roles(org, token, account):
            return available_roles

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "123456789", "administratoraccess"
        )

        assert is_valid is True
        assert message is None

    def test_empty_available_roles(self, mock_org_data, mock_token, monkeypatch):
        """Should handle empty role list."""

        def mock_get_available_roles(org, token, account):
            return []

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "123456789", "SomeRole"
        )

        assert is_valid is False
        assert roles == []


class TestGetAvailableRoles:
    """Test get_available_roles function."""

    def test_get_roles_success(self, mock_org_data, mock_token, monkeypatch):
        """Should return roles from provider."""
        test_roles = ["Role1", "Role2", "Role3"]

        def mock_get_provider(org):
            provider = MockProvider(roles=test_roles)
            return provider

        monkeypatch.setattr("cloudctl.providers.get_provider", mock_get_provider)

        roles = get_available_roles(mock_org_data, mock_token, "123456789")

        assert roles == test_roles

    def test_get_roles_provider_error(self, mock_org_data, mock_token, monkeypatch):
        """Should handle provider errors gracefully."""

        def mock_get_provider(org):
            class ErrorProvider:
                def list_roles(self, *args):
                    raise RuntimeError("API Error")

            return ErrorProvider()

        monkeypatch.setattr("cloudctl.providers.get_provider", mock_get_provider)

        # Should not raise, just return empty list
        roles = get_available_roles(mock_org_data, mock_token, "123456789")

        assert roles == []


class TestRoleValidationIntegration:
    """Integration tests for role validation flow."""

    def test_full_validation_workflow_success(
        self, mock_org_data, mock_token, monkeypatch
    ):
        """Should validate a correct role end-to-end."""
        available_roles = [
            "AdministratorAccess",
            "PowerUserAccess",
            "ReadOnlyAccess",
        ]

        def mock_get_available_roles(org, token, account):
            return available_roles

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "235494790978", "AdministratorAccess"
        )

        assert is_valid is True
        assert message is None
        assert "AdministratorAccess" in roles

    def test_full_validation_workflow_failure_with_suggestions(
        self, mock_org_data, mock_token, monkeypatch
    ):
        """Should provide suggestions when role validation fails."""
        available_roles = [
            "AdministratorAccess",
            "PowerUserAccess",
            "ReadOnlyAccess",
        ]

        def mock_get_available_roles(org, token, account):
            return available_roles

        monkeypatch.setattr(
            "cloudctl.role_validator.get_available_roles", mock_get_available_roles
        )

        # User provided "admin" instead of "AdministratorAccess"
        is_valid, message, roles = validate_role(
            mock_org_data, mock_token, "235494790978", "admin"
        )

        assert is_valid is False
        assert message is not None
        assert roles == available_roles

        # Check that we can find suggestions
        suggestions = find_role_suggestions("admin", available_roles)
        assert len(suggestions) > 0
        assert "AdministratorAccess" in suggestions
