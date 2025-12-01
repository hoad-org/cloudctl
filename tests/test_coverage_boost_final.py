# file: tests/test_cli_coverage_boost.py
"""
Supplemental tests to hit 100% coverage on CLI logic.
"""
import subprocess
from unittest.mock import MagicMock

# [FIX] Import utils to enable debug mode
from awsctl import cli, utils


def test_whoami_error(monkeypatch, mock_rich_console):
    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="AccessDenied"
    )
    monkeypatch.setattr("awsctl.core.run_aws", mock_run)
    assert cli.cmd_whoami() == 1
    out = "".join(mock_rich_console.captured)
    assert "Failed to get identity" in out


def test_whoami_exception(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.core.run_aws", MagicMock(side_effect=Exception("Boom")))
    assert cli.cmd_whoami() == 1
    out = "".join(mock_rich_console.captured)
    assert "Error: Boom" in out


def test_open_exception(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "myorg"})
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config", MagicMock(side_effect=Exception("ConfigFail"))
    )
    assert cli.cmd_open() == 1
    out = "".join(mock_rich_console.captured)
    assert "Error" in out


def test_cmd_login_chaining_exceptions(monkeypatch, mock_rich_console):
    # [FIX] Enable debug mode so we can see the silenced warning
    utils.set_debug(True)

    # Test exception during account resolution
    monkeypatch.setattr("awsctl.core.cmd_login", lambda o: 0)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "myorg"})
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config", lambda: {"orgs": [{"name": "myorg"}]}
    )
    monkeypatch.setattr("awsctl.cli._get_org_ref", lambda c, n: MagicMock())

    # Raise exception during resolution
    monkeypatch.setattr(
        "awsctl.cli._resolve_account_id",
        MagicMock(side_effect=Exception("ResolveFail")),
    )

    # Mock switch to prevent actual switch logic
    mock_switch = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_switch", mock_switch)

    args = type("Args", (), {"org": "myorg", "account": "123", "role": None})
    cli.cmd_login(args)

    out = "".join(mock_rich_console.captured)
    # [FIX] Assertion now passes because debug mode is on
    assert "Account resolution warning" in out
    # Ensure it proceeded to switch with raw ID
    mock_switch.assert_called_once()

    # [FIX] Clean up: disable debug mode
    utils.set_debug(False)


def test_cmd_switch_keyboard_interrupt(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    # Simulate user cancelling interactive mode
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use",
        MagicMock(side_effect=KeyboardInterrupt),
    )

    args = type("Args", (), {"target": None, "account": None, "org": "myorg"})
    # Should catch KeyboardInterrupt and return 1
    assert cli.cmd_switch(args) == 1
    out = "".join(mock_rich_console.captured)
    assert "Operation cancelled" in out


def test_cmd_switch_generic_exception(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use",
        MagicMock(side_effect=Exception("RandomFail")),
    )

    args = type("Args", (), {"target": None, "account": None, "org": "myorg"})
    assert cli.cmd_switch(args) == 1
    out = "".join(mock_rich_console.captured)
    assert "Switch failed" in out


def test_cmd_list_dispatch(monkeypatch):
    # Cover the specific branches in cmd_list
    mock_orgs = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_orgs", mock_orgs)

    args = type("Args", (), {"resource": "orgs", "json": False})
    cli.cmd_list(args)
    mock_orgs.assert_called_once()


def test_main_matrix_flag(monkeypatch):
    # Cover the --matrix hidden flag
    mock_matrix = MagicMock()
    monkeypatch.setattr("awsctl.cool_features.run_matrix_login", mock_matrix)

    cli.main(["--matrix"])
    mock_matrix.assert_called_once()
