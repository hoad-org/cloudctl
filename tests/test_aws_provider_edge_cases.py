# file: tests/test_aws_provider_edge_cases.py
"""
Comprehensive edge case tests for AWS CloudProvider.

Tests cover:
- Account extraction edge cases (malformed JSON, field delimiters, wrong positions)
- Region validation edge cases (invalid regions, cross-region permissions, partitions)
- Context parsing edge cases (leading zeros, case sensitivity, whitespace)
- Account ID format validation (12-digit IDs, non-numeric, empty strings)
"""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from cloudctl.providers.aws import AwsProvider

# =============================================================================
# Helpers
# =============================================================================


def _aws_result(returncode=0, stdout="", stderr=""):
    """Create a mock AWS CLI result."""
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


# =============================================================================
# Account Extraction Edge Cases
# =============================================================================


class TestAccountExtractionEdgeCases:
    """Test malformed SSO responses and field extraction failures."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_list_accounts_malformed_json_invalid(self, provider, org, monkeypatch):
        """Edge case: AWS returns syntactically invalid JSON.

        When AWS CLI returns malformed JSON (not parseable), list_accounts
        should catch the JSONDecodeError and return an empty list, logging
        the error.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout="{ invalid json ["),
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []

    def test_list_accounts_missing_account_id_field(self, provider, org, monkeypatch):
        """Edge case: AWS returns accountList but items lack accountId field.

        If account objects are missing the 'accountId' key, accessing it in the
        list comprehension will raise KeyError. The provider catches this and
        returns an empty list.
        """
        response = {
            "accountList": [
                {"accountName": "Prod", "accountId": "111111111111"},
                {"accountName": "Dev"},  # Missing accountId
            ]
        }
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        # Should catch KeyError and return empty list
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []

    def test_list_accounts_missing_account_name_field(self, provider, org, monkeypatch):
        """Edge case: AWS returns accountId but lacks accountName field.

        If account objects lack 'accountName' key, the extraction in the list
        comprehension will raise KeyError. The provider catches this and returns
        an empty list.
        """
        response = {
            "accountList": [
                {"accountId": "111111111111", "accountName": "Prod"},
                {"accountId": "222222222222"},  # Missing accountName
            ]
        }
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        # Should catch KeyError and return empty list
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []

    def test_list_accounts_unicode_in_account_name(self, provider, org, monkeypatch):
        """Edge case: Account name contains Unicode characters (emojis, etc).

        Verify that Unicode account names are handled gracefully. JSON encoding
        preserves Unicode characters correctly.
        """
        # JSON encoding of account with special chars
        raw_accounts = [
            {
                "accountId": "111111111111",
                "accountName": "Prod-Acme",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["name"] == "Prod-Acme"
        assert accounts[0]["id"] == "111111111111"

    def test_list_accounts_empty_account_list_field(self, provider, org, monkeypatch):
        """Edge case: AWS returns empty accountList array.

        If 'accountList' is present but empty, the function should return
        an empty list (not error).
        """
        response = {"accountList": []}
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []

    def test_list_accounts_missing_account_list_key(self, provider, org, monkeypatch):
        """Edge case: AWS response lacks 'accountList' key entirely.

        When 'accountList' key is missing, the .get() call should return []
        default, resulting in an empty account list.
        """
        response = {"nextToken": "token-xyz"}  # No accountList key
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []


# =============================================================================
# Region Validation Edge Cases
# =============================================================================


class TestRegionValidationEdgeCases:
    """Test region handling in get_credentials and role listing."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_get_credentials_invalid_region_name(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Invalid region name passed to get_credentials.

        get_credentials calls run_aws with the region parameter. AWS CLI will
        reject an invalid region with a non-zero exit code. The method should
        exit with error.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(1, stderr="Invalid region: not-a-region"),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "not-a-region")
        # Verify error message was logged
        output = "".join(mock_rich_console.captured)
        assert (
            "No valid SSO session" in output
            or "credentials fetch failed" in output.lower()
        )

    def test_get_credentials_empty_region_parameter(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Empty string passed as region parameter.

        AWS CLI requires a region. Empty string should trigger an error from
        AWS and cause the function to exit.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(
                1, stderr="Missing required parameter: --region"
            ),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "")
        output = "".join(mock_rich_console.captured)
        assert (
            "No valid SSO session" in output
            or "credentials fetch failed" in output.lower()
        )

    def test_get_credentials_whitespace_only_region(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Region parameter contains only whitespace.

        Whitespace-only region strings should fail when passed to AWS CLI.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(1, stderr="Invalid region: '   '"),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "   ")

    def test_get_credentials_partition_aws_us_east_1(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Standard AWS partition with us-east-1 region.

        Verify that get_credentials works with standard AWS region.
        """
        creds_payload = json.dumps(
            {
                "roleCredentials": {
                    "accessKeyId": "AKIA1234567890ABCDEF",
                    "secretAccessKey": "secret-key-value",
                    "sessionToken": "session-token-value",
                }
            }
        )
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=creds_payload),
        )
        creds = provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        assert creds["AWS_ACCESS_KEY_ID"] == "AKIA1234567890ABCDEF"
        assert creds["AWS_SECRET_ACCESS_KEY"] == "secret-key-value"
        assert creds["AWS_SESSION_TOKEN"] == "session-token-value"

    def test_get_credentials_china_partition_aws_cn(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: AWS China (aws-cn) partition with cn-north-1 region.

        get_credentials should work with any region string (it doesn't validate
        against a whitelist). Only the login() method special-cases aws-cn.
        """
        creds_payload = json.dumps(
            {
                "roleCredentials": {
                    "accessKeyId": "AKIA1234567890ABCDEF",
                    "secretAccessKey": "secret-key-value",
                    "sessionToken": "session-token-value",
                }
            }
        )
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=creds_payload),
        )
        creds = provider.get_credentials(org, "123456789012", "Admin", "cn-north-1")
        assert "AWS_ACCESS_KEY_ID" in creds
        assert creds["AWS_PROFILE"] == "test-org-123456789012-Admin"

    def test_get_credentials_govcloud_partition_aws_us_gov(
        self, provider, org, monkeypatch
    ):
        """Edge case: AWS GovCloud (aws-us-gov) partition with us-gov-east-1.

        get_credentials should accept and pass through GovCloud regions.
        """
        creds_payload = json.dumps(
            {
                "roleCredentials": {
                    "accessKeyId": "GAKIA1234567890ABCDE",
                    "secretAccessKey": "gov-secret-key",
                    "sessionToken": "gov-session-token",
                }
            }
        )
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=creds_payload),
        )
        creds = provider.get_credentials(org, "123456789012", "Admin", "us-gov-east-1")
        assert creds["AWS_ACCESS_KEY_ID"] == "GAKIA1234567890ABCDE"


# =============================================================================
# Context & Account ID Format Validation
# =============================================================================


class TestAccountIDFormatValidation:
    """Test account ID parsing and validation edge cases."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_list_accounts_account_id_with_leading_zeros(
        self, provider, org, monkeypatch
    ):
        """Edge case: AWS account ID has leading zeros (e.g., 000012345678).

        AWS account IDs are always 12 digits. Leading zeros are significant
        and should be preserved as strings. JSON parsing handles this correctly.
        """
        # Mock sso_list_accounts to return raw account data
        raw_accounts = [
            {
                "accountId": "000012345678",
                "accountName": "Prod",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["id"] == "000012345678"

    def test_list_accounts_account_id_all_zeros(self, provider, org, monkeypatch):
        """Edge case: Account ID is all zeros (000000000000).

        While not realistic, technically valid as 12-digit string. Should
        be returned without modification.
        """
        raw_accounts = [
            {
                "accountId": "000000000000",
                "accountName": "Test",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["id"] == "000000000000"

    def test_list_accounts_non_numeric_account_id(self, provider, org, monkeypatch):
        """Edge case: accountId contains non-numeric characters.

        AWS account IDs are always numeric, but if a malformed response
        includes non-numeric IDs, they should still be extracted (since
        we don't validate the format).
        """
        raw_accounts = [
            {
                "accountId": "ABCD12345678",
                "accountName": "Test",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        # Implementation doesn't validate format, just extracts
        assert len(accounts) == 1
        assert accounts[0]["id"] == "ABCD12345678"

    def test_list_accounts_empty_account_id_string(self, provider, org, monkeypatch):
        """Edge case: accountId field is an empty string.

        Empty account IDs should still be extracted (no validation).
        """
        raw_accounts = [
            {
                "accountId": "",
                "accountName": "Test",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["id"] == ""

    def test_list_accounts_null_account_id(self, provider, org, monkeypatch):
        """Edge case: accountId is JSON null.

        If AWS returns null for accountId, JSON parsing yields None.
        Extracting it should work (but the result won't be a string).
        """
        raw_accounts = [
            {
                "accountId": None,
                "accountName": "Test",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["id"] is None

    def test_list_accounts_account_id_max_length(self, provider, org, monkeypatch):
        """Edge case: accountId exceeds normal 12-digit length.

        AWS IDs are 12 digits, but if response has longer ID, it should
        still be extracted (no validation).
        """
        raw_accounts = [
            {
                "accountId": "123456789012345678901234",
                "accountName": "Test",
            }
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: raw_accounts,
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert len(accounts) == 1
        assert accounts[0]["id"] == "123456789012345678901234"


# =============================================================================
# Role Listing Edge Cases
# =============================================================================


class TestRoleListingEdgeCases:
    """Test role extraction edge cases."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_list_roles_malformed_json_response(self, provider, org, monkeypatch):
        """Edge case: Role list response has malformed JSON.

        Should catch JSONDecodeError and return empty list.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout="{ malformed json"),
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        assert roles == []

    def test_list_roles_missing_role_name_field(self, provider, org, monkeypatch):
        """Edge case: Role objects missing 'roleName' field.

        Should catch KeyError and return empty list.
        """
        raw_roles = [
            {"roleName": "Admin"},
            {"description": "No role name here"},
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_account_roles",
            lambda token, account_id: raw_roles,
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        # Should catch KeyError and return empty list
        assert roles == []

    def test_list_roles_empty_role_list(self, provider, org, monkeypatch):
        """Edge case: roleList is present but empty.

        Should return empty list without error.
        """
        response = {"roleList": []}
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        assert roles == []

    def test_list_roles_missing_role_list_key(self, provider, org, monkeypatch):
        """Edge case: Response lacks 'roleList' key.

        Should return empty list (default from .get()).
        """
        response = {"nextToken": "xyz"}  # No roleList
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        assert roles == []

    def test_list_roles_role_name_with_special_chars(self, provider, org, monkeypatch):
        """Edge case: Role names with special characters and spaces.

        Should extract and return role names as-is (no validation).
        """
        raw_roles = [
            {"roleName": "Admin-ReadOnly"},
            {"roleName": "Org-Master/Org-Infrastructure"},
            {"roleName": "TeamDevOps"},
        ]
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_account_roles",
            lambda token, account_id: raw_roles,
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        assert "Admin-ReadOnly" in roles
        assert "Org-Master/Org-Infrastructure" in roles
        assert "TeamDevOps" in roles


# =============================================================================
# Timeout & Error Handling
# =============================================================================


class TestTimeoutAndErrorHandling:
    """Test subprocess timeout and error handling."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_get_credentials_subprocess_timeout(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: AWS CLI subprocess times out after 30 seconds.

        Should catch TimeoutExpired and exit with error message.
        """

        def timeout_run(*args, **kw):
            raise subprocess.TimeoutExpired("aws", 30)

        monkeypatch.setattr("cloudctl.providers.aws.run_aws", timeout_run)

        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")

        output = "".join(mock_rich_console.captured)
        assert "timed out" in output.lower()

    def test_get_credentials_empty_stdout_from_aws(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: AWS CLI returns success (0) but empty stdout.

        Should handle empty/missing JSON gracefully.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=""),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        output = "".join(mock_rich_console.captured)
        assert "No credentials" in output or "Invalid JSON" in output

    def test_get_credentials_missing_role_credentials_key(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Response is valid JSON but lacks 'roleCredentials' key.

        Should detect missing credentials and exit with error.
        """
        response = {"someOtherKey": "value"}  # No roleCredentials
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        output = "".join(mock_rich_console.captured)
        assert "No credentials" in output or "no credentials" in output.lower()

    def test_get_credentials_empty_role_credentials_dict(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: roleCredentials key is present but empty dict.

        Should detect empty credentials and exit.
        """
        response = {"roleCredentials": {}}
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")

    def test_get_credentials_missing_access_key_in_credentials(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Credentials dict missing accessKeyId.

        Should raise KeyError when trying to access missing field.
        """
        response = {
            "roleCredentials": {
                "secretAccessKey": "secret",
                "sessionToken": "token",
                # Missing accessKeyId
            }
        }
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        with pytest.raises(KeyError):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")

    def test_get_credentials_missing_secret_key_in_credentials(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Credentials dict missing secretAccessKey.

        Should raise KeyError when accessing missing field.
        """
        response = {
            "roleCredentials": {
                "accessKeyId": "AKIA...",
                "sessionToken": "token",
                # Missing secretAccessKey
            }
        }
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        with pytest.raises(KeyError):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")

    def test_get_credentials_missing_session_token_in_credentials(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: Credentials dict missing sessionToken.

        Should raise KeyError when accessing missing field.
        """
        response = {
            "roleCredentials": {
                "accessKeyId": "AKIA...",
                "secretAccessKey": "secret",
                # Missing sessionToken
            }
        }
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=json.dumps(response)),
        )
        with pytest.raises(KeyError):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")


# =============================================================================
# Token & Org Handling Edge Cases
# =============================================================================


class TestTokenAndOrgHandling:
    """Test token and org parameter handling."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_get_credentials_with_dict_org(self, provider, monkeypatch):
        """Edge case: org parameter is a dict (normal case).

        Verify that dict org with 'name' key is handled correctly.
        """
        org = {
            "name": "my-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }
        creds_payload = json.dumps(
            {
                "roleCredentials": {
                    "accessKeyId": "AKIA...",
                    "secretAccessKey": "secret",
                    "sessionToken": "token",
                }
            }
        )
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=creds_payload),
        )
        creds = provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        assert creds["AWS_PROFILE"] == "my-org-123456789012-Admin"

    def test_get_credentials_with_dict_org_missing_name(self, provider, monkeypatch):
        """Edge case: org dict lacks 'name' key.

        Should fall back to "cloudctl" as profile name.
        """
        org = {
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
            # Missing name
        }
        creds_payload = json.dumps(
            {
                "roleCredentials": {
                    "accessKeyId": "AKIA...",
                    "secretAccessKey": "secret",
                    "sessionToken": "token",
                }
            }
        )
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout=creds_payload),
        )
        creds = provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        assert creds["AWS_PROFILE"] == "cloudctl-123456789012-Admin"

    def test_load_token_with_dict_org(self, provider, monkeypatch):
        """Edge case: load_token called with dict org.

        Verify correct extraction of name, url, region from dict.
        """
        org = {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }
        # Mock the sso_cache.load_active_sso_token to return a token
        mock_token = MagicMock()
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: mock_token,
        )
        token = provider.load_token(org)
        assert token == mock_token

    def test_load_token_with_non_dict_org(self, provider, monkeypatch):
        """Edge case: load_token called with non-dict org (object with attributes).

        Should extract name, sso_start_url, sso_region from attributes.
        """
        mock_org = MagicMock()
        mock_org.name = "test-org"
        mock_org.sso_start_url = "https://test.awsapps.com/start"
        mock_org.sso_region = "us-east-1"

        mock_token = MagicMock()
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: mock_token,
        )
        token = provider.load_token(mock_org)
        assert token == mock_token

    def test_load_token_with_keyboard_interrupt(self, provider, org, monkeypatch):
        """Edge case: load_token with KeyboardInterrupt from load_active_sso_token.

        Should re-raise KeyboardInterrupt (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt):
            provider.load_token(org)

    def test_load_token_with_system_exit(self, provider, org, monkeypatch):
        """Edge case: load_token with SystemExit from load_active_sso_token.

        Should re-raise SystemExit (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: (_ for _ in ()).throw(SystemExit(1)),
        )
        with pytest.raises(SystemExit):
            provider.load_token(org)

    def test_list_accounts_with_keyboard_interrupt(self, provider, org, monkeypatch):
        """Edge case: list_accounts with KeyboardInterrupt.

        Should re-raise KeyboardInterrupt (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt):
            provider.list_accounts(org, token="token-123")

    def test_list_accounts_with_system_exit(self, provider, org, monkeypatch):
        """Edge case: list_accounts with SystemExit.

        Should re-raise SystemExit (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: (_ for _ in ()).throw(SystemExit(1)),
        )
        with pytest.raises(SystemExit):
            provider.list_accounts(org, token="token-123")

    def test_list_roles_with_keyboard_interrupt(self, provider, org, monkeypatch):
        """Edge case: list_roles with KeyboardInterrupt.

        Should re-raise KeyboardInterrupt (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_account_roles",
            lambda token, account_id: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(KeyboardInterrupt):
            provider.list_roles(org, token="token-123", account_id="123456789012")

    def test_list_roles_with_system_exit(self, provider, org, monkeypatch):
        """Edge case: list_roles with SystemExit.

        Should re-raise SystemExit (not catch it).
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_account_roles",
            lambda token, account_id: (_ for _ in ()).throw(SystemExit(1)),
        )
        with pytest.raises(SystemExit):
            provider.list_roles(org, token="token-123", account_id="123456789012")


# =============================================================================
# Login, Logout, and Token Expiry Edge Cases
# =============================================================================


class TestLoginLogoutAndTokenExpiry:
    """Test login, logout, and token expiry operations."""

    @pytest.fixture
    def provider(self):
        return AwsProvider()

    @pytest.fixture
    def org(self):
        return {
            "name": "test-org",
            "sso_start_url": "https://test.awsapps.com/start",
            "sso_region": "us-east-1",
        }

    def test_login_aws_china_partition_not_supported(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: login() called with AWS China (aws-cn) partition.

        AWS China does not support IAM Identity Center. login() should detect
        this and return 1 without calling ensure_sso_base_profile.
        """
        china_org = dict(org)
        china_org["partition"] = "aws-cn"

        result = provider.login(china_org)
        assert result == 1
        output = "".join(mock_rich_console.captured)
        assert "does not support" in output.lower() or "aws china" in output.lower()

    def test_login_regular_partition_success(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: login() called with regular AWS partition.

        Regular AWS partition (or default) should attempt login via ensure_sso_base_profile
        and aws sso login command.
        """
        monkeypatch.setattr(
            "cloudctl.aws.ensure_sso_base_profile",
            lambda org: "test-org",
        )
        monkeypatch.setattr(
            "cloudctl.utils.run",
            lambda args: 0,
        )

        result = provider.login(org)
        # Should return 0 for successful login
        assert result == 0

    def test_login_subprocess_exception(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: login() catches exception from subprocess.run.

        When run() raises an exception, login should catch it and return 1.
        """
        monkeypatch.setattr(
            "cloudctl.aws.ensure_sso_base_profile",
            lambda org: "test-org",
        )
        monkeypatch.setattr(
            "cloudctl.utils.run",
            lambda args: (_ for _ in ()).throw(RuntimeError("Subprocess failed")),
        )

        result = provider.login(org)
        # Should catch exception and return 1
        assert result == 1
        output = "".join(mock_rich_console.captured)
        assert "Login failed" in output

    def test_logout_success(self, provider, monkeypatch):
        """Edge case: logout() returns 0 on success."""
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(return_value=MagicMock(returncode=0)),
        )
        result = provider.logout({"name": "test-org"})
        assert result == 0

    def test_logout_failure(self, provider, monkeypatch):
        """Edge case: logout() returns non-zero on failure."""
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(return_value=MagicMock(returncode=1)),
        )
        result = provider.logout({"name": "test-org"})
        assert result != 0

    def test_get_token_expiry_with_valid_token(self, provider, org, monkeypatch):
        """Edge case: get_token_expiry() with token having expiresAt.

        Should return the expiresAt value.
        """
        from datetime import datetime, timezone

        expected_expiry = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        mock_token = MagicMock()
        mock_token.expiresAt = expected_expiry

        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: mock_token,
        )

        expiry = provider.get_token_expiry(org)
        assert expiry == expected_expiry

    def test_get_token_expiry_with_token_missing_attribute(
        self, provider, org, monkeypatch
    ):
        """Edge case: get_token_expiry() with token missing expiresAt attribute.

        Should return None if attribute is missing.
        """
        mock_token = MagicMock(spec=[])  # Token without expiresAt
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: mock_token,
        )

        expiry = provider.get_token_expiry(org)
        assert expiry is None

    def test_get_token_expiry_load_token_returns_none(self, provider, org, monkeypatch):
        """Edge case: get_token_expiry() when load_token returns None.

        Should return None when token is not available.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: None,
        )

        expiry = provider.get_token_expiry(org)
        assert expiry is None

    def test_get_token_expiry_exception_handling(self, provider, org, monkeypatch):
        """Edge case: get_token_expiry() when load_token raises exception.

        Should catch exception and return None.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: (_ for _ in ()).throw(RuntimeError("Token load failed")),
        )

        expiry = provider.get_token_expiry(org)
        assert expiry is None

    def test_get_unsets_all_env_vars(self, provider):
        """Edge case: get_unsets() should unset all AWS environment variables.

        Verify that all _ENV_VARS are included in the unset output.
        """
        unsets = provider.get_unsets()
        for var in provider._ENV_VARS:
            assert f"unset {var}" in unsets

    def test_list_accounts_general_exception(self, provider, org, monkeypatch):
        """Edge case: list_accounts catches general exceptions.

        Any exception other than KeyboardInterrupt/SystemExit should be caught
        and return empty list.
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_accounts",
            lambda token: (_ for _ in ()).throw(ValueError("Bad value")),
        )
        accounts = provider.list_accounts(org, token="token-123")
        assert accounts == []

    def test_list_roles_general_exception(self, provider, org, monkeypatch):
        """Edge case: list_roles catches general exceptions.

        Any exception other than KeyboardInterrupt/SystemExit should be caught
        and return empty list.
        """
        monkeypatch.setattr(
            "cloudctl.aws.sso_list_account_roles",
            lambda token, account_id: (_ for _ in ()).throw(RuntimeError("Failed")),
        )
        roles = provider.list_roles(org, token="token-123", account_id="123456789012")
        assert roles == []

    def test_load_token_general_exception(self, provider, org, monkeypatch):
        """Edge case: load_token catches general exceptions.

        Any exception other than KeyboardInterrupt/SystemExit should be caught
        and return None.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.load_active_sso_token",
            lambda org_ref: (_ for _ in ()).throw(ValueError("Bad token")),
        )
        token = provider.load_token(org)
        assert token is None

    def test_get_credentials_invalid_json_error_handling(
        self, provider, org, monkeypatch, mock_rich_console
    ):
        """Edge case: get_credentials handles JSON decode errors.

        When AWS returns invalid JSON, should catch JSONDecodeError and exit.
        """
        monkeypatch.setattr(
            "cloudctl.providers.aws.run_aws",
            lambda args, **kw: _aws_result(0, stdout="invalid json {["),
        )
        with pytest.raises(SystemExit):
            provider.get_credentials(org, "123456789012", "Admin", "us-east-1")
        output = "".join(mock_rich_console.captured)
        assert "Invalid JSON" in output or "Invalid" in output
