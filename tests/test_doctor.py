# file: tests/test_doctor.py
"""Tests for doctor/diagnostics."""
from unittest.mock import MagicMock

from awsctl import doctor


def test_check_tool_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: "/bin/" + x)
    found, path = doctor.check_tool("git")
    assert found is True
    assert path == "/bin/git"


def test_check_tool_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: None)
    found, path = doctor.check_tool("git")
    assert found is False
    assert "Not found" in path


def test_doctor_success(monkeypatch):
    # Mock dependencies to exist
    monkeypatch.setattr("shutil.which", lambda x: "/bin/" + x)
    # Mock config to be valid
    monkeypatch.setattr(
        "awsctl.config.load_orgs_config", lambda: {"orgs": [{"name": "foo"}]}
    )
    # Mock WSL check
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)

    rc = doctor.run_diagnostics()
    assert rc == 0


def test_doctor_failure(monkeypatch):
    # Mock missing tool
    monkeypatch.setattr("shutil.which", lambda x: None)
    # Mock config failure
    monkeypatch.setattr(
        "awsctl.config.load_orgs_config",
        MagicMock(side_effect=Exception("Bad Config")),
    )

    rc = doctor.run_diagnostics()
    assert rc == 1
