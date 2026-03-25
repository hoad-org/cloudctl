# file: tests/test_accounts.py
from __future__ import annotations

from datetime import datetime, timezone

import awsctl.accounts as mod
from awsctl.sso_cache import OrgRef, SsoToken


def test_pagination(monkeypatch):
    """Verify that list_accounts correctly parses AWS account metadata."""

    # 1. Mock the AWS CLI response
    # The implementation expects keys: accountId and accountName
    mock_data = [
        {"accountId": "1", "accountName": "A", "emailAddress": "a@x"},
        {"accountId": "2", "accountName": "B", "emailAddress": "b@x"},
    ]

    # [FIX] Align signature: implementation calls it with (token, raise_error=False)
    # The previous lambda was taking (url, region, token), causing a TypeError
    monkeypatch.setattr(
        "awsctl.aws.sso_list_accounts", lambda token, raise_error=False: mock_data
    )

    # 2. Mock the token loader
    # [FIX] Implementation uses OrgRef to find a token.
    # Must support kwargs to handle 'raise_error' or 'cache_dir' if passed.
    mock_token = SsoToken(
        "valid-tok", "https://u", "eu-west-2", datetime.now(timezone.utc), {}
    )
    monkeypatch.setattr(
        "awsctl.accounts.load_active_sso_token", lambda org, **k: mock_token
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
    monkeypatch.setattr("awsctl.accounts.load_active_sso_token", lambda org, **k: None)

    # Implementation should return an empty list or raise SystemExit
    out = mod.list_accounts(OrgRef("o", "u", "r"))
    assert out == []
