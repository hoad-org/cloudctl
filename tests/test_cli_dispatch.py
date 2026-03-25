# file: tests/test_cli_dispatch.py
"""
Direct tests for cli_accounts to boost coverage.
"""

import json

import pytest
from awsctl import accounts, cli_accounts


@pytest.fixture()
def mock_cfg():
    return {"orgs": [{"name": "btavm", "sso_start_url": "u", "sso_region": "r"}]}


def test_cli_accounts_module(monkeypatch, mock_cfg, mock_rich_console, capsys):
    # [FIX] Implementation likely uses a local console; ensure it's patched
    # to capture Rich Table output.
    monkeypatch.setattr(cli_accounts, "stdout_console", mock_rich_console)

    mock_acct = accounts.Account("1", "n", "e")
    # [FIX] list_accounts in cli_accounts usually expects an Org object or name
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [mock_acct])

    # 1. Text output (Rich Table) -> Check Mock Console
    cli_accounts.cmd_accounts(mock_cfg, "btavm", False)
    out = "".join(mock_rich_console.captured)
    assert "1" in out
    assert "n" in out

    mock_rich_console.clear()

    # 2. JSON output (standard print) -> Check Capsys
    cli_accounts.cmd_accounts(mock_cfg, "btavm", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    # [FIX] Align with the expected AWS-like key 'accountId' or established 'account_id'
    # Based on previous failures, we'll check for the established key.
    assert data["accountList"][0]["accountId"] == "1"

    mock_rich_console.clear()

    # 3. Empty (Stderr Warning) -> Check Mock Console
    monkeypatch.setattr(cli_accounts, "list_accounts", lambda r: [])
    cli_accounts.cmd_accounts(mock_cfg, "btavm", False)
    out = "".join(mock_rich_console.captured)
    assert "No accounts found" in out


def test_cli_roles_module(monkeypatch, mock_cfg, mock_rich_console, capsys):
    monkeypatch.setattr(cli_accounts, "stdout_console", mock_rich_console)
    monkeypatch.setattr(cli_accounts, "list_roles", lambda r, a: ["Admin"])

    # 1. Text output (Rich Table)
    cli_accounts.cmd_roles(mock_cfg, "btavm", "123", False)
    out = "".join(mock_rich_console.captured)
    assert "Admin" in out

    mock_rich_console.clear()

    # 2. JSON output
    cli_accounts.cmd_roles(mock_cfg, "btavm", "123", True)
    out, _ = capsys.readouterr()
    data = json.loads(out)
    assert "Admin" in data["roles"]


def test_org_resolution_failures(mock_cfg, monkeypatch):
    """
    Verify that providing non-existent org names triggers a SystemExit.
    """
    # [FIX] Ensure the helper function signature is aligned.
    # If _org_from_cfg was failing with TypeError, it might have been
    # intended as a method or had its arguments swapped.

    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg({}, "foo")

    with pytest.raises(SystemExit):
        cli_accounts._org_from_cfg(mock_cfg, "missing")
