# file: tests/test_accounts.py
from __future__ import annotations

import json
import types
from datetime import datetime, timezone

import awsctl.accounts as mod
from awsctl.sso_cache import OrgRef, SsoToken


class P:
    def __init__(self, out, rc=0):
        self.stdout = out
        self.returncode = rc
        self.stderr = ""


def test_pagination(monkeypatch):
    pages = [
        {
            "accountList": [{"accountId": "1", "accountName": "A", "emailAddress": "a@x"}],
            "nextToken": "t",
        },
        {"accountList": [{"accountId": "2", "accountName": "B", "emailAddress": "b@x"}]},
    ]
    i = {"i": 0}

    def run(args, check, capture_output, text):
        j = i["i"]
        i["i"] += 1
        return P(json.dumps(pages[j]))

    monkeypatch.setattr(mod, "subprocess", types.SimpleNamespace(run=run))
    monkeypatch.setattr(
        mod,
        "load_active_sso_token",
        lambda org: SsoToken("TOK", "u", "eu-west-2", datetime.now(timezone.utc), {}),
    )
    out = mod.list_accounts(OrgRef("o", "u", "eu-west-2"))
    assert [a.account_id for a in out] == ["1", "2"]
