"""Tests for the SSO-based `cloudctl list-roles` command.

list-roles lists the IAM roles the current SSO user can assume, per account,
using the cached SSO access token + provider.list_roles (the same token path
`accounts` uses) — never ambient IAM credentials.
"""

from unittest.mock import MagicMock

import pytest

from cloudctl.commands.list_roles import ListRolesCommand


def _patch_chain(
    monkeypatch,
    *,
    org=None,
    token="tok",
    accounts=None,
    roles_by_acct=None,
    context=None,
):
    """Wire the local imports used inside ListRolesCommand to fakes."""
    org = (
        org
        if org is not None
        else {
            "name": "bt-avm",
            "sso_start_url": "https://d-9067dbbf5a.awsapps.com/start",
            "sso_region": "us-east-1",
        }
    )
    accounts = (
        accounts
        if accounts is not None
        else [
            {"Id": "111111111111", "Name": "mgmt"},
            {"Id": "222222222222", "Name": "audit"},
        ]
    )
    roles_by_acct = roles_by_acct or {
        "111111111111": ["AdministratorAccess"],
        "222222222222": ["ReadOnly", "SecurityAuditor"],
    }

    monkeypatch.setattr(
        "cloudctl.config.get_org", lambda name: {**org, "name": org.get("name", name)}
    )
    monkeypatch.setattr("cloudctl.sso_cache.load_active_sso_token", lambda ref: token)
    monkeypatch.setattr("cloudctl.accounts.get_account_list", lambda od, **k: accounts)
    monkeypatch.setattr("cloudctl.context_manager.load_context", lambda: context)

    provider = MagicMock()
    provider.list_roles.side_effect = lambda od, tok, acc_id: roles_by_acct.get(
        acc_id, []
    )
    monkeypatch.setattr("cloudctl.providers.get_provider", lambda od: provider)
    return provider


class _Args:
    def __init__(self, org=None, account=None, assigned=False, fmt="text"):
        self.org = org
        self.account = account
        self.assigned = assigned
        self.format = fmt


class TestRolesByAccount:
    def test_lists_roles_per_account_via_sso(self, monkeypatch):
        provider = _patch_chain(monkeypatch)
        data = ListRolesCommand().roles_by_account("bt-avm")
        assert data["111111111111"]["roles"] == ["AdministratorAccess"]
        assert data["222222222222"]["roles"] == ["ReadOnly", "SecurityAuditor"]
        assert provider.list_roles.call_count == 2

    def test_single_account_only_queries_that_account(self, monkeypatch):
        provider = _patch_chain(monkeypatch)
        data = ListRolesCommand().roles_by_account("bt-avm", account="111111111111")
        assert list(data.keys()) == ["111111111111"]
        assert provider.list_roles.call_count == 1

    def test_no_session_raises_actionable_error(self, monkeypatch):
        _patch_chain(monkeypatch, token=None)
        with pytest.raises(RuntimeError, match="No active SSO session"):
            ListRolesCommand().roles_by_account("bt-avm")


class TestResolveOrg:
    def test_explicit_org_wins(self, monkeypatch):
        _patch_chain(monkeypatch, context={"org": "ctx-org"})
        assert ListRolesCommand()._resolve_org(_Args(org="bt-avm")) == "bt-avm"

    def test_falls_back_to_context(self, monkeypatch):
        _patch_chain(monkeypatch, context={"current_org": "bt-avm"})
        assert ListRolesCommand()._resolve_org(_Args()) == "bt-avm"

    def test_no_org_no_context_raises(self, monkeypatch):
        _patch_chain(monkeypatch, context=None)
        with pytest.raises(RuntimeError, match="No organization given"):
            ListRolesCommand()._resolve_org(_Args())


class TestExecute:
    def test_text_output_success(self, monkeypatch):
        _patch_chain(monkeypatch)
        assert ListRolesCommand().execute(_Args(org="bt-avm")) == 0

    def test_json_output_success(self, monkeypatch, capsys):
        _patch_chain(monkeypatch)
        rc = ListRolesCommand().execute(_Args(org="bt-avm", fmt="json"))
        assert rc == 0
        import json

        out = json.loads(capsys.readouterr().out)
        assert out["organization"] == "bt-avm"
        names = {a["id"]: a["roles"] for a in out["accounts"]}
        assert names["111111111111"] == ["AdministratorAccess"]

    def test_no_session_returns_1(self, monkeypatch):
        _patch_chain(monkeypatch, token=None)
        assert ListRolesCommand().execute(_Args(org="bt-avm")) == 1

    def test_single_account_flag(self, monkeypatch):
        provider = _patch_chain(monkeypatch)
        rc = ListRolesCommand().execute(_Args(org="bt-avm", account="111111111111"))
        assert rc == 0
        assert provider.list_roles.call_count == 1
