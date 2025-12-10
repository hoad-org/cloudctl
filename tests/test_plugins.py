# file: tests/test_plugins.py
"""Tests for awsctl plugins."""

from concurrent.futures import TimeoutError
from unittest.mock import MagicMock, patch

import pytest

from awsctl import plugins
from awsctl.plugins import okta


# [FIX] Disable test mode so the plugin logic actually runs
@pytest.fixture(autouse=True)
def force_enable_plugin(monkeypatch):
    monkeypatch.delenv("AWSCTL_TEST_MODE", raising=False)


def test_okta_pre_login_success(mock_rich_console):
    with patch("requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})
    assert "SSO Endpoint reachable" in "".join(mock_rich_console.captured)


def test_plugin_security_block(mock_rich_console):
    with pytest.raises(SystemExit):
        plugins.load_plugins(["evil.plugin"])
    assert "Blocked illegal plugin" in "".join(mock_rich_console.captured)


def test_plugin_timeout(mock_rich_console):
    with patch("concurrent.futures.ThreadPoolExecutor.submit") as mock_submit:
        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError()
        mock_submit.return_value = mock_future
        mod = MagicMock()
        mod.hook = lambda: None
        with pytest.raises(SystemExit):
            plugins.call_hook([mod], "hook")
    assert "timed out" in "".join(mock_rich_console.captured)


def test_safe_exec_exception(mock_rich_console):
    def bad_hook():
        raise ValueError("Hook Fail")

    with pytest.raises(SystemExit):
        plugins._safe_exec(bad_hook)
    assert "Plugin hook failed" in "".join(mock_rich_console.captured)
