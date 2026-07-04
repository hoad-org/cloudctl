# file: tests/test_core_error_handling.py
"""
Final wave of coverage tests.
"""

import configparser
import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import aws, cli, core, sso_cache, utils


# --- AWS Module Coverage ---
def test_aws_config_write_backup_failure(monkeypatch, tmp_path):
    """Test config write ignores backup failure and proceeds to write."""
    cfg_file = tmp_path / "config"
    cfg_file.write_text("[default]", encoding="utf-8")
    monkeypatch.setattr(aws, "AWS_CONFIG", cfg_file)

    cfg = configparser.RawConfigParser()
    cfg.read(cfg_file)

    # [FIX] Implementation expects _configparser_write(config, path)
    with patch("shutil.copy2", side_effect=OSError("Backup failed")):
        aws._configparser_write(cfg, cfg_file)

    assert cfg_file.exists()


def test_aws_config_validation():
    """Test validation of config values to prevent profile corruption."""
    cfg = configparser.RawConfigParser()
    # Profiles should not contain newline characters in values
    with pytest.raises(ValueError):
        aws._set_section(cfg, "profile test", {"key": "val\nue"})


def test_aws_list_accounts_pagination(monkeypatch):
    """Test pagination loop in sso_list_accounts."""
    page1 = {"accountList": [{"accountId": "1"}], "nextToken": "token2"}
    page2 = {"accountList": [{"accountId": "2"}]}

    # [FIX] Aligned with run_aws signature (args as single list)
    def side_effect(args):
        if "token2" in str(args):
            return {"returncode": 0, "stdout": json.dumps(page2), "stderr": ""}
        return {"returncode": 0, "stdout": json.dumps(page1), "stderr": ""}

    monkeypatch.setattr(aws, "run_aws", side_effect)

    # list_accounts takes (token_obj) in v1.3.0+
    mock_token = sso_cache.SsoToken("tok", "u", "r", None, {})
    results = aws.sso_list_accounts(mock_token)
    assert len(results) == 2


def test_aws_list_accounts_error(monkeypatch):
    """Test error handling when AWS SSO API returns an error."""
    # [FIX] run_aws returns a dictionary
    monkeypatch.setattr(
        aws, "run_aws", lambda a: {"returncode": 1, "stderr": "AccessDenied"}
    )
    mock_token = sso_cache.SsoToken("tok", "u", "r", None, {})
    with pytest.raises(RuntimeError) as e:
        aws.sso_list_accounts(mock_token)
    assert "AccessDenied" in str(e.value)


# --- CLI Module Coverage ---
def test_cli_load_context_error(monkeypatch, mock_rich_console):
    """Test load_context handles corrupt context JSON gracefully."""
    # Mock the file to exist but contain garbage
    monkeypatch.setattr(
        cli,
        "CONTEXT_FILE",
        MagicMock(exists=lambda: True, read_text=lambda **k: "{bad"),
    )

    utils.set_debug(True)
    # [FIX] Patch debug_print in the module where it is defined
    with patch("cloudctl.utils.debug_print") as mock_debug:
        ctx = cli.load_context()
        assert ctx == {}
        assert mock_debug.called


def test_cli_switch_no_prev(monkeypatch, mock_rich_console):
    """Test switch - (hyphen) fails when no history exists."""
    monkeypatch.setattr("cloudctl.context_manager.get_previous_context", lambda: None)

    # Simulate Namespace object
    args = type("Args", (), {"target": "-", "org": None})
    assert cli.cmd_switch(args) == 1
    assert "No previous context" in "".join(mock_rich_console.captured)


def test_cli_switch_incomplete_prev(monkeypatch, mock_rich_console):
    """Test switch - fails when history is missing required fields."""
    monkeypatch.setattr(
        "cloudctl.context_manager.get_previous_context", lambda: {"org": "foo"}
    )

    args = type("Args", (), {"target": "-", "org": None})
    assert cli.cmd_switch(args) == 1
    assert "incomplete" in "".join(mock_rich_console.captured).lower()


def test_cli_switch_non_interactive_validation(monkeypatch, mock_rich_console):
    """Test that explicit switches validate required flags (like --role)."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"current_org": "btavm"})
    org_conf = {"name": "btavm", "sso_start_url": "u", "sso_region": "r"}

    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org_conf)
    monkeypatch.setattr(
        "cloudctl.cli._get_org_ref", lambda n: sso_cache.OrgRef("n", "u", "r")
    )
    monkeypatch.setattr("cloudctl.cli._resolve_account_id", lambda r, t: "123")

    # [FIX] role is None, which should trigger a validation error
    args = type(
        "Args",
        (),
        {"target": "123", "account": "123", "role": None, "region": "r", "org": None},
    )

    assert cli.cmd_switch(args) == 1
    assert "role" in "".join(mock_rich_console.captured).lower()


# --- Core Module Coverage ---
def test_core_logout_cleanup_error(monkeypatch, mock_rich_console):
    """Test logout proceeds even if context cleanup fails."""
    monkeypatch.setattr(
        "cloudctl.context_manager.save_context_update",
        MagicMock(side_effect=Exception("SaveFail")),
    )
    utils.set_debug(True)

    with patch("cloudctl.utils.debug_print") as mock_debug:
        core.cmd_logout()
        # Should have logged the internal failure but finished logout
        assert mock_debug.called


def test_core_cache_clear_errors(monkeypatch, mock_rich_console):
    """Test cache clear handles file deletion permission errors."""
    mock_file = MagicMock()
    mock_file.is_file.return_value = True
    mock_file.unlink.side_effect = OSError("Permission Denied")

    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.iterdir.return_value = [mock_file]

    # [FIX] Simplified path mocking
    monkeypatch.setattr("cloudctl.aws.SSO_CACHE_DIR", mock_path)
    utils.set_debug(True)

    with patch("cloudctl.utils.debug_print") as mock_debug:
        core.cmd_cache_clear()
        assert any("Permission Denied" in str(c) for c in mock_debug.mock_calls)


# --- Utils Coverage ---
def test_force_stderr_exceptions(monkeypatch):
    """Verify context manager handles flush errors gracefully."""
    mock_stdout = MagicMock()
    mock_stdout.flush.side_effect = OSError
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    with utils.ForceStderr():
        # Should not raise
        pass
