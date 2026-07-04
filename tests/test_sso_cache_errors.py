# file: tests/test_sso_cache_errors.py
"""
Tests for sso_cache.py error handling.
"""

import json

import pytest
from cloudctl.sso_cache import OrgRef, load_active_sso_token


def test_corrupt_cache_file(tmp_path):
    """Ensure we skip bad JSON files without crashing but raise error if no match found."""
    cache_dir = tmp_path / "sso_cache"
    cache_dir.mkdir()

    # 1. Create a corrupted file (invalid syntax)
    # The implementation should catch JSONDecodeError and continue the loop
    (cache_dir / "bad.json").write_text("{ not valid json }")

    # 2. Create a valid JSON file that does NOT match the target Org
    # startUrl and region mismatch "target.com" and "us-east-1"
    (cache_dir / "mismatch.json").write_text(
        json.dumps(
            {
                "startUrl": "https://other.com",
                "region": "us-west-2",
                "accessToken": "tok",
                "expiresAt": "2099-01-01T00:00:00Z",
            }
        )
    )

    org = OrgRef("btavm", "https://target.com", "us-east-1")

    # 3. Verify Contract: [AWSCTL-0021]
    # We expect a RuntimeError because we skipped the corrupt file AND
    # failed to find a valid match in the remaining files.
    with pytest.raises(RuntimeError) as e:
        # Pass raise_error=True if the implementation requires an explicit trigger,
        # or rely on the default behavior if the logic is updated to be strict.
        load_active_sso_token(org, cache_dir=cache_dir)

    assert "No valid token found" in str(e.value)


def test_cache_permission_error(tmp_path):
    """Verify RuntimeError is raised when the cache directory is inaccessible."""
    cache_dir = tmp_path / "protected_cache"
    cache_dir.mkdir(mode=0o000)  # Make directory unreadable

    org = OrgRef("test", "https://example.com", "us-east-1")

    try:
        with pytest.raises(RuntimeError) as e:
            load_active_sso_token(org, cache_dir=cache_dir)
        assert "Permission denied" in str(e.value)
    finally:
        cache_dir.chmod(mode=0o755)  # Cleanup for teardown
