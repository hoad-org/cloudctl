# file: tests/test_features.py
"""Tests for new feature modules."""

from unittest.mock import MagicMock

from awsctl import cli, context_manager, cool_features


def test_context_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(context_manager, "CONTEXT_FILE", tmp_path / "ctx.json")

    # Save
    context_manager.save_context_update(org="myorg", account="1", role="r", region="reg")
    data = context_manager.load_context()
    assert data["current_org"] == "myorg"
    assert data["account"] == "1"

    # Rotation
    context_manager.save_context_update(account="2")
    prev = context_manager.get_previous_context()
    assert prev["account"] == "1"


def test_status_dashboard(monkeypatch, capsys):
    # Mock context loading
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "foo", "account": "123"},
    )
    # Mock config hydration for token check
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda name: {"name": "foo", "sso_start_url": "u", "sso_region": "r"},
    )
    # Mock token check to raise Exit (simulating not logged in)
    monkeypatch.setattr(
        "awsctl.sso_cache.load_active_sso_token",
        lambda *a: (_ for _ in ()).throw(SystemExit()),
    )

    # Run
    context_manager.print_status()

    # Verify output (Rich console writes to STDERR)
    _, err = capsys.readouterr()
    assert "AWS Active Context" in err
    assert "foo" in err


def test_matrix_mode(capsys):
    # Mock sleep to run instantly
    cool_features.time.sleep = lambda x: None

    cool_features.run_matrix_login()

    out, _ = capsys.readouterr()
    # Matrix uses a standard Console(), check both streams to be safe,
    # but likely stdout for main console
    assert "SYSTEM READY" in (out + _)


def test_alias_switch_success(monkeypatch, mock_rich_console):
    # 1. Mock Config with Alias
    mock_aliases = {
        "prod": {
            "org": "myorg",
            "account": "123",
            "role": "Admin",
            "region": "eu-west-1",
        }
    }
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": mock_aliases},
    )

    # 2. Mock Org Hydration
    org_data = {
        "name": "myorg",
        "sso_start_url": "u",
        "sso_region": "r",
        "allowed_regions": ["eu-west-1"],
    }
    monkeypatch.setattr("awsctl.core.get_org", lambda x: org_data)

    # 3. Mock Token & Exports
    monkeypatch.setattr("awsctl.cli.emit_exports", lambda *a, **k: "export A=B")
    monkeypatch.setattr("awsctl.context_manager.save_context_update", MagicMock())

    # 4. Run Switch with Alias
    args = type("Args", (), {"target": "@prod", "org": None})
    rc = cli.cmd_switch(args)

    assert rc == 0


def test_alias_switch_not_found(monkeypatch, mock_rich_console):
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": {}},
    )
    args = type("Args", (), {"target": "@missing", "org": None})
    rc = cli.cmd_switch(args)

    assert rc == 1
    assert "not defined" in "".join(mock_rich_console.captured)


def test_alias_switch_invalid_definition(monkeypatch, mock_rich_console):
    mock_aliases = {"broken": {"org": "myorg"}}  # Missing fields
    monkeypatch.setattr(
        "awsctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": mock_aliases},
    )
    args = type("Args", (), {"target": "@broken", "org": None})
    rc = cli.cmd_switch(args)

    assert rc == 1
    assert "missing required fields" in "".join(mock_rich_console.captured)
