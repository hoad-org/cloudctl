# file: tests/test_config.py
"""
Tests for awsctl.config (Configuration loading and paths).
"""
import os
import stat

import pytest
import yaml

from awsctl import config, registry


def test_get_orgs_path_creates_secure_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "ORGS_USER", tmp_path / ".awsctl" / "orgs.yaml")
    p = config.get_orgs_path(ensure=True)
    if os.name == "posix":
        mode = p.parent.stat().st_mode
        assert mode & stat.S_IRWXU == 0o700


def test_hydration_logic(monkeypatch, tmp_path):
    """Ensure enabled_orgs maps to Registry data."""
    p = tmp_path / "orgs.yaml"
    p.write_text("enabled_orgs:\n- engineering\n")
    monkeypatch.setattr(config, "ORGS_USER", p)

    # Mock Registry
    mock_registry = [
        {
            "name": "engineering",
            "sso_start_url": "REGISTRY_URL",
            "allowed_regions": ["eu-west-1"],
        },
        {"name": "sales", "sso_start_url": "SALES_URL"},
    ]
    monkeypatch.setattr(registry, "KNOWN_ORGS", mock_registry)

    data = config.load_orgs_config()
    assert len(data["orgs"]) == 1
    assert data["orgs"][0]["name"] == "engineering"
    assert data["orgs"][0]["sso_start_url"] == "REGISTRY_URL"


def test_user_cannot_override_guardrails(monkeypatch, tmp_path):
    """SECURITY: User YAML fields must be ignored in favor of Registry."""
    p = tmp_path / "orgs.yaml"
    # User attempts to define their own 'orgs' block with weak security
    p.write_text(
        "enabled_orgs:\n"
        "  - engineering\n"
        "orgs:\n"
        "  - name: engineering\n"
        "    allowed_regions: ['ALL']\n"
    )
    monkeypatch.setattr(config, "ORGS_USER", p)

    mock_registry = [{"name": "engineering", "allowed_regions": ["STRICT_ONLY"]}]
    monkeypatch.setattr(registry, "KNOWN_ORGS", mock_registry)

    data = config.load_orgs_config()
    org = data["orgs"][0]

    # Registry must win
    assert org["allowed_regions"] == ["STRICT_ONLY"]
    assert "ALL" not in org["allowed_regions"]


def test_load_orgs_config_invalid(monkeypatch, tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("{")
    monkeypatch.setattr(config, "ORGS_USER", p)
    with pytest.raises(yaml.YAMLError):
        config.load_orgs_config()
