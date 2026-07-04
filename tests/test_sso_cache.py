# file: tests/test_sso_cache.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from cloudctl.sso_cache import OrgRef, _normalize_start_url, load_active_sso_token


def test_normalize():
    # [FIX] Ensure normalization handles uppercase and existing prefixes correctly
    assert _normalize_start_url("HTTPS://u") == "https://u"
    assert _normalize_start_url("u/") == "https://u"
    assert _normalize_start_url("") == ""


def test_sso_token_validation_branches(tmp_path):
    """Ensure we handle corrupt or oversized JSON files by skipping them."""
    # 1. Setup cache directory with problematic files
    (tmp_path / "big.json").write_bytes(b"0" * (1024 * 1024 + 100))
    (tmp_path / "bad.json").write_text("{ not valid json }")

    org = OrgRef("test", "https://target", "eu-west-1")

    # 2. Assert that we return None instead of crashing when files are invalid
    # The implementation should scan the dir and ignore the bad entries
    assert load_active_sso_token(org, cache_dir=tmp_path, raise_error=False) is None


def test_load_token_permission_error(monkeypatch):
    """Verify that OS-level permission errors are wrapped in RuntimeError."""
    # 1. Setup a mock Path object that raises PermissionError on glob/exists
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    # Implementation calls .glob("*.json") or list(); we trigger the failure there
    mock_path.glob.side_effect = PermissionError("Access Denied")

    org = OrgRef("test", "https://target", "eu-west-1")

    # 2. Assert the specific exception wrapper expected by the project
    with pytest.raises(RuntimeError) as e:
        load_active_sso_token(org, cache_dir=mock_path)

    assert "Permission denied" in str(e.value)


def test_load_active_sso_token_corrupt_flag(tmp_path):
    """Verify the explicit raise_error flag with a deterministic empty cache dir.

    Previously used the production SSO cache dir which may or may not exist on
    CI runners. Using tmp_path ensures the cache dir *exists* but has no matching
    tokens, exercising the strict=True → 'SSO cache corrupted' code path.
    """
    org = OrgRef("test", "https://target", "eu-west-1")

    with pytest.raises(RuntimeError) as e:
        load_active_sso_token(org, cache_dir=tmp_path, raise_error=True)

    assert "SSO cache corrupted" in str(e.value)
