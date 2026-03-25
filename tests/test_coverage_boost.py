# file: tests/test_coverage_boost.py
"""
Supplemental tests to ensure >75% coverage on Windows.
These target logic paths that are OS-agnostic but missed by main suites.
"""

from unittest.mock import MagicMock, patch

from awsctl import core, doctor, utils


def test_login_force_flag(mock_rich_console, monkeypatch):
    """Cover the 'force=True' path in cmd_login."""
    # 1. Setup happy path for config
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "test", "sso_start_url": "u", "sso_region": "r"},
    )
    # Patch aws module directly as cmd_login calls it
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "p")
    monkeypatch.setattr("awsctl.aws._resolve_aws_cli", lambda: "aws")

    # 2. Mock successful execution
    # Implementation expects a dict return from utils.run
    monkeypatch.setattr(
        "awsctl.utils.run", lambda *a, **k: {"returncode": 0, "stdout": ""}
    )

    # 3. Mock token loading
    # cmd_login checks for an active token to verify login was successful
    monkeypatch.setattr(
        "awsctl.core.load_active_sso_token", lambda *a, **k: MagicMock()
    )

    # 4. Run with force=True (skips "Already logged in" check)
    # Command should return 0 (Success)
    assert core.cmd_login("test", force=True) == 0

    # 5. Verify the console reports success
    output = "".join(mock_rich_console.captured)
    assert "Successful" in output


def test_doctor_network_fail(mock_rich_console, monkeypatch):
    """Cover the failure branch in doctor network check."""
    # 1. Mock standard checks to pass
    monkeypatch.setattr("awsctl.doctor.check_permissions", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_aws_version", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_shell_integration", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_time_sync", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_tool", lambda x: (True, "ok"))

    # 2. Fail the network check specifically
    monkeypatch.setattr(
        "awsctl.doctor.check_network_ssl", lambda: (False, "Timeout Error")
    )

    # 3. Run diagnostics
    doctor.run_diagnostics()

    # 4. Verify capture includes the specific error message
    output = "".join(mock_rich_console.captured)
    assert "Timeout Error" in output
    assert "Issues detected" in output


def test_utils_run_capture_false(monkeypatch):
    """Cover the capture=False path in utils.run."""
    # The implementation uses subprocess.run, not Popen
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)

        # Run with capture=False
        utils.run(["echo", "hi"], capture=False)

        # Verify capture_output was False in the call kwargs
        args, kwargs = mock_run.call_args
        assert kwargs["capture_output"] is False
