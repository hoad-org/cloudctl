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


def test_cli_accounts_module(monkeypatch, mock_cfg, capsys, mock_rich_console):
    mock_acct = accounts.Account("1", "n", "e")
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [mock_acct])

    # Text output -> Mock Console
    cli_accounts.cmd_accounts(mock_cfg, "myorg", False)
    captured = "".join(mock_rich_console.captured)
    assert "1" in captured
    assert "n" in captured

    # JSON output -> stdout (capsys)
    cli_accounts.cmd_accounts(mock_cfg, "myorg", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert data["accountList"][0]["account_id"] == "1"

    # Empty
    mock_rich_console.clear()
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [])
    cli_accounts.cmd_accounts(mock_cfg, "myorg", False)
    captured = "".join(mock_rich_console.captured)
    assert "No accounts found" in captured


def test_cli_roles_module(monkeypatch, mock_cfg, capsys, mock_rich_console):
    monkeypatch.setattr(cli_accounts, "list_roles", lambda r, a: ["Admin"])

    cli_accounts.cmd_roles(mock_cfg, "myorg", "123", False)
    captured = "".join(mock_rich_console.captured)
    assert "Admin" in captured

    cli_accounts.cmd_roles(mock_cfg, "myorg", "123", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert "Admin" in data["roles"]

    mock_rich_console.clear()
    monkeypatch.setattr(cli_accounts, "list_roles", lambda r, a: [])
    cli_accounts.cmd_roles(mock_cfg, "myorg", "123", False)
    captured = "".join(mock_rich_console.captured)
    assert "No roles found" in captured


def test_org_resolution_failures(mock_cfg):
    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg({}, "foo")
    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg(mock_cfg, "missing")
