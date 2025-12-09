# file: tests/test_cli_dispatch.py
"""
Direct tests for cli_accounts to boost coverage.
"""

import json

import pytest

from awsctl import accounts, cli_accounts


@pytest.fixture
def mock_cfg():
    return {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]}


def test_cli_accounts_module(monkeypatch, mock_cfg, mock_rich_console, capsys):
    # Patch Rich console to capture Table output
    monkeypatch.setattr(cli_accounts, "stdout_console", mock_rich_console)

    mock_acct = accounts.Account("1", "n", "e")
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [mock_acct])

    # 1. Text output (Rich Table) -> Check Mock Console
    cli_accounts.cmd_accounts(mock_cfg, "myorg", False)
    out = "".join(mock_rich_console.captured)
    assert "1" in out
    assert "n" in out

    mock_rich_console.clear()

    # 2. JSON output (print) -> Check Capsys
    cli_accounts.cmd_accounts(mock_cfg, "myorg", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["accountList"][0]["account_id"] == "1"

    # 3. Empty (Stderr Warning) -> Check Mock Console (since stderr console is globally mocked)
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [])
    cli_accounts.cmd_accounts(mock_cfg, "myorg", False)
    out = "".join(mock_rich_console.captured)
    assert "No accounts found" in out


def test_cli_roles_module(monkeypatch, mock_cfg, mock_rich_console, capsys):
    monkeypatch.setattr(cli_accounts, "stdout_console", mock_rich_console)
    monkeypatch.setattr(cli_accounts, "list_roles", lambda r, a: ["Admin"])

    # 1. Text output (Rich Table) -> Check Mock Console
    cli_accounts.cmd_roles(mock_cfg, "myorg", "123", False)
    out = "".join(mock_rich_console.captured)
    assert "Admin" in out

    mock_rich_console.clear()

    # 2. JSON output (print) -> Check Capsys
    cli_accounts.cmd_roles(mock_cfg, "myorg", "123", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert "Admin" in data["roles"]


def test_org_resolution_failures(mock_cfg):
    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg({}, "foo")
    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg(mock_cfg, "missing")
