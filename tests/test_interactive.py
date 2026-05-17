# file: tests/test_interactive.py
"""
Tests for cloudctl.interactive UI logic.
"""

from unittest.mock import MagicMock

import pytest
from cloudctl import accounts, interactive


@pytest.fixture()
def mock_inquirer(monkeypatch):
    """Mock the InquirerPy prompts."""
    dummy = MagicMock()
    # Ensure execute returns a mockable value
    dummy.execute.return_value = "mock_selection"

    # [FIX] Implementation likely uses inquirer.fuzzy or inquirer.select
    # Patch the specific module used by interactive.py
    monkeypatch.setattr("cloudctl.interactive.inquirer.fuzzy", lambda **k: dummy)
    monkeypatch.setattr("cloudctl.interactive.inquirer.select", lambda **k: dummy)
    return dummy


def test_select_account(mock_rich_console, mock_inquirer):
    mock_rich_console.clear()
    accts = [
        accounts.Account("123", "Dev", "dev@example.com"),
        accounts.Account("456", "Prod", "prod@example.com"),
    ]
    # InquirerPy selection returns the .value of the chosen choice
    mock_inquirer.execute.return_value = "123"

    # [FIX] Pass org_name for smart history lookup logic
    result = interactive.select_account(accts, "btavm")

    assert result == "123"
    captured = "".join(mock_rich_console.captured)
    assert "Available Accounts" in captured


def test_select_role(mock_rich_console, mock_inquirer):
    roles = ["Admin", "ViewOnly"]
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
    """Ensure we skip the prompt if only one region is allowed."""
    allowed = ["us-east-1"]
    result = interactive.select_region(allowed, "us-east-1")

    assert result == "us-east-1"
    # Prompt should not have been called
    assert mock_inquirer.execute.call_count == 0


def test_select_region_defaults(mock_rich_console, mock_inquirer):
    """Use None to indicate 'no restrictions' (allow all)."""
    mock_inquirer.execute.return_value = "us-east-2"
    result = interactive.select_region(None, "us-east-1")
    assert result == "us-east-2"


def test_run_interactive_use_success(monkeypatch, mock_rich_console, mock_inquirer):
    """Verify the full interactive flow: Account -> Role -> Region."""
    # 1. Mock Config
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "btavm", "sso_start_url": "u", "sso_region": "r"}]},
    )

    # 2. [FIX] Mock function calls as they appear in the interactive module
    # These functions are often imported into the namespace
    monkeypatch.setattr(
        "cloudctl.interactive.list_accounts",
        lambda token: [accounts.Account("1", "n", "e")],
    )
    monkeypatch.setattr(
        "cloudctl.interactive.list_roles", lambda token, acct: ["Admin"]
    )
    monkeypatch.setattr("cloudctl.guardrails.sort_roles", lambda o, r: r)
    monkeypatch.setattr("cloudctl.interactive.load_active_sso_token", lambda o: "token")

    # 3. Simulate sequential user inputs
    mock_inquirer.execute.side_effect = ["1", "Admin", "us-east-1"]

    acct, role, region = interactive.run_interactive_use("btavm")

    assert acct == "1"
    assert role == "Admin"
    assert region == "us-east-1"


def test_run_interactive_use_no_accounts(monkeypatch, mock_rich_console):
    """Ensure specific RuntimeError is raised when account list is empty."""
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "btavm", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr("cloudctl.interactive.load_active_sso_token", lambda o: "token")
    # [FIX] Patch interactive local reference
    monkeypatch.setattr("cloudctl.interactive.list_accounts", lambda token: [])

    with pytest.raises(RuntimeError) as e:
        interactive.run_interactive_use("btavm")
    assert "No accounts" in str(e.value)


def test_run_interactive_use_api_error(monkeypatch, mock_rich_console):
    """Ensure API exceptions are wrapped in RuntimeError."""
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "btavm", "sso_start_url": "u", "sso_region": "r"}]},
    )
    monkeypatch.setattr("cloudctl.interactive.load_active_sso_token", lambda o: "token")

    # [FIX] Trigger Exception
    monkeypatch.setattr(
        "cloudctl.interactive.list_accounts",
        MagicMock(side_effect=Exception("API Fail")),
    )

    with pytest.raises(RuntimeError) as e:
        interactive.run_interactive_use("btavm")
    assert "API Fail" in str(e.value)
