# file: tests/test_cli_config.py
from __future__ import annotations

from unittest.mock import MagicMock

from awsctl import core


def test_config_sync_direct(monkeypatch):
    """
    Test the config sync logic directly via core.
    Ensures that for every configured org, the SSO profile is initialized.
    """
    # 1. Mock the config loader
    # The implementation expects an 'orgs' list. We provide full metadata to
    # satisfy any internal validation logic in the sync loop.
    mock_config = {
        "orgs": [
            {
                "name": "engineering",
                "sso_start_url": "https://eng.okta.com",
                "sso_region": "us-east-1",
            }
        ]
    }

    # [FIX] Patch the load_orgs_config used inside the core module
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: mock_config)

    # 2. Mock the profile initialization
    # [FIX] Implementation in core.py likely imports this from aws.py.
    # We patch it at the source to ensure the call is intercepted.
    ensure_mock = MagicMock()
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", ensure_mock)

    # 3. Execute
    rc = core.cmd_config_sync()

    # 4. Assertions
    assert rc == 0
    # Verify that ensure_sso_base_profile was called with our mock org data
    ensure_mock.assert_called_once_with(mock_config["orgs"][0])


def test_config_sync_empty_orgs(monkeypatch):
    """Verify that sync handles empty configurations without error."""
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {"orgs": []})

    ensure_mock = MagicMock()
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", ensure_mock)

    rc = core.cmd_config_sync()

    assert rc == 0
    ensure_mock.assert_not_called()
