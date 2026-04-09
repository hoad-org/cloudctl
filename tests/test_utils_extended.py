# file: tests/test_utils_extended.py
"""Coverage boost for awsctl.utils"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from awsctl import utils


def test_run_success():
    # [FIX] Implementation uses subprocess.run, so we patch that directly
    # for cleaner, more reliable assertion.
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        proc = utils.run(["echo", "hi"])
        assert proc["stdout"] == "ok"


def test_run_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="fail", returncode=1)
        with pytest.raises(RuntimeError) as e:
            utils.run(["crash"])
        assert "fail" in str(e.value)


def test_is_wsl(monkeypatch):
    # [FIX] Align with the specific platform check logic in utils.py
    uname_mock = MagicMock()
    uname_mock.release = "5.15.90.1-microsoft-standard-WSL2"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is True

    uname_mock.release = "5.15.0-generic"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is False


def test_open_browser_wsl(monkeypatch):
    monkeypatch.setattr(utils, "is_wsl", lambda: True)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # Test path 1: wslview found
    with patch(
        "shutil.which", side_effect=lambda x: "/bin/wslview" if x == "wslview" else None
    ):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            # In our implementation, we call with wslview if found
            mock_run.assert_called_with(
                ["/bin/wslview", "http://example.com"], check=True
            )

    # Test path 2: fallback to explorer.exe
    with patch("shutil.which", return_value=None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            mock_run.assert_called_with(
                ["explorer.exe", "http://example.com"], check=False
            )


def test_open_browser_native(monkeypatch):
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    with patch("webbrowser.open", return_value=True) as mock_web:
        utils.open_browser("http://example.com")
        mock_web.assert_called_with("http://example.com")


def test_open_browser_error(monkeypatch, mock_rich_console):
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # If webbrowser.open raises, the error should be caught and reported to console
    mock_rich_console.clear()
    with patch("webbrowser.open", side_effect=Exception("Boom")):
        utils.open_browser("http://fail.com")  # must not raise
    captured = "".join(mock_rich_console.captured)
    assert "Boom" in captured or "open failed" in captured


def test_print_kv_table(mock_rich_console):
    # Ensure clean state
    mock_rich_console.clear()
    utils.print_kv_table("Title", {"Key": "Value"})
    out = "".join(mock_rich_console.captured)
    assert "Title" in out
    assert "Key" in out
    assert "Value" in out


def test_ensure_dir(tmp_path):
    d = tmp_path / "subdir"
    utils.ensure_dir(d)
    assert d.exists()


def test_debug_print(monkeypatch, mock_rich_console):
    mock_rich_console.clear()
    # [FIX] Use monkeypatch for environment variables if debug check is env-based
    monkeypatch.setenv("AWSCTL_DEBUG", "1")
    utils.debug_print("test_debug")
    out = "".join(mock_rich_console.captured)
    assert "test_debug" in out

    mock_rich_console.clear()
    monkeypatch.setenv("AWSCTL_DEBUG", "0")
    utils.debug_print("hidden")
    out = "".join(mock_rich_console.captured)
    assert "hidden" not in out


def test_force_stderr_lifecycle():
    with patch("os.isatty", return_value=False):
        with utils.ForceStderr() as fs:
            assert isinstance(fs, utils.ForceStderr)


def test_force_stderr_exceptions(monkeypatch):
    # Ensure stdout flush errors are suppressed/handled within context manager
    mock_stdout = MagicMock()
    mock_stdout.flush.side_effect = OSError
    monkeypatch.setattr(sys, "stdout", mock_stdout)
    with utils.ForceStderr():
        pass


def test_redact_cmd_mixed():
    cmd = ["cmd", "--access-token", "secret", "other"]
    out = utils._redact_cmd(cmd)
    assert "secret" not in out
    # [FIX] Matches specific redaction token used in implementation
    assert "[REDACTED]" in out
