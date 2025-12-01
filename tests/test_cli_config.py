# file: tests/test_cli_config.py
from __future__ import annotations

from unittest.mock import MagicMock

from awsctl import core


def test_config_sync_direct(monkeypatch):
    """
    Test the config sync logic directly via core.
    (The 'awsctl config' subcommand was removed in v1.3.0, replaced by setup automation)
    """
    # Mock config loader
    monkeypatch.setattr(
        "awsctl.config.load_orgs_config",
        lambda: {"orgs": [{"name": "myorg", "sso_start_url": "u", "sso_region": "r"}]},
    )

    # Mock ensure_profile
    ensure_mock = MagicMock()
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", ensure_mock)

    # Run
    rc = core.cmd_config_sync()

    assert rc == 0
    ensure_mock.assert_called()
