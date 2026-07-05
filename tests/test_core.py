# file: tests/test_core.py
"""Unit tests for cloudctl.core."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401 — kept for test decorators/fixtures
from cloudctl import config, core, sso_cache, utils  # noqa: F401

# NOTE: the local `mock_home` fixture that used to live here shadowed the
# hermetic autouse fixture in conftest.py and only redirected *some* of the
# frozen path constants — it left CONFIG_DIR / CONTEXT_FILE / aws.SSO_CACHE_DIR
# pointing at the real ~/.config and ~/.aws, so these tests deleted the user's
# real context file and SSO token cache. Removed so all tests use the fully
# isolated conftest fixture.


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


def test_cmd_logout_str(mock_home, monkeypatch):
    # [FIX] Mock binary resolution to return a predictable string "aws"
    monkeypatch.setattr("cloudctl.aws._resolve_aws_cli", lambda: "aws")

    with patch("subprocess.run") as mock_sub:
        output = core.cmd_logout_str()
        mock_sub.assert_called_with(["aws", "sso", "logout"], check=False)
    assert "unset AWS_ACCESS_KEY_ID" in output


def test_cmd_env_no_context(mock_home):
    with patch("cloudctl.context_manager.load_context", return_value={}):
        assert "No active context" in core.cmd_env()


def test_cmd_login_failure(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("cloudctl.core.load_active_sso_token", lambda *a, **k: None)

    # login is now a boto3 device-authorization flow; simulate the sso-oidc
    # client blowing up so the provider returns 1 and reports "Login failed".
    monkeypatch.setattr(
        "boto3.client", MagicMock(side_effect=Exception("Fail"))
    )
    assert core.cmd_login("o") == 1
    assert "Login failed" in "".join(mock_rich_console.captured)


def test_cmd_exec_missing_creds(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "cloudctl.context_manager.load_context", lambda: {"current_org": "btavm"}
    )
    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr(
        "cloudctl.core.load_active_sso_token",
        lambda *a, **k: sso_cache.SsoToken(
            "tok", "u", "r", datetime.now(timezone.utc), {}
        ),
    )

    # [FIX] Mock binary resolution for exec tests (called via _aws_json)
    monkeypatch.setattr("cloudctl.aws._resolve_aws_cli", lambda: "aws")

    monkeypatch.setattr("cloudctl.use_exports._aws_json", lambda cmd: {})
    assert core.cmd_exec("123", "Admin", "us-east-1", ["ls"]) == 1
    assert "Failed to get credentials" in "".join(mock_rich_console.captured)
