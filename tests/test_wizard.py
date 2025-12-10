# file: tests/test_wizard.py
"""Tests for the interactive setup wizard."""

from unittest.mock import MagicMock, patch

import yaml
from InquirerPy import inquirer

from awsctl import config, core, registry, shell, wizard


def test_wizard_happy_path(monkeypatch, tmp_path):
    # 1. Mock File System
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "ORGS_USER", tmp_path / ".awsctl" / "orgs.yaml")

    # 2. Mock Registry Choices
    mock_registry = [
        {
            "name": "engineering",
            "label": "Engineering",
            "description": "Main stuff",
            "sso_start_url": "u",
            "sso_region": "r",
            "default_region": "r",
            "allowed_regions": ["r"],
        }
    ]
    monkeypatch.setattr(registry, "KNOWN_ORGS", mock_registry)
    # Mock get_choices to return the formatted list
    monkeypatch.setattr(
        registry,
        "get_choices",
        lambda: [{"name": "Engineering - Main stuff", "value": mock_registry[0]}],
    )

    # 3. Mock User Input (Checkbox selection)
    mock_checkbox = MagicMock()
    mock_checkbox.execute.return_value = [mock_registry[0]]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_checkbox)

    # 4. Mock confirm (overwrite)
    mock_confirm = MagicMock()
    mock_confirm.execute.return_value = True
    monkeypatch.setattr(inquirer, "confirm", lambda **k: mock_confirm)

    # 5. Mock Dependencies
    monkeypatch.setattr(core, "cmd_config_sync", MagicMock())
    monkeypatch.setattr(shell, "detect_shell_profile", lambda: tmp_path / ".zshrc")
    monkeypatch.setattr(shell, "inject_shell_function", MagicMock(return_value=True))

    # Run
    wizard.run_wizard()

    # Verify Config Written
    conf_path = config.get_orgs_path()
    assert conf_path.exists()
    data = yaml.safe_load(conf_path.read_text())

    # Ensure the "enabled_orgs" list was written
    assert "engineering" in data["enabled_orgs"]


def test_wizard_abort_on_overwrite(monkeypatch, tmp_path):
    # Setup existing config
    conf_path = tmp_path / ".awsctl" / "orgs.yaml"
    conf_path.parent.mkdir()
    conf_path.write_text("exists: true")

    monkeypatch.setattr(config, "ORGS_USER", conf_path)

    # Mock inputs
    mock_checkbox = MagicMock()
    mock_checkbox.execute.return_value = [
        {"name": "org", "sso_start_url": "u", "sso_region": "r", "default_region": "r"}
    ]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_checkbox)

    # User says NO to overwrite
    mock_confirm = MagicMock()
    mock_confirm.execute.return_value = False
    monkeypatch.setattr(inquirer, "confirm", lambda **k: mock_confirm)

    wizard.run_wizard()

    # Verify NOT overwritten
    assert "exists: true" in conf_path.read_text()


def test_wizard_write_fail(monkeypatch, tmp_path, mock_rich_console):
    """Test config write failure."""
    # Mock inputs
    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr("awsctl.wizard.inquirer.checkbox", lambda **k: mock_cb)

    # Mock config path
    conf = tmp_path / "orgs.yaml"
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=True: conf)

    # Fail the write
    with patch("tempfile.mkstemp", side_effect=OSError("Write Fail")):
        assert wizard.run_wizard() is False

    assert "Failed to write config" in "".join(mock_rich_console.captured)


def test_wizard_cli_sync_fail(monkeypatch, tmp_path, mock_rich_console):
    """Test AWS CLI sync failure."""
    # Mock inputs
    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr("awsctl.wizard.inquirer.checkbox", lambda **k: mock_cb)

    monkeypatch.setattr(
        "awsctl.config.get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml"
    )

    # Mock failure
    monkeypatch.setattr(
        "awsctl.core.cmd_config_sync", MagicMock(side_effect=Exception("Sync Fail"))
    )

    # Mock shell detection
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr("awsctl.shell.inject_shell_function", lambda x: True)

    assert wizard.run_wizard() is True
    assert "Failed to sync profiles" in "".join(mock_rich_console.captured)
