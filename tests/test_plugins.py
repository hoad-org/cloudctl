# file: tests/test_plugins.py
"""
Tests for awsctl plugins.
"""
from unittest.mock import patch

import pytest
import requests

from awsctl.plugins import okta


def test_okta_pre_login_success(mock_rich_console):
    org = {"name": "test", "sso_start_url": "https://okta.example.com"}

    # Mock successful request
    with patch("requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        okta.pre_login(org)

    # Check mock console
    out = "".join(mock_rich_console.captured)
    assert "SSO Endpoint reachable" in out


def test_okta_pre_login_missing_url(mock_rich_console):
    okta.pre_login({"name": "test"})

    out = "".join(mock_rich_console.captured)
    assert "missing" in out


def test_okta_connection_error(mock_rich_console):
    org = {"name": "test", "sso_start_url": "https://bad.url"}

    with patch("requests.head", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(SystemExit) as e:
            okta.pre_login(org)
        assert e.value.code == 1

    out = "".join(mock_rich_console.captured)
    assert "Connection Failed" in out


def test_okta_timeout(mock_rich_console):
    org = {"name": "test", "sso_start_url": "https://slow.url"}

    with patch("requests.head", side_effect=requests.exceptions.Timeout):
        with pytest.raises(SystemExit) as e:
            okta.pre_login(org)
        assert e.value.code == 1

    out = "".join(mock_rich_console.captured)
    assert "Timed Out" in out
