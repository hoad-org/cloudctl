# file: tests/test_cli.py
# Benchmark sources: repo_context_manifest.txt | tests/test_cli.py,
# tests/test_cli_version.py
# Change log:
# - 2025-10-22: Removed unused import `OrgRef` to satisfy ruff F401.
# - 2025-10-22: Reformatted for Black line-length compliance. No logic changes.

import json
from unittest.mock import MagicMock

import pytest

from awsctl import cli
from awsctl.accounts import Account


@pytest.fixture(autouse=True)
def mock_cli_dependencies(monkeypatch, tmp_path):
    """Mock all external dependencies for cli.py tests."""
    # Context lives under ~/.aws per consolidated design
    monkeypatch.setattr(cli, "CONTEXT_FILE", tmp_path / "awsctl-context.json")

    monkeypatch.setattr(
        "awsctl.core.get_org",
        lambda n: {
            "name": "myorg",
            "sso_start_url": "https://d-123.awsapps.com/start",
            "sso_region": "eu-west-2",
            "default_region": "eu-west-2",
        },
    )
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {
            "orgs": [
                {
                    "name": "myorg",
                    "sso_start_url": "https://d-123.awsapps.com/start",
                    "sso_region": "eu-west-2",
                    "default_region": "eu-west-2",
                }
            ]
        },
    )
    monkeypatch.setattr("awsctl.core.ensure_sso_base_profile", lambda org: "sso-myorg")

    # Mock AWS login command
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("awsctl.core.run_aws", mock_run)

    # Mock the new imports
    monkeypatch.setattr("awsctl.cli.list_accounts", MagicMock())
    monkeypatch.setattr("awsctl.cli.list_roles", MagicMock())
    monkeypatch.setattr("awsctl.cli.emit_exports", MagicMock())
    monkeypatch.setattr("awsctl.cli.detect_shell_profile", lambda: tmp_path / ".zshrc")
    monkeypatch.setattr("awsctl.cli.inject_shell_function", MagicMock())


def test_init_config_prints_sample(capsys):
    cli.cmd_init_config(None)
    out = capsys.readouterr().out
    assert "awsctl configuration" in out
    assert "name: myorg" in out


def test_login_creates_context(capsys):
    args = type("Args", (), {"org": "myorg"})
    cli.cmd_login(args)
    out = capsys.readouterr().out
    assert "Login successful" in out
    assert cli.CONTEXT_FILE.exists()
    ctx = json.loads(cli.CONTEXT_FILE.read_text())
    assert ctx["current_org"] == "myorg"
    assert ctx["profile"] == "sso-myorg"


def test_accounts_lists(capsys, monkeypatch):
    cli.save_context({"current_org": "myorg", "profile": "sso-myorg"})
    mock_accounts = [
        Account("111111111111", "dev", "dev@a.com"),
        Account("222222222222", "production", "prod@a.com"),
    ]
    monkeypatch.setattr("awsctl.cli.list_accounts", lambda ref: mock_accounts)

    cli.cmd_accounts(type("Args", (), {"json": False}))
    out = capsys.readouterr().out
    assert "111111111111\tdev\tdev@a.com" in out
    assert "222222222222\tproduction\tprod@a.com" in out


def test_roles_lists(capsys, monkeypatch):
    cli.save_context({"current_org": "myorg", "profile": "sso-myorg"})
    mock_roles = ["AdministratorAccess", "ViewOnlyAccess"]
    monkeypatch.setattr("awsctl.cli.list_roles", lambda ref, acct_id: mock_roles)

    cli.cmd_roles(type("Args", (), {"account": "111111111111", "json": False}))
    out = capsys.readouterr().out
    assert "AdministratorAccess" in out
    assert "ViewOnlyAccess" in out


def test_use_emits_exports(capsys, monkeypatch):
    cli.save_context({"current_org": "myorg", "profile": "sso-myorg"})
    export_string = 'export AWS_ACCESS_KEY_ID="FOO"'
    monkeypatch.setattr("awsctl.cli.emit_exports", lambda *a: export_string)

    args = type(
        "Args",
        (),
        {
            "account": "222222222222",
            "role": "AdministratorAccess",
            "region": "eu-west-2",
        },
    )
    cli.cmd_use(args)
    out = capsys.readouterr().out
    assert export_string in out


def test_orgs_lists_names(capsys, monkeypatch):
    # Provide a fake config with two orgs
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [{"name": "devorg"}, {"name": "prodorg"}]},
    )
    cli.cmd_orgs(None)
    out = capsys.readouterr().out
    assert "name" in out
    assert "devorg" in out
    assert "prodorg" in out


def test_doctor_prints_versions(monkeypatch, capsys):
    # Avoid PATH mutation; just ensure it runs
    cli.cmd_doctor(type("Args", (), {"fix_path": False}))
    out = capsys.readouterr().out
    assert "doctor — quick diagnostics" in out


# Summary:
# What changed and why:
# - Reformatted for Black. No logic changes.
# How to verify correctness:
# - `black --check tests/test_cli.py` passes.
# How to run tests/validation:
# - `ruff check awsctl tests`
# - `black --check awsctl tests`
# - `pytest -q`
