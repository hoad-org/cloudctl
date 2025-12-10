# file: tests/test_cli.py
# SPDX-License-Identifier: MIT
"""
Tests for awsctl.cli entrypoint.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from awsctl import cli  # [FIX] Added doctor import


def test_resolved_version_metadata(monkeypatch):
    monkeypatch.setattr("importlib.metadata.version", lambda x: "1.2.3")
    assert cli._resolved_version() == "1.2.3"


def test_resolved_version_fallback(monkeypatch):
    monkeypatch.setattr("importlib.metadata.version", MagicMock(side_effect=Exception))
    assert cli._resolved_version() == "0.0.0"


def test_determine_strategy():
    assert cli.determine_strategy([]) == "EXEC"
    assert cli.determine_strategy(["switch"]) == "EVAL"
    assert cli.determine_strategy(["login", "-a", "123"]) == "EVAL"
    assert cli.determine_strategy(["login", "--org", "foo"]) == "EXEC"


def test_main_version_flag(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.cli._resolved_version", lambda: "9.9.9")
    monkeypatch.setattr(cli, "stdout_console", mock_rich_console)
    assert cli.main(["--version"]) == 0
    assert "9.9.9" in "".join(mock_rich_console.captured)


def test_main_help_flag(monkeypatch, mock_rich_console):
    monkeypatch.setattr(cli, "stdout_console", mock_rich_console)
    assert cli.main(["--help"]) == 0
    assert "awsctl" in "".join(mock_rich_console.captured)


def test_main_check_strategy(capsys):
    assert cli.main(["--check-strategy", "switch"]) == 0
    out, _ = capsys.readouterr()
    assert "EVAL" in out.strip()


def test_cmd_login_dispatch(monkeypatch):
    mock_core_login = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.core.cmd_login", mock_core_login)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr("awsctl.context_manager.save_context_update", MagicMock())
    args = type(
        "Args", (), {"org": "btavm", "account": None, "role": None, "force": False}
    )
    assert cli.cmd_login(args) == 0
    mock_core_login.assert_called_with("btavm", force=False)


def test_cmd_login_missing_org(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {})
    monkeypatch.setattr(cli, "console", mock_rich_console)
    args = type("Args", (), {"org": None})
    assert cli.cmd_login(args) == 1
    assert "Error: Could not determine organization" in "".join(
        mock_rich_console.captured
    )


def test_cmd_switch_dispatch_simple(monkeypatch):
    mock_switch = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_switch", mock_switch)
    monkeypatch.setattr("sys.argv", ["awsctl", "switch"])
    assert cli.main() == 0
    mock_switch.assert_called_once()


def test_cmd_exec_dispatch(monkeypatch):
    mock_core_exec = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.core.cmd_exec", mock_core_exec)
    monkeypatch.setattr(
        "awsctl.cli.load_context",
        lambda: {
            "current_org": "btavm",
            "account": "123",
            "role": "Admin",
            "region": "us-east-1",
        },
    )
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {})
    monkeypatch.setattr("awsctl.cli._get_org_ref", MagicMock())
    monkeypatch.setattr("awsctl.cli._resolve_account_id", lambda ref, t: "123")
    args = type(
        "Args",
        (),
        {"account": None, "role": None, "region": None, "command": ["ls", "-la"]},
    )
    assert cli.cmd_exec(args) == 0
    mock_core_exec.assert_called_with("123", "Admin", "us-east-1", ["ls", "-la"])


def test_cmd_doctor_dispatch(monkeypatch):
    mock_run = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.doctor.run_diagnostics", mock_run)
    args = type("Args", (), {"fix_path": False})
    assert cli.cmd_doctor(args) == 0
    mock_run.assert_called_with(False)


def test_cmd_status_dispatch(monkeypatch):
    mock_stat = MagicMock()
    monkeypatch.setattr("awsctl.context_manager.print_status", mock_stat)
    assert cli.cmd_status() == 0
    mock_stat.assert_called_once()
