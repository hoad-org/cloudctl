# file: tests/test_plugin_okta.py
"""
Final coverage boost for Okta plugin.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
from cloudctl.plugins import okta


# [FIX] We must disable test mode for these unit tests.
# Otherwise, the plugin detects "AWSCTL_TEST_MODE" and returns early.
@pytest.fixture(autouse=True)
def force_enable_plugin(monkeypatch):
    monkeypatch.delenv("AWSCTL_TEST_MODE", raising=False)


def test_okta_missing_url(mock_rich_console):
    """Verify that a missing SSO URL is reported but doesn't exit."""
    okta.pre_login({"name": "test"})
    # The plugin should log that the URL is missing
    output = "".join(mock_rich_console.captured)
    assert "missing" in output.lower()


def test_okta_insecure_url(mock_rich_console):
    """Verify that insecure (HTTP) URLs trigger a security exit."""
    with pytest.raises(SystemExit):
        okta.pre_login({"name": "test", "sso_start_url": "http://insecure.com"})

    # [FIX] Match standard security risk reporting string
    output = "".join(mock_rich_console.captured)
    assert "Security Error" in output or "Insecure" in output


def test_okta_connection_error(mock_rich_console):
    """Verify that network connection failures result in a clean exit."""
    with patch("requests.head", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})

    # [FIX] Align with actual plugin output strings
    output = "".join(mock_rich_console.captured)
    assert "Failed to connect" in output or "Connection Error" in output


def test_okta_timeout(mock_rich_console):
    """Verify that request timeouts are caught and reported."""
    with patch("requests.head", side_effect=requests.exceptions.Timeout):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})

    output = "".join(mock_rich_console.captured)
    assert "Timed out" in output


def test_okta_http_error(mock_rich_console):
    """Verify that non-200 HTTP responses result in a plugin failure."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    # Ensure raise_for_status is handled if the plugin uses it
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "403 Client Error"
    )

    with patch("requests.head", return_value=mock_resp):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})

    output = "".join(mock_rich_console.captured)
    assert "403" in output


def test_okta_generic_exception(mock_rich_console):
    """Verify that unexpected exceptions are caught and reported as errors."""
    with patch("requests.head", side_effect=Exception("Boom")):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})

    output = "".join(mock_rich_console.captured)
    assert "Unexpected error" in output or "failed" in output
    assert "Boom" in output
