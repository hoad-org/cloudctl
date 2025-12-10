# file: tests/conftest.py
"""
Shared pytest configuration and mocks for awsctl test suite.
"""

import io
import os
import pathlib
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console

# [FIX] Disable security hardening (TTY checks, Stream swapping) during tests.
os.environ["AWSCTL_TEST_MODE"] = "1"


class MockConsole:
    """
    A wrapper around rich.console.Console that captures output to a buffer.
    """

    def __init__(self):
        self.file = io.StringIO()
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
        self.captured = [self.file.getvalue()]


# [PATCH FIX]: Mocks Path.home() to point to the isolated temp directory.
@pytest.fixture(autouse=True)
def mock_home_path(monkeypatch, tmp_path):
    mock_isolated_home = tmp_path / "mocked_home"
    mock_isolated_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: mock_isolated_home)
    monkeypatch.setenv("HOME", str(mock_isolated_home))
    return mock_isolated_home


@pytest.fixture(autouse=True)
def no_real_subprocess(monkeypatch):
    """
    Prevent hitting real system commands.
    """
    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=["cmd"], returncode=0, stdout="", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", mock_run)

    mock_popen = MagicMock()

    def side_effect(*args, **kwargs):
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("", "")
        process_mock.returncode = 0
        process_mock.poll.side_effect = [None, 0]
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
    Inject the MockConsole globally for STDERR logs (errors, warnings, status).
    """
    dummy_console = MockConsole()

    targets = [
        "awsctl.utils.console",
        "awsctl.cli.console",
        "awsctl.core.console",
        "awsctl.config.console",
        "awsctl.interactive.console",
        "awsctl.cli_accounts.console",
        "awsctl.guardrails.console",
        "awsctl.plugins.okta.console",
        "awsctl.plugins.console",
        "awsctl.registry_loader.console",
        "awsctl.wizard.console",
        # [FIX] Patch doctor.console so output is captured in tests
        "awsctl.doctor.console",
        "awsctl.utils.stdout_console",
        "awsctl.cli.stdout_console",
        "awsctl.cli_accounts.stdout_console",
        "awsctl.core.stdout_console",
    ]

    for t in targets:
        monkeypatch.setattr(t, dummy_console, raising=False)

    return dummy_console


@pytest.fixture(autouse=True)
def mock_browser(monkeypatch):
    monkeypatch.setattr("webbrowser.open", MagicMock())
