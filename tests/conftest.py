# file: tests/conftest.py
"""
Shared pytest configuration and mocks for awsctl test suite.
"""
import io
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console


class MockConsole:
    """
    A wrapper around rich.console.Console that captures output to a buffer.
    Delegates rendering to Rich so tables/panels are formatted to string correctly.
    """

    def __init__(self):
        self.file = io.StringIO()
        # force_terminal=False removes ANSI codes, width=1000 prevents line wrapping
        self.real_console = Console(file=self.file, force_terminal=False, width=1000)
        self.captured = []

    def print(self, *args: Any, **kwargs: Any) -> None:
        self.real_console.print(*args, **kwargs)
        self._sync()

    def print_json(self, data: Any = None) -> None:
        self.real_console.print_json(data=data)
        self._sync()

    def status(self, *args: Any, **kwargs: Any) -> MagicMock:
        cm = MagicMock()
        cm.__enter__.return_value = None
        return cm

    def clear(self) -> None:
        self.file.truncate(0)
        self.file.seek(0)
        self.captured = []

    def _sync(self):
        # Update captured list with the full buffer content as a single string
        # This makes assertions like 'assert "Error" in "".join(captured)' work
        self.captured = [self.file.getvalue()]


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch):
    """
    Prevent hitting real system commands.
    Returns a new mock for every Popen call to allow multiple executions.
    """
    # Mock subprocess.run
    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=["cmd"], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", mock_run)

    # Mock subprocess.Popen to return a FRESH process mock every time
    mock_popen = MagicMock()

    def side_effect(*args, **kwargs):
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("", "")
        process_mock.returncode = 0
        # poll() returns None (running) once, then 0 (done)
        process_mock.poll.side_effect = [None, 0]

        # Context manager support
        cm_mock = MagicMock()
        cm_mock.__enter__.return_value = process_mock
        cm_mock.__exit__.return_value = None
        return cm_mock

    mock_popen.side_effect = side_effect
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    yield mock_run


@pytest.fixture(autouse=True)
def mock_rich_console(monkeypatch):
    """
    Inject the MockConsole globally.
    We must patch every module that imports 'console' to ensure they use the mock.
    """
    dummy_console = MockConsole()

    targets = [
        "awsctl.utils.console",
        "awsctl.cli.console",
        "awsctl.core.console",
        "awsctl.interactive.console",
        "awsctl.cli_accounts.console",
        # Critical: Patch modules that might have already imported console
        "awsctl.guardrails.console",
        "awsctl.plugins.okta.console",
    ]

    for t in targets:
        monkeypatch.setattr(t, dummy_console, raising=False)

    return dummy_console


@pytest.fixture(autouse=True)
def mock_browser(monkeypatch):
    """Prevent tests from opening real browser windows."""
    monkeypatch.setattr("webbrowser.open", MagicMock())
