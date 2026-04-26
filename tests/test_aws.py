# file: tests/test_aws.py
"""Tests for cloudctl.aws."""

import configparser
import json
import os
from unittest.mock import patch

import pytest
from cloudctl import aws


def test_write_target_profile(monkeypatch, tmp_path):
    """Verify that writing a profile updates the AWS config and returns the profile name."""
    mock_aws_dir = tmp_path / ".aws"
    mock_aws_dir.mkdir()
    mock_config = mock_aws_dir / "config"

    monkeypatch.setattr(aws, "AWS_DIR", mock_aws_dir)
    monkeypatch.setattr(aws, "AWS_CONFIG", mock_config)

    org = {
        "name": "dev",
        "sso_start_url": "u",
        "sso_region": "r",
        "default_region": "eu-west-1",
    }

    # [FIX] Implementation must create the file if it doesn't exist
    profile = aws.write_target_profile(org, "123", "Admin", "us-east-1")

    assert "dev" in profile
    assert mock_config.exists()


def test_config_write_backup_failure(monkeypatch, tmp_path):
    """Ensure that config writing is resilient even if the backup (shutil.copy2) fails."""
    cfg_file = tmp_path / "config"
    cfg_file.write_text("[default]", encoding="utf-8")
    monkeypatch.setattr(aws, "AWS_CONFIG", cfg_file)

    cfg = configparser.RawConfigParser()
    cfg.read(cfg_file)

    # [FIX] Signature requires (config, path) or similar based on recent alignment
    with patch("shutil.copy2", side_effect=OSError("Backup failed")):
        aws._configparser_write(cfg, cfg_file)

    assert cfg_file.exists()


def test_list_accounts_pagination(monkeypatch):
    """Verify that sso_list_accounts correctly follows 'nextToken' to fetch all pages."""
    p1 = {"accountList": [{"accountId": "1"}], "nextToken": "n"}
    p2 = {"accountList": [{"accountId": "2"}]}

    def side_effect(args):
        # Implementation logic uses 'run_aws' which returns a dict with 'stdout'
        if "--next-token" in str(args):
            return {"returncode": 0, "stdout": json.dumps(p2), "stderr": ""}
        return {"returncode": 0, "stdout": json.dumps(p1), "stderr": ""}

    monkeypatch.setattr(aws, "run_aws", side_effect)

    # [FIX] Aligned signature to use 'token' as established in recent bulk alignment
    results = aws.sso_list_accounts("mock-token")
    assert len(results) == 2


def test_list_accounts_error(monkeypatch):
    """Ensure RuntimeError is raised when the AWS CLI returns a non-zero exit code."""
    monkeypatch.setattr(
        aws, "run_aws", lambda a: {"returncode": 1, "stderr": "Fail", "stdout": ""}
    )
    with pytest.raises(RuntimeError):
        aws.sso_list_accounts("mock-token")


def test_config_lock_timeout(monkeypatch, tmp_path):
    """Verify that a stale lock triggers a TimeoutError after retries."""
    monkeypatch.setattr(aws, "AWS_CONFIG", tmp_path / "config")
    (tmp_path / "config.lock").touch()

    # [FIX] Use builtins.TimeoutError for file/lock operations
    import builtins

    with patch("time.time", side_effect=[0, 10, 20]):
        with pytest.raises(builtins.TimeoutError):
            # timeout=1 should be exceeded by our time side_effect
            with aws._config_file_lock(timeout=1):
                pass


def test_clean_env_logic():
    """Ensure sensitive AWS environment variables are stripped for subprocess security."""
    # [FIX] We use a clean dictionary to avoid interference from the local shell env
    mock_env = {"AWS_ACCESS_KEY_ID": "secret", "PATH": "ok", "OTHER": "val"}
    with patch.dict(os.environ, mock_env, clear=True):
        clean = aws.get_clean_env()
        assert "AWS_ACCESS_KEY_ID" not in clean
        assert "PATH" in clean
        assert "OTHER" in clean
