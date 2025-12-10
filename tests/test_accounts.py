# file: tests/test_accounts.py
from __future__ import annotations

from datetime import datetime, timezone

import awsctl.accounts as mod
from awsctl.sso_cache import OrgRef, SsoToken


def test_pagination(monkeypatch):
    # Mock the lower-level aws call
    mock_data = [
        {"accountId": "1", "accountName": "A", "emailAddress": "a@x"},
        {"accountId": "2", "accountName": "B", "emailAddress": "b@x"},
    ]
    monkeypatch.setattr(
        "awsctl.aws.sso_list_accounts", lambda url, region, access_token: mock_data
    )

    # [FIX] Mock the token loader to accept kwargs (raise_error=False)
    mock_token = SsoToken("valid-tok", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr(
        "awsctl.accounts.load_active_sso_token", lambda r, **k: mock_token
    )

    out = mod.list_accounts(OrgRef("o", "u", "eu-west-2"))
    assert [a.account_id for a in out] == ["1", "2"]
    assert [a.account_name for a in out] == ["A", "B"]
