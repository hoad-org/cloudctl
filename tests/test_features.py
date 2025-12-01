# file: tests/test_features.py
"""Tests for new feature modules."""

from awsctl import context_manager, cool_features


def test_context_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(context_manager, "CONTEXT_FILE", tmp_path / "ctx.json")

    # Save
    context_manager.save_context_update(
        org="myorg", account="1", role="r", region="reg"
    )
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
