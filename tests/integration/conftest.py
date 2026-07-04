"""Integration test configuration and fixtures.

PHASE 5A: AWS integration test setup.
Requires real AWS credentials and target accounts configured in orgs.yaml.
"""

import os
from pathlib import Path
from typing import Optional

import boto3
import pytest


@pytest.fixture(scope="session")
def aws_account_id() -> Optional[str]:
    """Get AWS account ID from environment or STS call.

    Returns None if not running in AWS environment (test will be skipped).
    """
    # Try to get from environment first
    account_id = os.getenv("AWS_ACCOUNT_ID")
    if account_id:
        return account_id

    # Try STS call
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        return identity["Account"]
    except Exception:
        pytest.skip("No AWS credentials available for integration test")
        return None


@pytest.fixture(scope="session")
def aws_region() -> str:
    """Get AWS region for integration tests.

    Defaults to us-east-1 if not set.
    """
    return os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture
def real_cloudctl_orgs_config(tmp_path) -> Path:
    """Create a minimal orgs.yaml pointing to real AWS account.

    This is used only if the integration test is running against
    real AWS credentials.
    """
    import yaml

    orgs_file = tmp_path / "orgs.yaml"
    config = {
        "version": "4.0.0",
        "organizations": {
            "test-org": {
                "provider": "aws",
                "partition": "aws",
                "sso_start_url": "https://example.awsapps.com/start",
                "sso_region": "us-east-1",
            }
        },
    }

    with open(orgs_file, "w") as f:
        yaml.dump(config, f)

    return orgs_file


@pytest.fixture(scope="session")
def skip_if_no_aws_creds():
    """Skip test if no AWS credentials available."""

    def _skip():
        try:
            boto3.client("sts").get_caller_identity()
        except Exception as e:
            pytest.skip(f"AWS credentials not available: {e}")

    return _skip


# ============================================================================
# AWS SERVICE FIXTURES
# ============================================================================


@pytest.fixture
def aws_sso_client():
    """Boto3 SSO client for integration testing.

    Uses real AWS SSO API against test account.
    """
    return boto3.client("sso", region_name="us-east-1")


@pytest.fixture
def aws_sts_client():
    """Boto3 STS client for integration testing.

    Uses real AWS STS API to verify credentials.
    """
    return boto3.client("sts")


@pytest.fixture
def aws_iam_client():
    """Boto3 IAM client for integration testing.

    Used for role validation and listing.
    """
    return boto3.client("iam")


# ============================================================================
# MARKERS & SKIP CONDITIONS
# ============================================================================


def pytest_configure(config):
    """Add integration-specific markers."""
    config.addinivalue_line(
        "markers",
        "integration_aws: Mark test as requiring real AWS integration",
    )
    config.addinivalue_line(
        "markers",
        "requires_sso: Mark test as requiring AWS SSO credentials",
    )


def pytest_collection_modifyitems(config, items):
    """Conditionally skip integration tests based on environment."""
    skip_aws = pytest.mark.skip(reason="no AWS credentials configured")

    for item in items:
        # If test is marked for AWS integration and no creds available, skip
        if "integration_aws" in item.keywords or "requires_sso" in item.keywords:
            if not os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_PROFILE"):
                item.add_marker(skip_aws)
