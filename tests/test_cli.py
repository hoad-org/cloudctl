# file: tests/test_cli.py
# SPDX-License-Identifier: MIT
"""
Tests for awsctl.cli entrypoint.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from awsctl import cli


def test_resolved_version_metadata(monkeypatch):
    """Verify version retrieval from package metadata."""
    monkeypatch.setattr("importlib.metadata.version", lambda x: "1.2.3")
    assert cli._resolved_version() == "1.2.3"


def test_resolved_version_fallback(monkeypatch):
    """Verify that version falls back to the internal default on metadata failure."""
    monkeypatch.setattr("importlib.metadata.version", MagicMock(side_effect=Exception))
    # [FIX] Implementation V8+ uses 1.2.3 as the hardcoded developer fallback
    assert cli._resolved_version() == "1.2.3"


def test_determine_strategy():
    """Verify that the shell wrapper is instructed to EVAL for context changes."""
    assert cli.determine_strategy([]) == "EXEC"
    assert cli.determine_strategy(["switch"]) == "EVAL"
    # [FIX] Logic must detect shorthand flags for login-chaining
    assert cli.determine_strategy(["login", "-a", "123"]) == "EVAL"
    assert cli.determine_strategy(["login", "--org", "foo"]) == "EXEC"


def test_main_version_flag(monkeypatch, mock_rich_console):
    """Verify --version prints to stdout and exits with 0."""
    monkeypatch.setattr("awsctl.cli._resolved_version", lambda: "9.9.9")
    # Patch the console used inside main/dispatcher
    monkeypatch.setattr(cli, "stdout_console", mock_rich_console.console)
    assert cli.main(["--version"]) == 0
    assert "9.9.9" in "".join(mock_rich_console.captured)


def test_main_help_flag(monkeypatch, mock_rich_console):
    """Verify --help prints usage and exits with 0."""
    monkeypatch.setattr(cli, "stdout_console", mock_rich_console.console)
    assert cli.main(["--help"]) == 0
    assert "awsctl" in "".join(mock_rich_console.captured).lower()


def test_main_check_strategy(capsys):
    """Verify --check-strategy prints the routing instruction for the shell wrapper."""
    assert cli.main(["--check-strategy", "switch"]) == 0
    out, _ = capsys.readouterr()
    assert "EVAL" in out.strip()


def test_cmd_login_dispatch(monkeypatch):
    """Verify that cmd_login correctly invokes core logic."""
    mock_core_login = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.core.cmd_login", mock_core_login)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr("awsctl.context_manager.save_context_update", MagicMock())

    # [FIX] Added missing account/role/region fields to prevent AttributeError in dispatcher
    args = type(
        "Args",
        (),
        {"org": "btavm", "account": None, "role": None, "region": None, "force": False},
    )
    assert cli.cmd_login(args) == 0
    mock_core_login.assert_called_with("btavm", force=False)


def test_cmd_login_missing_org(monkeypatch, mock_rich_console):
    """Verify error reporting when no org is provided or can be inferred."""
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {"orgs": []})
    monkeypatch.setattr(cli, "console", mock_rich_console.console)

    args = type("Args", (), {"org": None})
    assert cli.cmd_login(args) == 1
    # Check unified capture
    assert "determine" in "".join(mock_rich_console.captured).lower()


def test_cmd_switch_dispatch_simple(monkeypatch):
    """Verify main entrypoint dispatches to cmd_switch correctly."""
    mock_switch = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_switch", mock_switch)
    # Simulate: awsctl switch
    monkeypatch.setattr("sys.argv", ["awsctl", "switch"])
    assert cli.main() == 0
    assert mock_switch.called


def test_cmd_exec_dispatch(monkeypatch):
    """Verify dispatcher correctly resolves defaults from context before calling core.exec."""
    mock_core_exec = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.core.cmd_exec", mock_core_exec)

    # Setup context that should be used as fallbacks
    monkeypatch.setattr(
        "awsctl.cli.load_context",
        lambda: {
            "current_org": "btavm",
            "account": "123",
            "role": "Admin",
            "region": "us-east-1",
        },
    )
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {"orgs": []})
    monkeypatch.setattr("awsctl.cli._get_org_ref", lambda n: MagicMock())
    monkeypatch.setattr("awsctl.cli._resolve_account_id", lambda ref, target: "123")

    # Args are all None to force fallback logic
    args = type(
        "Args",
        (),
        {
            "account": None,
            "role": None,
            "region": None,
            "command": ["ls", "-la"],
            "org": None,
        },
    )
    assert cli.cmd_exec(args) == 0
    mock_core_exec.assert_called_with("123", "Admin", "us-east-1", ["ls", "-la"])


def test_cmd_doctor_dispatch(monkeypatch):
    """Verify doctor command triggers diagnostics."""
    mock_run = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.doctor.run_diagnostics", mock_run)
    args = type("Args", (), {"fix_path": False})
    assert cli.cmd_doctor(args) == 0
    mock_run.assert_called()


def test_cmd_status_dispatch(monkeypatch):
    """Verify status command triggers the dashboard view."""
    mock_stat = MagicMock(return_value=0)
    # Patch where the cli module looks for cmd_status
    monkeypatch.setattr("awsctl.cli.cmd_status", mock_stat)

    # We test the main entry point to ensure dispatcher works
    cli.main(["status"])
    assert mock_stat.called
