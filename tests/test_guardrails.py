# file: tests/test_guardrails.py
"""Tests for guardrails logic."""

from unittest.mock import MagicMock

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
    # No list = Deny All (Secure default)
    with pytest.raises(SystemExit):
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


def test_check_min_version_pass(monkeypatch):
    monkeypatch.setattr("awsctl.guardrails.__version__", "2.0.0")
    # Config requires 1.0.0, current is 2.0.0 -> Pass
    guardrails.check_min_version({"min_client_version": "1.0.0"})


def test_check_min_version_fail(monkeypatch, mock_rich_console):
    monkeypatch.setattr("awsctl.guardrails.__version__", "1.0.0")
    # Config requires 2.0.0, current is 1.0.0 -> Fail
    with pytest.raises(SystemExit):
        guardrails.check_min_version({"min_client_version": "2.0.0"})

    out = "".join(mock_rich_console.captured)
    assert "UPDATE REQUIRED" in out


def test_check_break_glass_prompt(monkeypatch, mock_rich_console, tmp_path):
    monkeypatch.setattr(guardrails, "AUDIT_LOG", tmp_path / "audit.log")

    cfg = {"name": "prod", "sensitive_roles": ["Admin"]}

    # Mock Inquirer to return a reason
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = "Fixing DB"
    monkeypatch.setattr("InquirerPy.inquirer.text", lambda **k: mock_prompt)

    guardrails.check_break_glass(cfg, "Admin")

    # Verify log written
    log_content = (tmp_path / "audit.log").read_text()
    assert "ROLE=Admin" in log_content
    assert "REASON=Fixing DB" in log_content
    assert "SENSITIVE ROLE ACCESS" in "".join(mock_rich_console.captured)


def test_check_break_glass_abort(monkeypatch, mock_rich_console):
    cfg = {"name": "prod", "sensitive_roles": ["Admin"]}

    mock_prompt = MagicMock()
    mock_prompt.execute.side_effect = KeyboardInterrupt
    monkeypatch.setattr("InquirerPy.inquirer.text", lambda **k: mock_prompt)

    with pytest.raises(SystemExit):
        guardrails.check_break_glass(cfg, "Admin")

    assert "Access Aborted" in "".join(mock_rich_console.captured)
