# file: tests/test_plugin_execution.py
"""
Final coverage for Plugins logic.
"""

import pytest

from awsctl import plugins


def test_call_hook_empty():
    """Ensure call_hook returns early for empty list."""
    plugins.call_hook([], "hook")


def test_safe_exec_exception(mock_rich_console):
    """Test exception inside hook execution wrapper."""

    def bad_hook():
        raise ValueError("Hook Fail")

    with pytest.raises(SystemExit):
        plugins._safe_exec(bad_hook)

    assert "Plugin hook failed" in "".join(mock_rich_console.captured)
