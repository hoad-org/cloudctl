# file: tests/test_plugins.py
"""Tests for cloudctl plugins."""

from concurrent.futures import TimeoutError
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import plugins
from cloudctl.plugins import okta


# [FIX] Ensure plugin logic actually runs by disabling test mode
@pytest.fixture(autouse=True)
def force_enable_plugin(monkeypatch):
    monkeypatch.delenv("AWSCTL_TEST_MODE", raising=False)


def test_okta_pre_login_success(mock_rich_console):
    """Verify Okta plugin reports reachability to stdout."""
    # We patch requests.head as the plugin uses it for a health check
    with patch("requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        okta.pre_login({"name": "test", "sso_start_url": "https://okta.com"})

    # [FIX] Okta plugin writes to stdout for shell visibility
    # Combined captured handles both stdout/stderr for parity
    output = "".join(mock_rich_console.captured)
    assert "SSO Endpoint reachable" in output


def test_plugin_security_block(mock_rich_console):
    """Verify that 'evil' plugins are blocked and reported to stderr."""
    with pytest.raises(SystemExit):
        plugins.load_plugins(["evil.plugin"])

    # [FIX] Security blocks go to stderr (console)
    assert "Blocked illegal plugin" in "".join(mock_rich_console.captured)


def test_plugin_timeout(mock_rich_console, capsys):
    """Verify that plugin timeouts result in a specific stdout marker."""
    with patch("concurrent.futures.ThreadPoolExecutor.submit") as mock_submit:
        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError()
        mock_submit.return_value = mock_future

        mod = MagicMock()
        mod.hook = lambda: None

        with pytest.raises(SystemExit):
            plugins.call_hook([mod], "hook")

    # [FIX] Timeouts are written to raw stdout for the shell wrapper bridge
    # but captured by our unified mock_rich_console
    assert "timed out" in "".join(mock_rich_console.captured)


def test_safe_exec_exception(mock_rich_console):
    """Verify that plugin hook exceptions are caught and reported."""

    def bad_hook():
        raise ValueError("Hook Fail")

    with pytest.raises(SystemExit):
        plugins._safe_exec(bad_hook)

    # [FIX] Plugin hook failures are reported to stderr via the console
    output = "".join(mock_rich_console.captured)
    assert "Plugin hook failed" in output
    assert "Hook Fail" in output
