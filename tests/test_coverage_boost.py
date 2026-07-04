# file: tests/test_coverage_boost.py
"""
Supplemental tests to ensure >75% coverage on Windows.
These target logic paths that are OS-agnostic but missed by main suites.
"""

from unittest.mock import MagicMock, patch

from cloudctl import core, doctor, utils


def test_login_force_flag(mock_rich_console, monkeypatch):
    """Cover the 'force=True' path in cmd_login.

    login is now a boto3 SSO OIDC device-authorization flow, so we mock the
    sso-oidc client to return a token immediately rather than mocking the old
    ensure_sso_base_profile + `aws sso login` shell-out.
    """
    # 1. Setup happy path for config
    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda x: {"name": "test", "sso_start_url": "https://x/start", "sso_region": "r"},
    )

    # 2. Mock the boto3 sso-oidc client for an immediate-success device flow.
    oidc = MagicMock()
    oidc.register_client.return_value = {"clientId": "cid", "clientSecret": "csec"}
    oidc.start_device_authorization.return_value = {
        "deviceCode": "dev",
        "userCode": "USER-CODE",
        "verificationUriComplete": "https://x/verify?code=USER-CODE",
        "interval": 0,
        "expiresIn": 600,
    }
    oidc.create_token.return_value = {"accessToken": "AT", "expiresIn": 3600}
    monkeypatch.setattr("boto3.client", lambda *a, **k: oidc)
    monkeypatch.setattr("cloudctl.utils.open_browser", lambda url: None)

    # 3. Mock token loading (cmd_login re-reads to confirm — not required but
    # harmless).
    monkeypatch.setattr(
        "cloudctl.core.load_active_sso_token", lambda *a, **k: MagicMock()
    )

    # 4. Run with force=True (skips "Already logged in" check)
    assert core.cmd_login("test", force=True) == 0

    # 5. Verify the console reports success
    output = "".join(mock_rich_console.captured)
    assert "Successful" in output


def test_doctor_network_fail(mock_rich_console, monkeypatch):
    """Cover the failure branch in doctor network check."""
    # 1. Mock standard checks to pass
    monkeypatch.setattr("cloudctl.doctor.check_permissions", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_aws_version", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_shell_integration", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_time_sync", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_tool", lambda x: (True, "ok"))

    # 2. Fail the network check specifically
    monkeypatch.setattr(
        "cloudctl.doctor.check_network_ssl", lambda: (False, "Timeout Error")
    )

    # 3. Run diagnostics (force table mode: under pytest stdout is not a TTY,
    #    so the default would resolve to the JSON summary instead of the table).
    doctor.run_diagnostics(fmt="table")

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
