# file: tests/test_wizard.py
"""Tests for the interactive setup wizard."""

from unittest.mock import MagicMock

import yaml
from awsctl import config, core, registry, shell, wizard
from awsctl.wizard import inquirer


def test_wizard_happy_path(monkeypatch, tmp_path, mock_rich_console):
    # 1. Mock File System
    # We mock HOME and ORGS_USER to point into our temp directory
    monkeypatch.setattr(config, "HOME", tmp_path)
    orgs_file = tmp_path / ".awsctl" / "orgs.yaml"
    monkeypatch.setattr(config, "ORGS_USER", orgs_file)

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
    # Patch registry to return our mock data
    monkeypatch.setattr(registry, "get_registry", lambda: mock_registry)
    monkeypatch.setattr(
        registry,
        "get_choices",
        # Use exact Rich markup expected by the implementation
        lambda: [
            {"name": "Engineering — [dim]Main stuff[/]", "value": mock_registry[0]}
        ],
    )

    # 3. Mock User Input (InquirerPy checkbox and confirm)
    mock_checkbox = MagicMock()
    mock_checkbox.execute.return_value = [mock_registry[0]]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_checkbox)

    mock_confirm = MagicMock()
    mock_confirm.execute.return_value = True
    monkeypatch.setattr(inquirer, "confirm", lambda **k: mock_confirm)

    # 4. Mock Dependencies
    # CRITICAL: cmd_config_sync must return 0 for the wizard to continue to Step 5
    monkeypatch.setattr(core, "cmd_config_sync", lambda: 0)
    monkeypatch.setattr(shell, "detect_shell_profile", lambda: tmp_path / ".zshrc")
    monkeypatch.setattr(shell, "inject_shell_function", MagicMock(return_value=True))

    # 5. Execute
    success = wizard.run_wizard()

    # 6. Verify Results
    assert success is True

    # Verify Config Written
    # The wizard should have created the directories and the file
    assert orgs_file.exists()

    # Specify encoding to prevent issues with Rich special characters on Windows
    data = yaml.safe_load(orgs_file.read_text(encoding="utf-8"))

    # Ensure the "enabled_orgs" list was written correctly
    assert "engineering" in data["enabled_orgs"]


def test_wizard_config_update_fail(monkeypatch, tmp_path, mock_rich_console):
    """
    Test the failure path when writing/reading config raises an exception.
    """
    # 1. Setup environment
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(registry, "get_registry", lambda: [{"name": "org"}])
    monkeypatch.setattr(
        registry, "get_choices", lambda: [{"name": "Org", "value": {"name": "org"}}]
    )

    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_cb)

    # 2. Force config read/write to fail
    # We create a mock path that raises an exception on read_text
    mock_path = MagicMock()
    mock_path.parent.exists.return_value = True
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = Exception("Disk IO Error")

    # We patch core.get_orgs_path because that's what the wizard calls
    monkeypatch.setattr(core, "get_orgs_path", lambda ensure=True: mock_path)

    # 3. Run
    success = wizard.run_wizard()

    # 4. Assert Failure Handling
    assert success is False

    # Ensure the failure message was printed to the rich console
    captured_output = "".join(mock_rich_console.captured)
    assert "Failed to update config" in captured_output
    assert "Disk IO Error" in captured_output
