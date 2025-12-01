# file: tests/test_accounts.py
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import awsctl.accounts as mod
from awsctl.sso_cache import OrgRef, SsoToken


def test_pagination(monkeypatch):
    # Mock token
    monkeypatch.setattr(
        mod,
        "load_active_sso_token",
        lambda org: SsoToken("TOK", "u", "eu-west-2", datetime.now(timezone.utc), {}),
    )

    # Mock run() to return pages
    pages = [
        {
            "accountList": [
                {"accountId": "1", "accountName": "A", "emailAddress": "a@x"}
            ],
            "nextToken": "t",
        },
        {
            "accountList": [
                {"accountId": "2", "accountName": "B", "emailAddress": "b@x"}
            ]
        },
    ]

    # Iterator to yield pages
    page_iter = iter(pages)

    def mock_run(*args, **kwargs):
        try:
            data = next(page_iter)
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(data), stderr=""
            )
        except StopIteration:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="{}", stderr=""
            )

    monkeypatch.setattr(mod, "run", mock_run)

    out = mod.list_accounts(OrgRef("o", "u", "eu-west-2"))
    assert [a.account_id for a in out] == ["1", "2"]
