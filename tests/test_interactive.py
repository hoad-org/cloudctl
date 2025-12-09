# file: tests/test_interactive.py
"""
Tests for awsctl.interactive UI logic.
"""

from unittest.mock import MagicMock

import pytest

from awsctl import accounts, interactive


@pytest.fixture
def mock_inquirer(monkeypatch):
    """Mock the InquirerPy prompts."""
    dummy = MagicMock()
    dummy.execute.return_value = "mock_selection"
    monkeypatch.setattr("InquirerPy.inquirer.fuzzy", lambda **k: dummy)
    monkeypatch.setattr("InquirerPy.inquirer.select", lambda **k: dummy)
    return dummy


def test_select_account(mock_rich_console, mock_inquirer):
    accts = [
        accounts.Account("123", "Dev", "dev@example.com"),
        accounts.Account("456", "Prod", "prod@example.com"),
    ]
    mock_inquirer.execute.return_value = "123"
    # [FIX] Pass org_name for smart history lookup
    result = interactive.select_account(accts, "myorg")
    assert result == "123"
    captured = "".join(mock_rich_console.captured)
    assert "Available Accounts" in captured


def test_select_role(mock_rich_console, mock_inquirer):
    roles = ["Admin", "ViewOnly"]
    # [FIX] Provide dummy org dict
    org = {"name": "test", "role_aliases": {}}

    mock_inquirer.execute.return_value = "Admin"
    result = interactive.select_role(org, roles)

    assert result == "Admin"


def test_select_region(mock_rich_console, mock_inquirer):
    allowed = ["us-east-1", "eu-west-1"]
    mock_inquirer.execute.return_value = "eu-west-1"
    result = interactive.select_region(allowed, "us-east-1")
    assert result == "eu-west-1"


def test_select_region_single_choice(mock_rich_console, mock_inquirer):
    allowed = ["us-east-1"]
    result = interactive.select_region(allowed, "us-east-1")
    assert result == "us-east-1"
    assert len(mock_inquirer.execute.mock_calls) == 0


def test_select_region_defaults(mock_rich_console, mock_inquirer):
    # [FIX] Use None to indicate "no restrictions" (allow all),
    # since [] means "allow nothing" (deny all)
    mock_inquirer.execute.return_value = "us-east-2"
    result = interactive.select_region(None, "us-east-1")
    assert result == "us-east-2"


def test_run_interactive_use_success(monkeypatch, mock_rich_console, mock_inquirer):
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr("awsctl.interactive.list_accounts", lambda r: [accounts.Account("1", "n", "e")])
    monkeypatch.setattr("awsctl.interactive.list_roles", lambda r, a: ["Admin"])
    monkeypatch.setattr("awsctl.guardrails.sort_roles", lambda o, r: r)

    mock_inquirer.execute.side_effect = ["1", "Admin", "us-east-1"]

    acct, role, region = interactive.run_interactive_use("myorg")

    assert acct == "1"
    assert role == "Admin"


def test_run_interactive_use_no_accounts(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr("awsctl.interactive.list_accounts", lambda r: [])

    # [FIX] Expect RuntimeError, not SystemExit
    with pytest.raises(RuntimeError):
        interactive.run_interactive_use("myorg")


def test_run_interactive_use_api_error(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr("awsctl.interactive.list_accounts", MagicMock(side_effect=Exception("API Fail")))

    # [FIX] Expect RuntimeError
    with pytest.raises(RuntimeError):
        interactive.run_interactive_use("myorg")
