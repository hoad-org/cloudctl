# file: tests/test_accounts.py
from __future__ import annotations

from datetime import datetime, timezone
import json

import cloudctl.accounts as mod
from cloudctl.sso_cache import OrgRef, SsoToken


def test_pagination(monkeypatch):
    """Verify that list_accounts correctly parses AWS account metadata."""

    # 1. Mock the AWS CLI response
    # The implementation expects keys: accountId and accountName
    mock_data = [
        {"accountId": "1", "accountName": "A", "emailAddress": "a@x"},
        {"accountId": "2", "accountName": "B", "emailAddress": "b@x"},
    ]

    # [FIX] Align signature: implementation calls it with (token, region=None)
    # The previous lambda was taking (url, region, token), causing a TypeError
    monkeypatch.setattr(
        "cloudctl.aws.sso_list_accounts", lambda token, region=None: mock_data
    )

    # 2. Mock the token loader
    # [FIX] Implementation uses OrgRef to find a token.
    # Must support kwargs to handle 'raise_error' or 'cache_dir' if passed.
    mock_token = SsoToken(
        "valid-tok", "https://u", "eu-west-2", datetime.now(timezone.utc), {}
    )
    monkeypatch.setattr(
        "cloudctl.accounts.load_active_sso_token", lambda org, **k: mock_token
    )

    # 3. Execute logic
    # mod.list_accounts(org_ref) -> List[Account]
    out = mod.list_accounts(OrgRef("o", "https://u", "eu-west-2"))

    # 4. Verify Attributes
    # [FIX] We use .id and .name in the Account class to match standard AWS SDK patterns,
    # but the test was looking for .account_id and .account_name.
    # We update the assertion to check the mapped properties.
    assert [a.id for a in out] == ["1", "2"]
    assert [a.name for a in out] == ["A", "B"]


def test_list_accounts_no_token(monkeypatch, mock_rich_console):
    """Verify failure path when no active SSO session is found."""
    # Simulate token missing
    monkeypatch.setattr(
        "cloudctl.accounts.load_active_sso_token", lambda org, **k: None
    )

    # Implementation should return an empty list or raise SystemExit
    out = mod.list_accounts(OrgRef("o", "u", "r"))
    assert out == []


def test_accounts_json_format(monkeypatch, capsys):
    """Verify accounts command with --format json outputs valid JSON."""
    from cloudctl.commands.accounts import AccountsCommand
    from argparse import Namespace

    # Mock get_account_list
    mock_accounts = [
        {
            "Id": "123456789",
            "Name": "prod",
            "Email": "prod@example.com",
            "Status": "ACTIVE",
        },
        {
            "Id": "987654321",
            "Name": "dev",
            "Email": "dev@example.com",
            "Status": "ACTIVE",
        },
    ]
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_account_list",
        lambda org, force_sync=False: mock_accounts,
    )

    # Mock get_org
    monkeypatch.setattr("cloudctl.commands.accounts.get_org", lambda org: {"name": org})

    # Execute with json format
    cmd = AccountsCommand()
    args = Namespace(org="test-org", sync=False, format="json")
    result = cmd.execute(args)

    # Verify exit code
    assert result == 0

    # Capture stdout and verify JSON
    captured = capsys.readouterr()
    # JSON goes to stdout
    output_text = captured.out.strip()
    assert (
        output_text
    ), f"No JSON output captured. stdout={repr(captured.out)}, stderr={repr(captured.err)}"

    output = json.loads(output_text)
    assert output["organization"] == "test-org"
    assert len(output["accounts"]) == 2
    assert output["count"] == 2


def test_accounts_json_structure(monkeypatch, capsys):
    """Verify JSON output contains correct account structure."""
    from cloudctl.commands.accounts import AccountsCommand
    from argparse import Namespace

    # Mock get_account_list
    mock_accounts = [
        {
            "Id": "111111111",
            "Name": "staging",
            "Email": "staging@x.com",
            "Status": "ACTIVE",
        },
    ]
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_account_list",
        lambda org, force_sync=False: mock_accounts,
    )

    # Mock get_org
    monkeypatch.setattr("cloudctl.commands.accounts.get_org", lambda org: {"name": org})

    # Execute
    cmd = AccountsCommand()
    args = Namespace(org="test-org", sync=False, format="json")
    cmd.execute(args)

    # Verify JSON structure
    captured = capsys.readouterr()
    output_text = captured.out.strip()
    output = json.loads(output_text)

    # Verify each account has required fields
    account = output["accounts"][0]
    assert "id" in account
    assert "name" in account
    assert "email" in account
    assert "status" in account
    assert account["id"] == "111111111"
    assert account["name"] == "staging"
    assert account["email"] == "staging@x.com"


def test_accounts_json_count_field(monkeypatch, capsys):
    """Verify JSON output includes correct count field."""
    from cloudctl.commands.accounts import AccountsCommand
    from argparse import Namespace

    # Mock get_account_list with 3 accounts
    mock_accounts = [
        {"Id": "1", "Name": "a", "Email": "a@x.com", "Status": "ACTIVE"},
        {"Id": "2", "Name": "b", "Email": "b@x.com", "Status": "ACTIVE"},
        {"Id": "3", "Name": "c", "Email": "c@x.com", "Status": "ACTIVE"},
    ]
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_account_list",
        lambda org, force_sync=False: mock_accounts,
    )

    # Mock get_org
    monkeypatch.setattr("cloudctl.commands.accounts.get_org", lambda org: {"name": org})

    # Execute
    cmd = AccountsCommand()
    args = Namespace(org="test-org", sync=False, format="json")
    cmd.execute(args)

    # Verify count matches account list
    captured = capsys.readouterr()
    output_text = captured.out.strip()
    output = json.loads(output_text)

    assert output["count"] == 3
    assert len(output["accounts"]) == 3


def test_accounts_table_still_works(monkeypatch, capsys):
    """Verify table output still works when --format json not specified."""
    from cloudctl.commands.accounts import AccountsCommand
    from argparse import Namespace

    # Mock get_account_list
    mock_accounts = [
        {"Id": "123456789", "Name": "prod", "Email": "prod@example.com"},
        {"Id": "987654321", "Name": "dev", "Email": "dev@example.com"},
    ]
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_account_list",
        lambda org, force_sync=False: mock_accounts,
    )

    # Mock get_org
    monkeypatch.setattr("cloudctl.commands.accounts.get_org", lambda org: {"name": org})

    # Execute with table format (default)
    cmd = AccountsCommand()
    args = Namespace(org="test-org", sync=False, format="table")
    result = cmd.execute(args)

    # Verify exit code
    assert result == 0

    # Verify table output (not JSON) is produced
    captured = capsys.readouterr()
    # Table output goes to stderr
    assert "Accounts in" in captured.err or "prod" in captured.err
