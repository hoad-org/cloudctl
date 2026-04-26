from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console


@pytest.fixture(autouse=True)
def mock_home(tmp_path, monkeypatch):
    """Sets up a hermetic home directory for every test."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    # Critical: Mock both the env var and Path.home() if used in source
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # For Windows parity

    # Pre-create required directory structures
    (home / ".cloudctl").mkdir(exist_ok=True)
    (home / ".aws" / "sso" / "cache").mkdir(parents=True, exist_ok=True)

    # Global browser mock to prevent tests from launching real windows
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", MagicMock(return_value=True))

    return home


@pytest.fixture
def mock_rich_console(monkeypatch):
    """
    Unified console capture fixture.
    It replaces the real Rich console with one that records to a buffer.
    """

    class CapturedConsole:
        def __init__(self):
            self.buffer = StringIO()
            # We create a REAL Rich Console but point it at our buffer
            self.console = Console(
                file=self.buffer, force_terminal=False, width=100, color_system=None
            )

        @property
        def captured(self):
            """Returns a list of strings, split by actual output to match test expectations."""
            val = self.buffer.getvalue()
            return [val] if val else []

        def print(self, *args, **kwargs):
            """Proxy to the real Rich console print method."""
            self.console.print(*args, **kwargs)

        def clear(self):
            """Wipes the buffer for the next assertion."""
            self.buffer.truncate(0)
            self.buffer.seek(0)

    cap = CapturedConsole()

    # We must patch the utils module where the consoles are defined
    import cloudctl.utils

    # Replace the Rich Console instances with our capture object
    # Note: We patch the attributes that the code actually calls
    monkeypatch.setattr(cloudctl.utils, "console", cap.console)
    monkeypatch.setattr(cloudctl.utils, "stdout_console", cap.console)

    # We return the 'cap' wrapper so tests can call .clear() or check .captured
    return cap
