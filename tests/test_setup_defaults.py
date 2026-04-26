# file: tests/test_setup_defaults.py
from unittest.mock import patch

import yaml
from cloudctl import core


def test_cmd_setup_merge_defaults(monkeypatch, tmp_path, mock_rich_console):
    """
    Ensure core.cmd_setup merges existing user config with defaults
    without overwriting custom keys.
    """
    # 1. Setup Mock Filesystem
    conf = tmp_path / "orgs.yaml"
    # Existing user config
    conf.write_text("other_key: true", encoding="utf-8")

    # 2. Patch Path and Shell dependencies
    monkeypatch.setattr("cloudctl.config.get_orgs_path", lambda ensure=True: conf)
    monkeypatch.setattr("cloudctl.shell.detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr("cloudctl.shell.inject_shell_function", lambda x: True)

    # 3. Patch Core and Wizard behavior
    # We must ensure cmd_config_sync returns 0 so the wizard reports success
    monkeypatch.setattr("cloudctl.core.cmd_config_sync", lambda: 0)

    # Mock the sample default yaml
    monkeypatch.setattr(
        "cloudctl.config.sample_orgs_yaml",
        lambda: "enabled_orgs: [default]\nplugins: {enabled: []}",
    )

    # 4. Execute
    # core.cmd_setup should return 0 if wizard.run_wizard returns True
    assert core.cmd_setup() == 0

    # 5. Verify Merge Result
    # [FIX] Enforce UTF-8 for cross-platform stability
    data = yaml.safe_load(conf.read_text(encoding="utf-8"))

    # Check that custom key survived
    assert data["other_key"] is True
    # Check that defaults were merged in
    assert "default" in data["enabled_orgs"]


def test_config_sync_loop(monkeypatch):
    """
    Verify that sync only attempts to ensure profiles for orgs
    that have both a start_url and a region.
    """
    # 1. Define mixed configuration
    orgs = [
        {"name": "full", "sso_start_url": "u", "sso_region": "r"},
        {"name": "partial", "sso_start_url": "u"},  # Missing region
        {"name": "empty"},  # Missing both
    ]

    # 2. Patch config loader
    monkeypatch.setattr("cloudctl.config.load_orgs_config", lambda: {"orgs": orgs})

    # 3. Patch the AWS layer where profile creation happens
    # Use the absolute path to ensure the patch hits the exact reference in core.py
    with patch("cloudctl.aws.ensure_sso_base_profile") as mock_ensure:
        core.cmd_config_sync()

        # 4. Assert only the 'full' org triggered the AWS call
        assert mock_ensure.call_count == 1
        # Verify it was called with the correct data
        mock_ensure.assert_called_with(orgs[0])
