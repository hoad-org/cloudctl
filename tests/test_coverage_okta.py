# file: tests/test_coverage_okta.py
"""
Final coverage boost for Okta plugin.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from awsctl.plugins import okta


def test_okta_missing_url(mock_rich_console):
    okta.pre_login({"name": "test"})
    assert "missing" in "".join(mock_rich_console.captured)


def test_okta_insecure_url(mock_rich_console):
    with pytest.raises(SystemExit):
        okta.pre_login({"name": "test", "sso_start_url": "http://insecure.com"})
    assert "Security Risk" in "".join(mock_rich_console.captured)


def test_okta_connection_error(mock_rich_console):
    with patch("requests.head", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})
    assert "Connection Failed" in "".join(mock_rich_console.captured)


def test_okta_timeout(mock_rich_console):
    with patch("requests.head", side_effect=requests.exceptions.Timeout):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})
    assert "Timed Out" in "".join(mock_rich_console.captured)


def test_okta_http_error(mock_rich_console):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.head", return_value=mock_resp):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})
    assert "returned error 403" in "".join(mock_rich_console.captured)


def test_okta_generic_exception(mock_rich_console):
    with patch("requests.head", side_effect=Exception("Boom")):
        with pytest.raises(SystemExit):
            okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})
    assert "Unexpected error" in "".join(mock_rich_console.captured)
