# file: tests/test_config.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yaml

from awsctl import config

# ... (Keep get_orgs_path and sample_orgs_yaml tests if they exist, or just use this file)


def test_config_hydrate_missing_org(monkeypatch, mock_rich_console):
    """Ensure we warn on missing orgs."""
    # [FIX] Patch get_registry, NOT KNOWN_ORGS, because _hydrate_orgs calls it now
    monkeypatch.setattr("awsctl.registry.get_registry", lambda: [])

    enabled_names = {"missing"}
    config._hydrate_orgs(enabled_names)

    assert "Warning: Org 'missing' not found" in "".join(mock_rich_console.captured)


def test_load_raw_config_missing_file(monkeypatch):
    monkeypatch.setattr(
        "awsctl.config.get_orgs_path",
        lambda ensure=False: MagicMock(exists=lambda: False),
    )
    assert config.load_raw_config() == {}


def test_load_raw_config_bad_yaml(monkeypatch, tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("{")
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=False: f)

    with pytest.raises(yaml.YAMLError):
        config.load_raw_config()
