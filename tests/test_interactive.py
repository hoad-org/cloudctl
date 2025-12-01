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
    # Default execute return value
    dummy.execute.return_value = "mock_selection"

    # Mock the inquirer module attributes
    monkeypatch.setattr("InquirerPy.inquirer.fuzzy", lambda **k: dummy)
    monkeypatch.setattr("InquirerPy.inquirer.select", lambda **k: dummy)
    return dummy


def test_select_account(mock_rich_console, mock_inquirer):
    accts = [
        accounts.Account("123", "Dev", "dev@example.com"),
        accounts.Account("456", "Prod", "prod@example.com"),
    ]

    # Run
    mock_inquirer.execute.return_value = "123"
    result = interactive.select_account(accts)

    # Verify
    assert result == "123"
    captured = "".join(mock_rich_console.captured)
    assert "Available Accounts" in captured
    assert "Dev" in captured


def test_select_role(mock_rich_console, mock_inquirer):
    roles = ["Admin", "ViewOnly"]

    mock_inquirer.execute.return_value = "Admin"
    result = interactive.select_role(roles)

    assert result == "Admin"


def test_select_region(mock_rich_console, mock_inquirer):
    # Case 1: Multiple allowed, prompts user
    allowed = ["us-east-1", "eu-west-1"]
    mock_inquirer.execute.return_value = "eu-west-1"

    result = interactive.select_region(allowed, "us-east-1")
    assert result == "eu-west-1"


def test_select_region_single_choice(mock_rich_console, mock_inquirer):
    # Case 2: Only one allowed, auto-selects without prompt
    allowed = ["us-east-1"]
    result = interactive.select_region(allowed, "us-east-1")

    assert result == "us-east-1"
    # Should NOT call inquirer
    assert len(mock_inquirer.execute.mock_calls) == 0


def test_select_region_defaults(mock_rich_console, mock_inquirer):
    # Case 3: No allowed list (all allowed), uses defaults
    mock_inquirer.execute.return_value = "us-east-2"
    result = interactive.select_region([], "us-east-1")

    assert result == "us-east-2"


def test_run_interactive_use_success(monkeypatch, mock_rich_console, mock_inquirer):
    # Mock Config
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )

    # Mock Account/Role Listing
    monkeypatch.setattr(
        "awsctl.interactive.list_accounts", lambda r: [accounts.Account("1", "n", "e")]
    )
    monkeypatch.setattr("awsctl.interactive.list_roles", lambda r, a: ["Admin"])

    # Mock Guardrails
    monkeypatch.setattr("awsctl.guardrails.sort_roles", lambda o, r: r)

    # Setup Selections
    # 1. Account -> "1"
    # 2. Role -> "Admin"
    # 3. Region -> "us-east-1" (via select_region logic)
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

    with pytest.raises(SystemExit):
        interactive.run_interactive_use("myorg")

    assert "No accounts found" in "".join(mock_rich_console.captured)


def test_run_interactive_use_api_error(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr(
        "awsctl.interactive.list_accounts", MagicMock(side_effect=Exception("API Fail"))
    )

    with pytest.raises(SystemExit):
        interactive.run_interactive_use("myorg")

    assert "Error listing accounts" in "".join(mock_rich_console.captured)
