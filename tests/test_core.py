# file: tests/test_core.py
# SPDX-License-Identifier: MIT
"""
Unit tests for awsctl.core orchestration logic.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from awsctl import config, core, sso_cache


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Isolate HOME."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(core, "AWS_DIR", tmp_path / ".aws")
    monkeypatch.setattr(core, "SSO_CACHE_DIR", tmp_path / ".aws" / "sso" / "cache")
    return tmp_path


def test_cmd_cache_clear(mock_home, mock_rich_console):
    cli_cache_dir = core.AWS_DIR / "cli" / "cache"
    cli_cache_dir.mkdir(parents=True)
    (cli_cache_dir / "data.json").touch()
    assert (cli_cache_dir / "data.json").exists()

    core.cmd_cache_clear()

    assert cli_cache_dir.exists()
    assert not (cli_cache_dir / "data.json").exists()
    assert "Cache cleared" in "".join(mock_rich_console.captured)


def test_cmd_logout_str(mock_home):
    with patch("awsctl.aws.run_aws") as mock_aws:
        output = core.cmd_logout_str()
    assert "unset AWS_ACCESS_KEY_ID" in output
    mock_aws.assert_called_with(["aws", "sso", "logout"])


def test_cmd_env_no_context(mock_home):
    with patch("awsctl.context_manager.load_context", return_value={}):
        assert "No active context" in core.cmd_env()


def test_cmd_env_success(mock_home, monkeypatch):
    ctx = {"current_org": "myorg", "account": "1", "role": "r", "region": "us-east-1"}
    monkeypatch.setattr("awsctl.context_manager.load_context", lambda: ctx)
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "myorg", "sso_start_url": "u", "sso_region": "r"},
    )

    with patch("awsctl.use_exports.emit_exports", return_value="export FOO=BAR"):
        output = core.cmd_env()
    assert "export FOO=BAR" in output


def test_cmd_login_success_with_plugin(mock_home, monkeypatch):
    # Org defines a registry plugin
    mock_org_data = {
        "name": "myorg",
        "sso_start_url": "u",
        "sso_region": "r",
        "plugins": ["registry.plugin"],
    }

    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: mock_org_data,
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "profile")
    monkeypatch.setattr("awsctl.sso_cache.load_active_sso_token", lambda *a, **k: None)

    # [FIX] Patch config.load_orgs_config where it is defined, so core.py sees the mock
    monkeypatch.setattr(
        "awsctl.config.load_orgs_config",
        lambda: {"orgs": [mock_org_data], "plugins": {"enabled": ["user.plugin"]}},
    )

    # Mock the plugin execution
    mock_load_plugins = MagicMock(return_value=["mock_module"])
    mock_call_hook = MagicMock()
    monkeypatch.setattr("awsctl.plugins.load_plugins", mock_load_plugins)
    monkeypatch.setattr("awsctl.plugins.call_hook", mock_call_hook)
    monkeypatch.setattr("awsctl.aws.run_aws", lambda a, **k: MagicMock(returncode=0))

    assert core.cmd_login("myorg") == 0

    # ASSERT: Both registry and user plugins were passed to load_plugins
    mock_load_plugins.assert_called_once()
    args, _ = mock_load_plugins.call_args
    loaded_plugins = args[0]
    assert "registry.plugin" in loaded_plugins
    assert "user.plugin" in loaded_plugins

    mock_call_hook.assert_called_once_with(
        ["mock_module"], "pre_login", org=mock_org_data
    )


def test_cmd_login_failure(mock_home, monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "myorg", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "profile")
    monkeypatch.setattr("awsctl.sso_cache.load_active_sso_token", lambda *a, **k: None)

    mock_proc = MagicMock(returncode=1, stderr="Error")
    monkeypatch.setattr("awsctl.aws.run_aws", lambda a, **k: mock_proc)

    assert core.cmd_login("myorg") == 1
    assert "Login failed" in "".join(mock_rich_console.captured)


def test_cmd_exec_passes_env(mock_home, monkeypatch):
    monkeypatch.setattr(
        "awsctl.context_manager.load_context", lambda: {"current_org": "myorg"}
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "myorg", "sso_start_url": "u", "sso_region": "r"},
    )

    monkeypatch.setattr(
        "awsctl.core.load_active_sso_token",
        lambda *a, **k: sso_cache.SsoToken(
            "tok", "u", "r", datetime.now(timezone.utc), {}
        ),
    )

    creds = {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "ST",
        }
    }
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: creds)

    mock_run = MagicMock(returncode=0)
    monkeypatch.setattr("subprocess.run", mock_run)

    core.cmd_exec("123", "Admin", "us-east-1", ["ls"])

    _, kwargs = mock_run.call_args
    assert kwargs["env"]["AWS_ACCESS_KEY_ID"] == "AK"


def test_cmd_exec_missing_creds(mock_home, monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.context_manager.load_context", lambda: {"current_org": "myorg"}
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "myorg", "sso_start_url": "u", "sso_region": "r"},
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
