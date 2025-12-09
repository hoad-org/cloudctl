# file: tests/test_doctor.py
# SPDX-License-Identifier: MIT
"""
Tests for awsctl.doctor logic.
"""

from typing import Dict, Generator
from unittest.mock import MagicMock

import pytest
from _pytest.capture import CaptureFixture

from awsctl import doctor


@pytest.fixture
def mock_doctor_deps(monkeypatch) -> Generator[Dict[str, MagicMock], None, None]:
    """Mock external dependencies for doctor checks."""
    mocks = {}
    mocks["which"] = MagicMock()
    monkeypatch.setattr("shutil.which", mocks["which"])

    # Mock config loading
    monkeypatch.setattr("awsctl.config.load_orgs_config", lambda: {"orgs": [{"name": "demo"}]})

    # Mock WSL check
    monkeypatch.setattr("awsctl.utils.is_wsl", lambda: False)

    yield mocks


def test_check_tool_found(mock_doctor_deps) -> None:
    mock_doctor_deps["which"].return_value = "/bin/tool"
    ok, path = doctor.check_tool("tool")
    assert ok is True
    assert path == "/bin/tool"


def test_check_tool_missing(mock_doctor_deps) -> None:
    mock_doctor_deps["which"].return_value = None
    ok, path = doctor.check_tool("tool")
    assert ok is False
    assert "Not found" in path


def test_doctor_all_ok(mock_doctor_deps: Dict[str, MagicMock], capsys: CaptureFixture[str]) -> None:
    """Test doctor when all dependencies are found and checks pass."""
    # Tools found
    mock_doctor_deps["which"].side_effect = lambda x: f"/bin/{x}"

    # Run doctor
    rc = doctor.run_diagnostics(fix_path=False)

    out = "".join(capsys.readouterr())

    # Assert table headers exist (proving code ran)
    assert "System Health Check" in out
    assert "Configuration" in out
    assert "Binary: aws" in out
    assert "Everything looks good" in out
    assert rc == 0


def test_doctor_issues_found(mock_doctor_deps: Dict[str, MagicMock], capsys: CaptureFixture[str]) -> None:
    """Test doctor reporting issues."""
    # Missing binary
    mock_doctor_deps["which"].return_value = None

    # Config Fail
    def raise_err():
        raise Exception("Config Bad")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("awsctl.config.load_orgs_config", raise_err)

    # Run
    rc = doctor.run_diagnostics(fix_path=False)

    out = "".join(capsys.readouterr())

    assert "Issues detected" in out
    assert rc == 1
