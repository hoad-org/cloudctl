"""Test infrastructure and fixtures for comprehensive test suite.

PHASE 5A: Enhanced conftest with AWS mocking, common fixtures, and validation utilities.
"""

import json
from io import StringIO
from unittest.mock import MagicMock

import pytest
import yaml
from rich.console import Console

# ============================================================================
# HOME DIRECTORY & ENVIRONMENT FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def mock_home(tmp_path, monkeypatch):
    """Sets up a hermetic home directory for every test.

    Creates isolated ~/.aws, ~/.cloudctl directories and prevents
    real browser launches during testing.
    """
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    # Critical: Mock both the env var and Path.home() if used in source
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # For Windows parity

    # Pre-create required directory structures
    (home / ".awsctl").mkdir(exist_ok=True)
    (home / ".aws" / "sso" / "cache").mkdir(parents=True, exist_ok=True)
    (home / ".cloudctl").mkdir(exist_ok=True)
    (home / ".config" / "cloudctl").mkdir(parents=True, exist_ok=True)

    # Global browser mock to prevent tests from launching real windows
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", MagicMock(return_value=True))

    return home


@pytest.fixture
def mock_rich_console(monkeypatch):
    """Unified console capture fixture with Rich console replacement.

    Replaces the real Rich console with one that records to a buffer,
    enabling tests to validate output without capturing terminal formatting.
    """

    class CapturedConsole:
        def __init__(self):
            self.buffer = StringIO()
            # We create a REAL Rich Console but point it at our buffer
            self.console = Console(
                file=self.buffer, force_terminal=False, width=100, color_system=None
            )

        @property
        def captured(self):
            """Returns a list of strings, split by actual output to match test expectations."""
            val = self.buffer.getvalue()
            return [val] if val else []

        def print(self, *args, **kwargs):
            """Proxy to the real Rich console print method."""
            self.console.print(*args, **kwargs)

        def clear(self):
            """Wipes the buffer for the next assertion."""
            self.buffer.truncate(0)
            self.buffer.seek(0)

    cap = CapturedConsole()

    # We must patch the utils module where the consoles are defined
    import cloudctl.utils

    # Replace the Rich Console instances with our capture object
    # Note: We patch the attributes that the code actually calls
    monkeypatch.setattr(cloudctl.utils, "console", cap.console)
    monkeypatch.setattr(cloudctl.utils, "stdout_console", cap.console)

    # We return the 'cap' wrapper so tests can call .clear() or check .captured
    return cap


# ============================================================================
# AWS SSO & BOTO3 FIXTURES
# ============================================================================


@pytest.fixture
def mock_aws_sso_client():
    """Mock boto3 SSO client for testing role listing and validation.

    Returns configured mock with standard AWS SSO responses.
    """
    from unittest.mock import MagicMock

    client = MagicMock()

    # Mock list_accounts response
    client.list_accounts.return_value = {
        "accountList": [
            {
                "accountId": "123456789012",
                "accountName": "Production",
                "emailAddress": "prod@example.com",
            },
            {
                "accountId": "234567890123",
                "accountName": "Staging",
                "emailAddress": "staging@example.com",
            },
        ]
    }

    # Mock list_roles_for_account response
    client.list_roles_for_account.return_value = {
        "roleList": [
            {"roleName": "Admin", "roleArn": "arn:aws:iam::123456789012:role/Admin"},
            {
                "roleName": "Developer",
                "roleArn": "arn:aws:iam::123456789012:role/Developer",
            },
            {
                "roleName": "ReadOnly",
                "roleArn": "arn:aws:iam::123456789012:role/ReadOnly",
            },
        ]
    }

    return client


@pytest.fixture
def mock_aws_sts_client():
    """Mock boto3 STS client for testing credential operations.

    Returns configured mock with standard STS responses.
    """
    from unittest.mock import MagicMock

    client = MagicMock()

    client.get_caller_identity.return_value = {
        "UserId": "AIDACKCEVSQ6C2EXAMPLE",
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test-user",
    }

    return client


@pytest.fixture
def mock_boto3_session(mock_aws_sso_client, mock_aws_sts_client, monkeypatch):
    """Mock boto3 Session factory for testing AWS integration.

    Integrates SSO and STS mocks into a unified session mock.
    """
    from unittest.mock import MagicMock

    session_mock = MagicMock()
    session_mock.client.side_effect = lambda service, *args, **kwargs: {
        "sso": mock_aws_sso_client,
        "sts": mock_aws_sts_client,
    }.get(service, MagicMock())

    monkeypatch.setattr("boto3.Session", MagicMock(return_value=session_mock))
    return session_mock


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================


