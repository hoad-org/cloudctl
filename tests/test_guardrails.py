# file: tests/test_guardrails.py
"""Tests for guardrails logic."""
import pytest

from awsctl import guardrails


def test_validate_region_allowed():
    cfg = {"name": "o", "allowed_regions": ["us-east-1"]}
    # Should not raise
    guardrails.validate_region(cfg, "us-east-1")


def test_validate_region_denied(mock_rich_console):
    cfg = {"name": "o", "allowed_regions": ["us-east-1"]}

    with pytest.raises(SystemExit):
        guardrails.validate_region(cfg, "eu-west-1")

    # Check the mock console buffer
    combined = "".join(mock_rich_console.captured)
    assert "Guardrail Violation" in combined
    assert "eu-west-1" in combined


def test_validate_region_empty_config():
    # No list = allow all
    guardrails.validate_region({}, "anywhere")


def test_sort_roles():
    cfg = {"preferred_roles": ["Admin"]}
    roles = ["Viewer", "Admin", "Editor"]
    sorted_roles = guardrails.sort_roles(cfg, roles)
    assert sorted_roles == ["Admin", "Editor", "Viewer"]


def test_sort_roles_missing_preferred():
    cfg = {"preferred_roles": ["MissingRole"]}
    roles = ["B", "A"]
    sorted_roles = guardrails.sort_roles(cfg, roles)
    assert sorted_roles == ["A", "B"]
