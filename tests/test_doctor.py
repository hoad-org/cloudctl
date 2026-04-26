# file: tests/test_doctor.py
from unittest.mock import MagicMock

import pytest
from cloudctl import doctor


@pytest.fixture()
def mock_doctor_deps(monkeypatch):
    """
    Surgical mock of all doctor dependencies to ensure a predictable
    baseline for success/failure tests.
    """
    mocks = {}
    mocks["which"] = MagicMock()
    monkeypatch.setattr("shutil.which", mocks["which"])

    # Mock config to prevent actual filesystem reads
    monkeypatch.setattr(
        "cloudctl.config.load_orgs_config", lambda: {"orgs": [{"name": "demo"}]}
    )
    monkeypatch.setattr("cloudctl.config.load_raw_config", lambda: {})

    # Patch directly on the module object to ensure internal calls are intercepted
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)

    # All diagnostic checks must return a (bool, str) tuple per the project spec
    monkeypatch.setattr("cloudctl.doctor.check_aws_version", lambda: (True, "v2.0.0"))
    monkeypatch.setattr(
        "cloudctl.doctor.check_shell_integration", lambda: (True, "Present")
    )
    monkeypatch.setattr("cloudctl.doctor.check_permissions", lambda: (True, "User owned"))
    monkeypatch.setattr("cloudctl.doctor.check_time_sync", lambda: (True, "Synced"))
    monkeypatch.setattr("cloudctl.doctor.check_network_ssl", lambda: (True, "Reachable"))
    monkeypatch.setattr("cloudctl.doctor.check_wsl_performance", lambda: (True, "N/A"))

    return mocks


def test_check_tool_found(mock_doctor_deps):
    """Verify check_tool returns success when shutil finds the binary."""
    mock_doctor_deps["which"].return_value = "/bin/tool"
    # check_tool must return the tuple (True, path)
    ok, path = doctor.check_tool("tool")
    assert ok is True
    assert path == "/bin/tool"


def test_check_tool_missing(mock_doctor_deps):
    """Verify check_tool returns failure when binary is missing."""
    mock_doctor_deps["which"].return_value = None
    ok, path = doctor.check_tool("tool")
    assert ok is False
    assert "Not found" in path


def test_doctor_all_ok(mock_doctor_deps, mock_rich_console):
    """Test the 'Happy Path' where all system diagnostics pass."""
    # Ensure all required tools (aws, etc) are found
    mock_doctor_deps["which"].side_effect = lambda x: f"/bin/{x}"

    # fix_path=False matches the signature of the implementation
    rc = doctor.run_diagnostics(fix_path=None)
    out = "".join(mock_rich_console.captured)

    # Verify diagnostic section markers are present in output
    assert "System Health Check" in out
    assert "Configuration" in out
    assert "AWS CLI" in out
    assert "Shell Integration" in out
    assert "Everything looks good" in out
    assert rc == 0


def test_doctor_issues_found(mock_doctor_deps, mock_rich_console, monkeypatch):
    """Test that diagnostics report failure when a check fails."""
    # 1. Fail tool check
    mock_doctor_deps["which"].return_value = None

    # 2. Force a specific config error
    def fail_load():
        raise Exception("Config Bad")

    monkeypatch.setattr("cloudctl.config.load_orgs_config", fail_load)

    rc = doctor.run_diagnostics()
    out = "".join(mock_rich_console.captured)

    # 3. Assert failure reporting
    assert "Issues detected" in out
    assert rc == 1


# --- WSL Performance Tests (Coverage Boost) ---


def test_check_wsl_performance_not_wsl(monkeypatch):
    """Verify performance check returns N/A on non-WSL systems."""
    monkeypatch.setattr(doctor, "is_wsl", lambda: False)
    ok, msg = doctor.check_wsl_performance()
    assert ok is True
    assert "N/A" in msg


def test_check_wsl_performance_no_aws(monkeypatch):
    """Verify failure when AWS CLI is missing inside WSL."""
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    monkeypatch.setattr("shutil.which", lambda x: None)
    ok, msg = doctor.check_wsl_performance()
    assert ok is False
    assert "not found" in msg.lower()


def test_check_wsl_performance_windows_binary(monkeypatch):
    """Verify warning when WSL is using the Windows-native .exe binary."""
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    # Finding 'aws.exe' in /mnt/c is a common performance bottleneck in WSL
    monkeypatch.setattr(
        "shutil.which", lambda x: "/mnt/c/Program Files/Amazon/AWSCLIV2/aws.exe"
    )
    ok, msg = doctor.check_wsl_performance()
    assert ok is False
    assert "Windows binary" in msg


def test_check_wsl_performance_native_binary(monkeypatch):
    """Verify success when WSL is using a native Linux AWS binary."""
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/aws")
    ok, msg = doctor.check_wsl_performance()
    assert ok is True
    assert "Native" in msg


def test_run_diagnostics_wsl_warning(mock_doctor_deps, mock_rich_console, monkeypatch):
    """Test that diagnostics include the specific WSL warning string."""
    # 1. Force WSL environment
    monkeypatch.setattr(doctor, "is_wsl", lambda: True)

    # 2. Force the performance check to return an issue
    monkeypatch.setattr(
        "cloudctl.doctor.check_wsl_performance",
        lambda: (False, "using the Windows AWS CLI"),
    )

    doctor.run_diagnostics()
    out = "".join(mock_rich_console.captured)

    # 3. Verify specifically requested warning markers
    assert "WSL Performance" in out
    assert "using the Windows AWS CLI" in out
