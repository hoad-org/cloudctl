# file: tests/test_cli_edge_cases.py
# SPDX-License-Identifier: MIT
"""Supplemental tests to hit 100% coverage on CLI logic."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest

from awsctl import cli


def test_whoami_error(monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any) -> None:
    monkeypatch.setattr(cli, "console", mock_rich_console)
    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="AccessDenied"
    )
    monkeypatch.setattr("awsctl.core.run_aws", mock_run)
    assert cli.cmd_whoami() == 1
    assert "Failed to get identity" in "".join(mock_rich_console.captured)


def test_whoami_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    monkeypatch.setattr(cli, "console", mock_rich_console)
    monkeypatch.setattr("awsctl.core.run_aws", MagicMock(side_effect=Exception("Boom")))
    assert cli.cmd_whoami() == 1
    assert "Error: Boom" in "".join(mock_rich_console.captured)


def test_open_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    monkeypatch.setattr(cli, "console", mock_rich_console)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "btavm"})
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config", MagicMock(side_effect=Exception("ConfigFail"))
    )
    assert cli.cmd_open() == 1
    assert "Error" in "".join(mock_rich_console.captured)


def test_cmd_login_chaining_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("awsctl.core.cmd_login", lambda o, **k: 0)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "btavm"})
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config", lambda: {"orgs": [{"name": "btavm"}]}
    )
    monkeypatch.setattr("awsctl.cli._get_org_ref", lambda c, n: MagicMock())

    monkeypatch.setattr(
        "awsctl.cli._resolve_account_id",
        MagicMock(side_effect=Exception("ResolveFail")),
    )
    mock_switch = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_switch", mock_switch)
    args = type(
        "Args", (), {"org": "btavm", "account": "123", "role": None, "force": False}
    )
    cli.cmd_login(args)
    mock_switch.assert_called_once()


def test_cmd_switch_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    monkeypatch.setattr(cli, "console", mock_rich_console)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use",
        MagicMock(side_effect=KeyboardInterrupt),
    )
    args = type("Args", (), {"target": None, "account": None, "org": "btavm"})
    assert cli.cmd_switch(args) == 1
    assert "Operation cancelled" in "".join(mock_rich_console.captured)


def test_cmd_switch_generic_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    monkeypatch.setattr(cli, "console", mock_rich_console)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use",
        MagicMock(side_effect=Exception("RandomFail")),
    )
    args = type("Args", (), {"target": None, "account": None, "org": "btavm"})
    assert cli.cmd_switch(args) == 1
    assert "Switch failed" in "".join(mock_rich_console.captured)


def test_cmd_list_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_orgs = MagicMock(return_value=0)
    monkeypatch.setattr("awsctl.cli.cmd_orgs", mock_orgs)
    args = type("Args", (), {"resource": "orgs", "json": False})
    cli.cmd_list(args)
    mock_orgs.assert_called_once()
