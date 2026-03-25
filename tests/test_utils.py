# file: tests/test_utils.py
"""Tests for awsctl.utils."""

import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from awsctl import utils


def test_run_success():
    """Test successful command execution."""
    # Since utils.py uses subprocess.run, we patch that instead of Popen
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        proc = utils.run(["echo", "hi"])
        assert proc["stdout"] == "ok"


def test_run_failure():
    """Test command execution failure raising RuntimeError."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", stderr="fail", returncode=1)
        with pytest.raises(RuntimeError) as e:
            utils.run(["crash"])
        # Ensure the error message contains the stderr output
        assert "fail" in str(e.value)


@pytest.mark.skipif(os.name == "nt", reason="Posix-only features (killpg)")
def test_run_new_session_kill(monkeypatch):
    """Test killpg is called for timeouts in new sessions."""
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 1)):
        with patch("os.killpg") as mock_killpg:
            # We use 0 because os.getpgid(0) is used in the implementation
            with patch("os.getpgid", return_value=999):
                with pytest.raises(RuntimeError) as e:
                    utils.run(["sleep"], timeout=0.1, capture=True)

                assert "timed out" in str(e.value).lower()
                mock_killpg.assert_called_with(999, signal.SIGKILL)


def test_is_wsl(monkeypatch):
    """Test WSL environment detection logic."""
    uname_mock = MagicMock()
    uname_mock.release = "5.15.90.1-microsoft-standard-WSL2"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is True

    uname_mock.release = "generic-linux-kernel"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is False


def test_open_browser_wsl(monkeypatch):
    """Test browser opening logic when inside WSL."""
    monkeypatch.setattr(utils, "is_wsl", lambda: True)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # Branch 1: wslview exists
    with patch(
        "shutil.which", side_effect=lambda x: "/bin/wslview" if x == "wslview" else None
    ):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            mock_run.assert_called_with(
                ["/bin/wslview", "http://example.com"], check=True
            )

    # Branch 2: wslview missing, fallback to explorer.exe
    with patch("shutil.which", return_value=None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            mock_run.assert_called_with(
                ["explorer.exe", "http://example.com"], check=False
            )


def test_open_browser_native(monkeypatch):
    """Test standard browser opening on non-WSL systems."""
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    with patch("webbrowser.open", return_value=True) as mock_web:
        utils.open_browser("http://example.com")
        mock_web.assert_called_with("http://example.com")


def test_open_browser_error(monkeypatch, mock_rich_console):
    """Test handling of browser opening exceptions."""
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    monkeypatch.setattr(utils, "is_headless", lambda: False)

    # If webbrowser.open returns False or raises, it should result in an exception
    with patch("webbrowser.open", side_effect=Exception("Boom")):
        with pytest.raises(Exception) as e:
            utils.open_browser("http://fail.com")
        assert "No Browser" in str(e.value) or "Boom" in str(e.value)


def test_print_kv_table(mock_rich_console):
    """Test rendering of the Key-Value table."""
    utils.print_kv_table("Title", {"Key": "Value"})
    out = "".join(mock_rich_console.captured)
    assert "Title" in out
    assert "Key" in out


def test_ensure_dir(tmp_path):
    """Test directory creation helper."""
    d = tmp_path / "subdir"
    utils.ensure_dir(d)
    assert d.exists()


def test_debug_print(mock_rich_console):
    """Test debug print behavior based on debug flag."""
    utils.set_debug(True)
    utils.debug_print("test_debug_msg")
    assert "DEBUG: test_debug_msg" in "".join(mock_rich_console.captured)

    mock_rich_console.clear()
    utils.set_debug(False)
    utils.debug_print("hidden_msg")
    assert "hidden_msg" not in "".join(mock_rich_console.captured)


def test_force_stderr_lifecycle():
    """Test the ForceStderr context manager structure."""
    with patch("os.isatty", return_value=False):
        with utils.ForceStderr() as fs:
            assert isinstance(fs, utils.ForceStderr)


def test_force_stderr_exceptions(monkeypatch):
    """Verify ForceStderr doesn't crash if stdout flush fails."""
    mock_stdout = MagicMock()
    mock_stdout.flush.side_effect = OSError
    monkeypatch.setattr(sys, "stdout", mock_stdout)
    with utils.ForceStderr():
        pass


def test_redact_cmd_mixed():
    """Verify that sensitive arguments are redacted from command lists."""
    cmd = ["cmd", "--access-token", "secret-value", "public-arg"]
    out = utils._redact_cmd(cmd)
    assert "secret-value" not in out
    assert "[REDACTED]" in out
    assert "public-arg" in out
