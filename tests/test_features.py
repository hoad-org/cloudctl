# file: tests/test_features.py
# SPDX-License-Identifier: MIT
"""Tests for new feature modules."""

from unittest.mock import MagicMock

from cloudctl import cli, context_manager


def test_context_manager(tmp_path, monkeypatch):
    """Verify context saving, loading, and rotation logic."""
    monkeypatch.setattr(context_manager, "CONTEXT_FILE", tmp_path / "ctx.json")

    # 1. Test Save/Load
    # Implementation expects kwargs which are packed into a dict
    context_manager.save_context_update(
        org="btavm", account="1", role="r", region="reg"
    )
    data = context_manager.load_context()
    assert data["current_org"] == "btavm"
    assert data["account"] == "1"

    # 2. Test Rotation (History)
    # When we save a new context, the old one moves to 'previous'
    context_manager.save_context_update(account="2")
    prev = context_manager.get_previous_context()

    assert prev is not None
    assert prev["account"] == "1"


def test_status_dashboard(monkeypatch, mock_rich_console):
    """Verify the status dashboard correctly identifies and prints context."""
    # 1. Mock context loading
    monkeypatch.setattr(
        "cloudctl.context_manager.load_context",
        lambda: {"current_org": "foo", "account": "123", "role": "r", "region": "r"},
    )
    # 2. Mock config hydration for token check
    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda name: {"name": "foo", "sso_start_url": "u", "sso_region": "r"},
    )
    # 3. Mock token check to simulate being logged in (avoiding SystemExit)
    monkeypatch.setattr(
        "cloudctl.sso_cache.load_active_sso_token",
        lambda *a: MagicMock(),
    )

    # 4. Run
    # Implementation uses cloudctl.utils.console for output
    context_manager.print_status()

    # 5. Verify output using unified mock_rich_console
    output = "".join(mock_rich_console.captured)
    assert "AWS Context" in output
    assert "foo" in output
    assert "123" in output


def test_alias_switch_success(monkeypatch, mock_rich_console):
    """Verify @alias targets are correctly resolved to full contexts."""
    # 1. Mock Config with Alias
    mock_aliases = {
        "prod": {
            "org": "btavm",
            "account": "123",
            "role": "Admin",
            "region": "eu-west-1",
        }
    }
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": mock_aliases},
    )

    # 2. Mock Org Hydration
    org_data = {
        "name": "btavm",
        "sso_start_url": "u",
        "sso_region": "r",
        "allowed_regions": ["eu-west-1"],
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org_data)

    # 3. Mock Token & Exports
    monkeypatch.setattr("cloudctl.cli.emit_exports", lambda *a, **k: "export A=B")
    monkeypatch.setattr("cloudctl.context_manager.save_context_update", MagicMock())

    # 4. Run Switch with Alias
    # Use type('Args', ...) to simulate argparse namespace
    args = type(
        "Args",
        (),
        {"target": "@prod", "org": None, "account": None, "role": None, "region": None},
    )
    rc = cli.cmd_switch(args)

    assert rc == 0


def test_alias_switch_not_found(monkeypatch, mock_rich_console):
    """Verify error reporting when an undefined alias is requested."""
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": {}},
    )
    args = type("Args", (), {"target": "@missing", "org": None})

    # cmd_switch should catch the error and return failure code
    rc = cli.cmd_switch(args)

    assert rc == 1
    output = "".join(mock_rich_console.captured)
    assert "not defined" in output


def test_alias_switch_invalid_definition(monkeypatch, mock_rich_console):
    """Verify validation for aliases missing required context fields."""
    mock_aliases = {"broken": {"org": "btavm"}}  # Missing account, role, etc.
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config",
        lambda: {"orgs": [], "plugins": {}, "aliases": mock_aliases},
    )
    args = type("Args", (), {"target": "@broken", "org": None})

    rc = cli.cmd_switch(args)

    assert rc == 1
    output = "".join(mock_rich_console.captured)
    assert "missing" in output.lower()
