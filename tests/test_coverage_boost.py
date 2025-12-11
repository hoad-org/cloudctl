# file: tests/test_coverage_boost.py
"""
Supplemental tests to ensure >75% coverage on Windows.
These target logic paths that are OS-agnostic but missed by main suites.
"""

from unittest.mock import MagicMock, patch

from awsctl import core, doctor, utils


def test_login_force_flag(mock_rich_console, monkeypatch):
    """Cover the 'force=True' path in cmd_login."""
    # Setup happy path for config
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "test", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "p")
    # Mock resolved binary to avoid windows issues
    monkeypatch.setattr("awsctl.aws._resolve_aws_cli", lambda: "aws")

    # Mock run success
    monkeypatch.setattr("awsctl.utils.run", MagicMock())

    # Mock successful token load AFTER login
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: "token")

    # Run with force=True (skips "Already logged in" check)
    assert core.cmd_login("test", force=True) == 0
    assert "Login Successful" in "".join(mock_rich_console.captured)


def test_doctor_network_fail(mock_rich_console, monkeypatch):
    """Cover the failure branch in doctor network check."""
    # Mock everything to pass EXCEPT network
    monkeypatch.setattr("awsctl.doctor.check_permissions", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_aws_version", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_shell_integration", lambda: (True, "ok"))
    monkeypatch.setattr("awsctl.doctor.check_time_sync", lambda: (True, "ok"))

    # Fail network
    monkeypatch.setattr("awsctl.doctor.check_network_ssl", lambda: (False, "Timeout"))

    # Run (ignore return code to avoid unused variable linter error)
    doctor.run_diagnostics(fix_path=False)

    # We just need to ensure the failure path logged the error
    assert "Timeout" in "".join(mock_rich_console.captured)


def test_utils_run_capture_false(monkeypatch):
    """Cover the capture=False path in utils.run."""
    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.return_value = ("stdout", "stderr")
        proc.returncode = 0
        mock_popen.return_value.__enter__.return_value = proc

        # Run with capture=False
        utils.run(["echo", "hi"], capture=False)

        # Verify stderr was NOT piped
        kwargs = mock_popen.call_args[1]
        assert kwargs["stderr"] is None
