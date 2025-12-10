# file: tests/test_core.py
"""Unit tests for awsctl.core."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from awsctl import config, core, sso_cache, utils


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(core, "AWS_DIR", tmp_path / ".aws")
    monkeypatch.setattr(core, "SSO_CACHE_DIR", tmp_path / ".aws" / "sso" / "cache")
    return tmp_path


def test_cmd_cache_clear(mock_home, mock_rich_console):
    (core.AWS_DIR / "cli" / "cache").mkdir(parents=True)
    core.cmd_cache_clear()
    assert "Cache cleared" in "".join(mock_rich_console.captured)


def test_core_cache_clear_errors(monkeypatch, mock_rich_console):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_file = MagicMock()
    mock_file.exists.return_value = True
    mock_file.is_file.return_value = True
    mock_file.unlink.side_effect = Exception("DelFail")
    mock_path.iterdir.return_value = [mock_file]

    mock_aws = MagicMock()
    mock_aws.__truediv__.return_value.__truediv__.return_value = mock_path
    monkeypatch.setattr(core, "AWS_DIR", mock_aws)

    utils.set_debug(True)
    monkeypatch.setattr(core, "console", mock_rich_console)

    core.cmd_cache_clear()
    assert "Failed to remove" in "".join(mock_rich_console.captured)


def test_cmd_logout_str(mock_home):
    with patch("subprocess.run") as mock_sub:
        output = core.cmd_logout_str()
        # [FIX] Use the mock variable to satisfy linter F841
        mock_sub.assert_called_with(["aws", "sso", "logout"], check=False)
    assert "unset AWS_ACCESS_KEY_ID" in output


def test_cmd_env_no_context(mock_home):
    with patch("awsctl.context_manager.load_context", return_value={}):
        assert "No active context" in core.cmd_env()


def test_cmd_login_failure(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "p")
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: None)
    monkeypatch.setattr("awsctl.utils.run", MagicMock(side_effect=Exception("Fail")))
    assert core.cmd_login("o") == 1
    assert "Login failed" in "".join(mock_rich_console.captured)


def test_cmd_exec_missing_creds(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.context_manager.load_context", lambda: {"current_org": "btavm"}
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.core.load_active_sso_token",
        lambda *a, **k: sso_cache.SsoToken(
            "tok", "u", "r", datetime.now(timezone.utc), {}
        ),
    )
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: {})
    assert core.cmd_exec("123", "Admin", "us-east-1", ["ls"]) == 1
    assert "Failed to get credentials" in "".join(mock_rich_console.captured)
