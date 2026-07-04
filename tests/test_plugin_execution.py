# file: tests/test_plugin_execution.py
"""
Final coverage for Plugins logic.
"""

import pytest
from cloudctl import plugins


def test_call_hook_empty():
    """Ensure call_hook returns early for empty list."""
    # Logic should return an empty list when no modules are provided
    result = plugins.call_hook([], "hook")
    assert result == []


def test_safe_exec_exception(mock_rich_console):
    """Test exception inside hook execution wrapper."""
    # Ensure buffer is clean before starting
    mock_rich_console.clear()

    def bad_hook():
        raise ValueError("Hook Fail")

    # [FIX] safe_exec prints the error to console and exits with 1
    with pytest.raises(SystemExit) as e:
        plugins._safe_exec(bad_hook)

    assert e.value.code == 1

    # [FIX] Implementation uses console.print() which is captured by mock_rich_console
    captured_output = "".join(mock_rich_console.captured)
    assert "Plugin hook failed" in captured_output
    assert "Hook Fail" in captured_output


def test_call_hook_success():
    """Verify that call_hook successfully executes present methods."""

    class MockModule:
        def success_hook(self, *args, **kwargs):
            return "ok"

    module = MockModule()
    # Testing call_hook with a list of modules
    results = plugins.call_hook([module], "success_hook")
    assert results == ["ok"]
