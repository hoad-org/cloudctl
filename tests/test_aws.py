# file: tests/test_aws.py
"""
Tests for awsctl.aws (AWS CLI wrappers and Profile generation).
"""
import configparser
import json
from unittest.mock import MagicMock

from awsctl import aws


def test_write_target_profile(monkeypatch, tmp_path):
    """Test that profile sections are written to ~/.aws/config."""
    # Mock AWS paths
    mock_aws_dir = tmp_path / ".aws"
    mock_config = mock_aws_dir / "config"
    monkeypatch.setattr(aws, "AWS_DIR", mock_aws_dir)
    monkeypatch.setattr(aws, "AWS_CONFIG", mock_config)

    org = {
        "name": "dev",
        "sso_start_url": "https://start",
        "sso_region": "eu-west-1",
        "default_region": "eu-west-2",
    }

    profile = aws.write_target_profile(org, "123", "Admin", "us-east-1")

    assert profile == "sso-dev-123-Admin-us-east-1"
    assert mock_config.exists()

    cfg = configparser.RawConfigParser()
    cfg.read(mock_config)

    # Check base profile
    assert "profile sso-dev" in cfg
    assert cfg["profile sso-dev"]["sso_session"] == "dev"

    # Check sso-session
    assert "sso-session dev" in cfg
    assert cfg["sso-session dev"]["sso_start_url"] == "https://start"

    # Check target profile
    target_sect = f"profile {profile}"
    assert target_sect in cfg
    assert cfg[target_sect]["sso_account_id"] == "123"
    assert cfg[target_sect]["sso_role_name"] == "Admin"


def test_sso_list_accounts(monkeypatch):
    """Test legacy shim parsing."""
    mock_proc = MagicMock(
        returncode=0,
        stdout='{"accountList": [{"accountId": "1", "accountName": "A"}]}',
        stderr="",
    )
    monkeypatch.setattr(aws, "run_aws", lambda args: mock_proc)

    accts = aws.sso_list_accounts("u", "r", "p")
    assert len(accts) == 1
    assert accts[0]["accountId"] == "1"


def test_sso_list_account_roles(monkeypatch):
    """Test legacy role listing."""
    mock_proc = MagicMock(
        returncode=0,
        stdout='{"roleList": [{"roleName": "Admin"}, {"roleName": "ViewOnly"}]}',
        stderr="",
    )
    monkeypatch.setattr(aws, "run_aws", lambda args: mock_proc)
    roles = aws.sso_list_account_roles("u", "123", "r", "p")
    assert roles == ["Admin", "ViewOnly"]


def test_get_valid_sso_access_token(monkeypatch, tmp_path):
    """Test legacy token retrieval logic."""
    monkeypatch.setattr(aws, "SSO_CACHE_DIR", tmp_path)

    # 1. No cache dir (non-existent)
    # We use a sub-path that doesn't exist yet to test this branch
    missing_path = tmp_path / "missing_cache"
    monkeypatch.setattr(aws, "SSO_CACHE_DIR", missing_path)
    assert aws.get_valid_sso_access_token("u", "r") is None

    # 2. Create cache dir (tmp_path exists by default) and valid token
    # Reset to valid path
    monkeypatch.setattr(aws, "SSO_CACHE_DIR", tmp_path)

    token_file = tmp_path / "valid.json"
    # Future expiry
    exp = "2099-01-01T00:00:00Z"
    token_data = {
        "startUrl": "https://u",
        "region": "r",
        "expiresAt": exp,
        "accessToken": "secret-token",
    }
    token_file.write_text(json.dumps(token_data))

    # 3. Match
    tok = aws.get_valid_sso_access_token("https://u", "r")
    assert tok == "secret-token"

    # 4. Mismatch URL
    assert aws.get_valid_sso_access_token("bad", "r") is None

    # 5. Expired
    token_data["expiresAt"] = "2000-01-01T00:00:00Z"
    token_file.write_text(json.dumps(token_data))
    assert aws.get_valid_sso_access_token("https://u", "r") is None
