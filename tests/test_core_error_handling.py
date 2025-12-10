# file: tests/test_core_error_handling.py
"""
Final wave of coverage tests.
"""

import configparser
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from awsctl import aws, cli, core, sso_cache, utils


# --- AWS Module Coverage ---
def test_aws_config_write_backup_failure(monkeypatch, tmp_path):
    """Test config write ignores backup failure."""
    cfg_file = tmp_path / "config"
    cfg_file.write_text("[default]")
    monkeypatch.setattr(aws, "AWS_CONFIG", cfg_file)

    cfg = configparser.RawConfigParser()
    cfg.read(cfg_file)

    # Mock copy2 to fail
    with patch("shutil.copy2", side_effect=OSError("Backup failed")):
        aws._configparser_write(cfg)

    assert cfg_file.exists()


def test_aws_config_validation():
    """Test validation of config values."""
    cfg = configparser.RawConfigParser()
    with pytest.raises(ValueError):
        aws._set_section(cfg, "profile test", {"key": "val\nue"})


def test_aws_list_accounts_pagination(monkeypatch):
    """Test pagination loop in list_accounts."""
    page1 = {"accountList": [{"accountId": "1"}], "nextToken": "token2"}
    page2 = {"accountList": [{"accountId": "2"}]}

    def side_effect(args, **kwargs):
        if "token2" in args:
            return MagicMock(returncode=0, stdout=json.dumps(page2), stderr="")
        return MagicMock(returncode=0, stdout=json.dumps(page1), stderr="")

    monkeypatch.setattr(aws, "run_aws", side_effect)

    results = aws.sso_list_accounts("url", "region")
    assert len(results) == 2


def test_aws_list_accounts_error(monkeypatch):
    """Test error handling in list accounts."""
    monkeypatch.setattr(
        aws, "run_aws", lambda a: MagicMock(returncode=1, stderr="Fail")
    )
    with pytest.raises(RuntimeError):
        aws.sso_list_accounts("url", "region")


# --- CLI Module Coverage ---
def test_cli_load_context_error(monkeypatch, mock_rich_console):
    """Test load_context handles corrupt JSON."""
    monkeypatch.setattr(
        cli, "CONTEXT_FILE", MagicMock(exists=lambda: True, read_text=lambda e: "{bad")
    )

    utils.set_debug(True)

    # Patch cli's debug_print
    with patch("awsctl.cli.debug_print") as mock_debug:
        ctx = cli.load_context()
        assert ctx == {}
        # Verify call
        mock_debug.assert_called()


def test_cli_switch_no_prev(monkeypatch, mock_rich_console):
    """Test switch - with no previous context."""
    monkeypatch.setattr("awsctl.context_manager.get_previous_context", lambda: None)

    args = type("Args", (), {"target": "-", "org": None})
    assert cli.cmd_switch(args) == 1
    assert "No previous context" in "".join(mock_rich_console.captured)


def test_cli_switch_incomplete_prev(monkeypatch, mock_rich_console):
    """Test switch - with partial previous context."""
    monkeypatch.setattr(
        "awsctl.context_manager.get_previous_context", lambda: {"org": "foo"}
    )

    args = type("Args", (), {"target": "-", "org": None})
    assert cli.cmd_switch(args) == 1
    assert "context is incomplete" in "".join(mock_rich_console.captured)


def test_cli_switch_non_interactive_validation(monkeypatch, mock_rich_console):
    """Test explicit switch validation."""
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "btavm"})

    org_conf = {
        "name": "btavm",
        "sso_start_url": "u",
        "sso_region": "r",
        "default_region": "r",
    }
    monkeypatch.setattr("awsctl.core.get_org", lambda x: org_conf)
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {})
    # [FIX] Use sso_cache.OrgRef, not aws.OrgRef
    monkeypatch.setattr(
        "awsctl.cli._get_org_ref", lambda c, n: sso_cache.OrgRef("n", "u", "r")
    )

    # [FIX] Mock resolve account ID to avoid it failing
    monkeypatch.setattr("awsctl.cli._resolve_account_id", lambda r, t: "123")

    args = type(
        "Args",
        (),
        {"target": "123", "account": "123", "role": None, "region": "r", "org": None},
    )

    assert cli.cmd_switch(args) == 1
    assert "requires --role" in "".join(mock_rich_console.captured)


# --- Core Module Coverage ---
def test_core_logout_cleanup_error(monkeypatch, mock_rich_console):
    """Test logout handles context save failure."""
    monkeypatch.setattr(
        "awsctl.context_manager.save_context_update",
        MagicMock(side_effect=Exception("SaveFail")),
    )
    utils.set_debug(True)

    # Patch debug_print in core
    with patch("awsctl.core.debug_print") as mock_debug:
        with patch("subprocess.run"):
            core.cmd_logout()

        # Verify call
        assert mock_debug.called


def test_core_cache_clear_errors(monkeypatch):
    """Test cache clear handles deletion errors."""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_file = MagicMock()
    mock_file.exists.return_value = True
    mock_file.is_symlink.return_value = False
    mock_file.is_file.return_value = True
    mock_file.unlink.side_effect = Exception("DelFail")

    # Must return iterable
    mock_path.iterdir.return_value = [mock_file]

    # Mock the full path chain: AWS_DIR / "cli" / "cache"
    # AWS_DIR is imported in core.py.
    # We need to mock awsctl.core.AWS_DIR so that (AWS_DIR / "cli" / "cache") resolves to mock_path

    # Mock AWS_DIR
    mock_aws = MagicMock()
    # Mock AWS_DIR / "cli"
    mock_cli_dir = MagicMock()
    # Mock AWS_DIR / "cli" / "cache"
    mock_aws.__truediv__.return_value = mock_cli_dir
    mock_cli_dir.__truediv__.return_value = mock_path

    monkeypatch.setattr(core, "AWS_DIR", mock_aws)

    utils.set_debug(True)

    # [FIX] Patch debug_print in core explicitly to verify call
    with patch("awsctl.core.debug_print") as mock_debug:
        core.cmd_cache_clear()

        # Verify it was called with our error message
        assert mock_debug.called
        # Check args for string content
        found = False
        for call in mock_debug.mock_calls:
            if call.args and "DelFail" in str(call.args[0]):
                found = True
                break
        assert found


# --- Utils Coverage ---
def test_force_stderr_exceptions(monkeypatch):
    """Test exceptions in context manager."""
    mock_stdout = MagicMock()
    mock_stdout.flush.side_effect = OSError
    monkeypatch.setattr(sys, "stdout", mock_stdout)

    with utils.ForceStderr():
        pass
