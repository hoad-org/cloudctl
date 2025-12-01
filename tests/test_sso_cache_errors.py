# file: tests/test_sso_cache_errors.py
"""
Tests for sso_cache.py error handling.
"""
import json

import pytest

from awsctl.sso_cache import OrgRef, load_active_sso_token


def test_corrupt_cache_file(tmp_path, capsys):
    """Ensure we skip bad JSON files without crashing."""
    cache_dir = tmp_path / "sso_cache"
    cache_dir.mkdir()

    # Create a corrupted file
    (cache_dir / "bad.json").write_text("{ not valid json }")

    # Create a valid but mismatched file to ensure loop continues
    (cache_dir / "other.json").write_text(
        json.dumps(
            {
                "startUrl": "https://other.com",
                "region": "us-east-1",
                "accessToken": "tok",
                "expiresAt": "2099-01-01T00:00:00Z",
            }
        )
    )

    org = OrgRef("myorg", "https://target.com", "us-east-1")

    # Should exit because no valid matching token found, but NOT crash on json decode
    with pytest.raises(SystemExit):
        load_active_sso_token(org, cache_dir=cache_dir)

    out, err = capsys.readouterr()
    assert "does not exist" in (out + err)
