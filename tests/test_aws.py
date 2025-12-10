# file: tests/test_aws.py
"""Tests for awsctl.aws."""

import configparser
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from awsctl import aws


def test_write_target_profile(monkeypatch, tmp_path):
    mock_aws_dir = tmp_path / ".aws"
    mock_config = mock_aws_dir / "config"
    monkeypatch.setattr(aws, "AWS_DIR", mock_aws_dir)
    monkeypatch.setattr(aws, "AWS_CONFIG", mock_config)
    org = {
        "name": "dev",
        "sso_start_url": "u",
        "sso_region": "r",
        "default_region": "eu-west-1",
    }
    profile = aws.write_target_profile(org, "123", "Admin", "us-east-1")
    assert "sso-dev" in profile
    assert mock_config.exists()


def test_config_write_backup_failure(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config"
    cfg_file.write_text("[default]")
    monkeypatch.setattr(aws, "AWS_CONFIG", cfg_file)
    cfg = configparser.RawConfigParser()
    cfg.read(cfg_file)
    with patch("shutil.copy2", side_effect=OSError("Backup failed")):
        aws._configparser_write(cfg)
    assert cfg_file.exists()


def test_list_accounts_pagination(monkeypatch):
    p1 = {"accountList": [{"accountId": "1"}], "nextToken": "n"}
    p2 = {"accountList": [{"accountId": "2"}]}

    def side_effect(args, **kwargs):
        return MagicMock(returncode=0, stdout=json.dumps(p2 if "n" in args else p1))

    monkeypatch.setattr(aws, "run_aws", side_effect)
    results = aws.sso_list_accounts("u", "r")
    assert len(results) == 2


def test_list_accounts_error(monkeypatch):
    monkeypatch.setattr(
        aws, "run_aws", lambda a: MagicMock(returncode=1, stderr="Fail")
    )
    with pytest.raises(RuntimeError):
        aws.sso_list_accounts("u", "r")


def test_config_lock_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(aws, "AWS_CONFIG", tmp_path / "config")
    (tmp_path / "config.lock").touch()
    with patch("time.time", side_effect=[0, 10, 20]):
        with pytest.raises(TimeoutError):
            with aws._config_file_lock(timeout=1):
                pass


def test_clean_env_logic():
    with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "secret", "PATH": "ok"}):
        # [FIX] Updated function name from _clean_env to get_clean_env
        clean = aws.get_clean_env()
        assert "AWS_ACCESS_KEY_ID" not in clean
        assert "PATH" in clean
