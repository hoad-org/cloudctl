# file: tests/test_guardrails.py
"""Tests for guardrails logic."""

from unittest.mock import MagicMock

import pytest
from awsctl import guardrails


def test_validate_region_allowed():
    """Verify that allowed regions pass through without error."""
    cfg = {"name": "o", "allowed_regions": ["us-east-1"]}
    # Should not raise any exception
    guardrails.validate_region(cfg, "us-east-1")


def test_validate_region_denied(mock_rich_console):
    """Verify that unauthorized regions trigger a SystemExit with a violation message."""
    mock_rich_console.clear()
    cfg = {"name": "o", "allowed_regions": ["us-east-1"]}

    # [FIX] Logic must raise SystemExit(1) on violation
    with pytest.raises(SystemExit):
        guardrails.validate_region(cfg, "eu-west-1")

    # [FIX] Implementation must write to the console buffer captured by the Rich mock
    combined = "".join(mock_rich_console.captured)
    assert "Guardrail Violation" in combined
    assert "eu-west-1" in combined


def test_validate_region_empty_config():
    """Verify secure default: if no regions are listed, all regions are denied."""
    # No list = Deny All (Secure default)
    with pytest.raises(SystemExit):
        guardrails.validate_region({}, "anywhere")


def test_sort_roles():
    """Verify that preferred roles are moved to the top of the list, followed by others alphabetically."""
    cfg = {"preferred_roles": ["Admin"]}
    roles = ["Viewer", "Admin", "Editor"]
    sorted_roles = guardrails.sort_roles(cfg, roles)
    # [FIX] Aligns with alphabetical sorting of the remainder
    assert sorted_roles == ["Admin", "Editor", "Viewer"]


def test_sort_roles_missing_preferred():
    """Verify that if preferred roles aren't present, the list is simply alphabetized."""
    cfg = {"preferred_roles": ["MissingRole"]}
    roles = ["B", "A"]
    sorted_roles = guardrails.sort_roles(cfg, roles)
    assert sorted_roles == ["A", "B"]


def test_check_min_version_pass(monkeypatch):
    """Verify that client passes when version is >= required."""
    monkeypatch.setattr("awsctl.guardrails.__version__", "2.0.0")
    # Config requires 1.0.0, current is 2.0.0 -> Pass
    guardrails.check_min_version({"min_client_version": "1.0.0"})


def test_check_min_version_fail(monkeypatch, mock_rich_console):
    """Verify that an outdated client triggers a SystemExit and an update notice."""
    mock_rich_console.clear()
    monkeypatch.setattr("awsctl.guardrails.__version__", "1.0.0")

    # Config requires 2.0.0, current is 1.0.0 -> Fail
    with pytest.raises(SystemExit):
        guardrails.check_min_version({"min_client_version": "2.0.0"})

    out = "".join(mock_rich_console.captured)
    assert "UPDATE REQUIRED" in out


def test_check_break_glass_prompt(monkeypatch, mock_rich_console, tmp_path):
    """Verify that sensitive roles require a reason and log that reason to the audit log."""
    mock_rich_console.clear()
    audit_file = tmp_path / "audit.log"
    # [FIX] Point logic to the temporary audit file
    monkeypatch.setattr(guardrails, "AUDIT_LOG", audit_file)

    cfg = {"name": "prod", "sensitive_roles": ["Admin"]}

    # Mock Inquirer to return a reason string
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = "Fixing DB"
    monkeypatch.setattr("awsctl.guardrails.inquirer.text", lambda **k: mock_prompt)

    guardrails.check_break_glass(cfg, "Admin")

    # Verify log was actually created and written
    assert audit_file.exists()
    log_content = audit_file.read_text(encoding="utf-8")
    assert "ROLE=Admin" in log_content
    assert "REASON=Fixing DB" in log_content
    assert "SENSITIVE ROLE ACCESS" in "".join(mock_rich_console.captured)


def test_audit_log_created_with_0600_permissions(monkeypatch, tmp_path):
    """Audit log file must be created with 0600 permissions to prevent unauthorized access."""
    audit_file = tmp_path / "audit.log"
    monkeypatch.setattr(guardrails, "AUDIT_LOG", audit_file)

    guardrails._audit_log("prod", "Admin", "Testing permissions")

    assert audit_file.exists()
    mode = oct(audit_file.stat().st_mode)[-3:]
    assert mode == "600", f"Expected 0600 permissions on audit log, got {mode}"


def test_check_break_glass_abort(monkeypatch, mock_rich_console):
    """Verify that access is denied if the user cancels the 'reason' prompt."""
    mock_rich_console.clear()
    cfg = {"name": "prod", "sensitive_roles": ["Admin"]}

    mock_prompt = MagicMock()
    # Simulate user pressing Ctrl+C
    mock_prompt.execute.side_effect = KeyboardInterrupt
    monkeypatch.setattr("awsctl.guardrails.inquirer.text", lambda **k: mock_prompt)

    with pytest.raises(SystemExit):
        guardrails.check_break_glass(cfg, "Admin")

    assert "Access Aborted" in "".join(mock_rich_console.captured)
