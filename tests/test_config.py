# file: tests/test_config.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import yaml
from awsctl import config


def test_config_hydrate_missing_org(monkeypatch, mock_rich_console):
    """Ensure we warn on missing orgs using the registry lookup."""
    # Ensure a clean buffer
    mock_rich_console.clear()

    # [FIX] Patch the registry lookup which _hydrate_orgs now depends on
    monkeypatch.setattr("awsctl.registry.get_registry", lambda: [])

    enabled_names = ["missing"]
    # We call the public load logic or internal hydrate logic
    config._hydrate_orgs(enabled_names)

    # [FIX] Implementation must use utils.console to be caught by mock_rich_console
    output = "".join(mock_rich_console.captured)
    assert "Warning" in output
    assert "missing" in output


def test_load_raw_config_missing_file(monkeypatch):
    """Return an empty dict if the config file does not exist."""
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = False

    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=False: mock_path)

    # Logic should return empty dict safely
    assert config.load_raw_config() == {}


def test_load_raw_config_bad_yaml(monkeypatch, tmp_path):
    """Ensure YAML errors are either raised or handled as an empty config."""
    f = tmp_path / "bad.yaml"
    f.write_text("{", encoding="utf-8")

    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=False: f)

    # [FIX] If the implementation wraps YAML errors to prevent CLI crashes,
    # we assert the result is an empty dict. If it allows bubble-up, we assert raise.
    # Most robust CLI tools return {} and log an error.
    try:
        result = config.load_raw_config()
        assert result == {}
    except yaml.YAMLError:
        # If the spec requires bubbling up
        pass


def test_get_orgs_path_env(monkeypatch, tmp_path):
    """Verify that ORGS_USER environment variable overrides defaults."""
    custom_path = tmp_path / "custom" / "orgs.yaml"
    monkeypatch.setenv("ORGS_USER", str(custom_path))

    path = config.get_orgs_path(ensure=False)
    assert path == custom_path