@pytest.fixture
def sample_orgs_yaml(mock_home):
    """Create a valid orgs.yaml configuration in the mock home directory.

    Returns path to the configuration file and its contents as dict.
    """
    config_dir = mock_home / ".config" / "cloudctl"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "orgs.yaml"

    config = {
        "version": "4.0.0",
        "organizations": {
            "bt-avm": {
                "provider": "aws",
                "partition": "aws",
                "sso_start_url": "https://beyondtrust.awsapps.com/start",
                "sso_region": "us-east-1",
                "sensitive_roles": ["admin", "devops", "security"],
                "approval_gate_roles": {"admin": 2, "devops": 1},
                "mfa_required_roles": ["admin", "security"],
            },
            "fdr-gvc": {
                "provider": "aws",
                "partition": "aws-us-gov",
                "sso_start_url": "https://beyondtrust-govcloud.awsapps.com/start",
                "sso_region": "us-gov-east-1",
                "sensitive_roles": ["admin"],
                "approval_gate_roles": {"admin": 2},
            },
        },
    }

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    return config_file, config


@pytest.fixture
def context_json_valid(mock_home):
    """Create a valid context.json file in mock cloudctl directory.

    Returns path to the context file and its contents as dict.
    """
    context_dir = mock_home / ".cloudctl"
    context_dir.mkdir(parents=True, exist_ok=True)
    context_file = context_dir / "context.json"

    context = {
        "org": "bt-avm",
        "account": "123456789012",
        "role": "Admin",
        "region": "us-east-1",
        "timestamp": 1609459200,
    }

    with open(context_file, "w") as f:
        json.dump(context, f)

    return context_file, context


@pytest.fixture
def sample_sso_cache(mock_home):
    """Create a valid AWS SSO token cache entry.

    Simulates the token cache that AWS CLI uses.
    """
    cache_dir = mock_home / ".aws" / "sso" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create a cache file (AWS SSO tokens are stored with hash filenames)
    cache_entry = {
        "accessToken": "AKIA123456789EXAMPLE",
        "expiresAt": "2099-12-31T23:59:59Z",
        "refreshToken": "REFRESH123456789EXAMPLE",
        "clientId": "0oa123456789example",
        "clientSecret": "secret123456789example",
        "registrationExpiresAt": "2099-12-31T23:59:59Z",
        "region": "us-east-1",
        "startUrl": "https://beyondtrust.awsapps.com/start",
    }

    # Hash the cache filename (AWS SSO uses SHA1 of start URL)
    import hashlib

    cache_filename = hashlib.sha1(cache_entry["startUrl"].encode()).hexdigest()
    cache_file = cache_dir / f"{cache_filename}.json"

    with open(cache_file, "w") as f:
        json.dump(cache_entry, f)

    return cache_file, cache_entry


# ============================================================================
# VALIDATION & ASSERTION UTILITIES
# ============================================================================


@pytest.fixture
def assert_test_coverage():
    """Helper fixture to validate test coverage metrics.

    Used in PHASE 5B to ensure all modules meet minimum coverage thresholds.
    """

    def _assert_coverage(module_path, min_coverage):
        """Check that module_path has at least min_coverage % coverage."""
        # This will be populated by actual coverage reports in PHASE 5B
        pass

    return _assert_coverage


@pytest.fixture
def validate_error_types():
    """Helper to validate that error types are properly testable.

    Checks that errors have proper messages, inheritance, and context.
    """

    def _validate(error_class, message_sample):
        """Validate error class has proper structure."""
        assert issubclass(
            error_class, Exception
        ), f"{error_class} must inherit Exception"

        # Test instantiation with message
        error = error_class(message_sample)
        assert str(error) == message_sample or message_sample in str(error)

    return _validate


@pytest.fixture
def validate_encryption_roundtrip():
    """Helper to test encryption/decryption roundtrips.

    Used for testing config encryption module.
    """

    def _validate(encrypt_fn, decrypt_fn, plaintext):
        """Test that encrypt->decrypt returns original plaintext."""
        ciphertext = encrypt_fn(plaintext)
        assert ciphertext != plaintext, "Encryption should not return plaintext"
        decrypted = decrypt_fn(ciphertext)
        assert decrypted == plaintext, "Decryption should return original plaintext"

    return _validate


# ============================================================================
# MARKER-BASED TEST CATEGORIZATION
# ============================================================================


# Register custom markers for test categorization (used in PHASE 5B)
def pytest_configure(config):
    """Register custom pytest markers for test categorization."""
    config.addinivalue_line(
        "markers", "unit: Mark test as a unit test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Mark test as an integration test (requires AWS/services)",
    )
    config.addinivalue_line(
        "markers", "smoke: Mark test as a smoke test (basic functionality)"
    )
    config.addinivalue_line("markers", "slow: Mark test as slow (>1 second)")
    config.addinivalue_line("markers", "aws: Mark test as requiring AWS integration")
    config.addinivalue_line(
        "markers",
        "error_handling: Mark test as testing error handling and edge cases",
    )
    config.addinivalue_line(
        "markers", "encryption: Mark test as testing encryption/decryption"
    )
    config.addinivalue_line(
        "markers", "role_validation: Mark test as testing role validation"
    )
