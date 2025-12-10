# file: tests/test_doctor.py
from unittest.mock import MagicMock

import pytest

from awsctl import doctor


@pytest.fixture
def mock_doctor_deps(monkeypatch):
    mocks = {}
    mocks["which"] = MagicMock()
    monkeypatch.setattr("shutil.which", mocks["which"])
    monkeypatch.setattr(
        "awsctl.config.load_orgs_config", lambda: {"orgs": [{"name": "demo"}]}
    )
    # Patch directly on the module object to ensure it takes effect
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)

    # Mock new checks to guarantee success path
    monkeypatch.setattr("awsctl.doctor.check_aws_version", lambda: (True, "v2.0.0"))
    monkeypatch.setattr(
        "awsctl.doctor.check_shell_integration", lambda: (True, "Present")
    )
    monkeypatch.setattr("awsctl.doctor.check_permissions", lambda: (True, "User owned"))
    monkeypatch.setattr("awsctl.doctor.check_time_sync", lambda: (True, "Synced"))
    monkeypatch.setattr("awsctl.doctor.check_network_ssl", lambda: (True, "Reachable"))

    # Mock WSL check default to avoid side effects
    monkeypatch.setattr("awsctl.doctor.check_wsl_performance", lambda: (True, "N/A"))

    return mocks


def test_check_tool_found(mock_doctor_deps):
    mock_doctor_deps["which"].return_value = "/bin/tool"
    ok, path = doctor.check_tool("tool")
    assert ok is True
    assert path == "/bin/tool"


def test_check_tool_missing(mock_doctor_deps):
    mock_doctor_deps["which"].return_value = None
    ok, path = doctor.check_tool("tool")
    assert ok is False
    assert "Not found" in path


def test_doctor_all_ok(mock_doctor_deps, mock_rich_console):
    # Ensure tools are found
    mock_doctor_deps["which"].side_effect = lambda x: f"/bin/{x}"

    rc = doctor.run_diagnostics(fix_path=False)
    out = "".join(mock_rich_console.captured)

    # Assert key components are visible
    assert "System Health Check" in out
    assert "Configuration" in out
    assert "AWS CLI" in out
    assert "Shell Integration" in out
    assert "Everything looks good" in out
    assert rc == 0


def test_doctor_issues_found(mock_doctor_deps, mock_rich_console, monkeypatch):
    # Fail tool check
    mock_doctor_deps["which"].return_value = None

    # Force config error
    def fail_load():
        raise Exception("Config Bad")

    monkeypatch.setattr("awsctl.config.load_orgs_config", fail_load)

    rc = doctor.run_diagnostics(fix_path=False)
    out = "".join(mock_rich_console.captured)

    assert "Issues detected" in out
    assert rc == 1


# --- WSL Performance Tests (Coverage Boost) ---


def test_check_wsl_performance_not_wsl(monkeypatch):
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)
    ok, msg = doctor.check_wsl_performance()
    assert ok is True
    assert "N/A" in msg


def test_check_wsl_performance_no_aws(monkeypatch):
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    monkeypatch.setattr("shutil.which", lambda x: None)
    ok, msg = doctor.check_wsl_performance()
    assert ok is False
    assert "not found" in msg


def test_check_wsl_performance_windows_binary(monkeypatch):
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    # Simulate finding aws.exe via WSL interop
    monkeypatch.setattr(
        "shutil.which", lambda x: "/mnt/c/Program Files/Amazon/AWSCLIV2/aws.exe"
    )
    ok, msg = doctor.check_wsl_performance()
    assert ok is False
    assert "Windows binary" in msg


def test_check_wsl_performance_native_binary(monkeypatch):
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/aws")
    ok, msg = doctor.check_wsl_performance()
    assert ok is True
    assert "Native" in msg


def test_run_diagnostics_wsl_warning(mock_doctor_deps, mock_rich_console, monkeypatch):
    """Test that the WSL warning is printed when issues are found."""
    # Force WSL env
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)

    # Force the check to fail
    monkeypatch.setattr("awsctl.doctor.check_wsl_performance", lambda: (False, "Slow"))

    doctor.run_diagnostics(fix_path=False)
    out = "".join(mock_rich_console.captured)

    assert "WSL Performance" in out
    # [FIX] Corrected case sensitivity ("Using" -> "using")
    assert "using the Windows AWS CLI" in out
