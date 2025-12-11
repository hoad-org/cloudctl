# file: tests/test_wizard.py
"""Tests for the interactive setup wizard."""

from unittest.mock import MagicMock

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
    # [FIX] Mock both get_registry (for manual check) and get_choices (for display)
    monkeypatch.setattr(registry, "get_registry", lambda: mock_registry)

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
    # [FIX] Windows: Must specify encoding="utf-8" or ⚠️ char fails on CP1252
    data = yaml.safe_load(conf_path.read_text(encoding="utf-8"))

    # Ensure the "enabled_orgs" list was written
    assert "engineering" in data["enabled_orgs"]


def test_wizard_config_update_fail(monkeypatch, tmp_path, mock_rich_console):
    """
    Test the failure path when writing/reading config raises an exception.
    This covers the 'except Exception' block in Step 4 of wizard.py.
    """
    # 1. Setup minimal happy path mocks until the crash point
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "ORGS_USER", tmp_path / "orgs.yaml")

    monkeypatch.setattr(registry, "get_registry", lambda: [{"name": "org"}])
    monkeypatch.setattr(
        registry, "get_choices", lambda: [{"name": "Org", "value": {"name": "org"}}]
    )

    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_cb)

    # 2. Force config read to fail
    # We mock 'read_text' on the Path object returned by get_orgs_path
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = Exception("Disk IO Error")
    monkeypatch.setattr(config, "get_orgs_path", lambda ensure=True: mock_path)

    # Run
    success = wizard.run_wizard()

    # Assert
    assert success is False
    assert "Failed to update config" in "".join(mock_rich_console.captured)
