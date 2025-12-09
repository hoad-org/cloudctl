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
    with patch("subprocess.Popen") as mock_popen:
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("ok", "")
        process_mock.returncode = 0
        mock_popen.return_value.__enter__.return_value = process_mock
        proc = utils.run(["echo", "hi"])
        assert proc.stdout == "ok"


def test_run_failure():
    with patch("subprocess.Popen") as mock_popen:
        process_mock = MagicMock()
        process_mock.communicate.return_value = ("", "fail")
        process_mock.returncode = 1
        mock_popen.return_value.__enter__.return_value = process_mock
        with pytest.raises(RuntimeError) as e:
            utils.run(["crash"])
        assert "fail" in str(e.value)


@pytest.mark.skipif(os.name == "nt", reason="Posix-only features (killpg)")
def test_run_new_session_kill(monkeypatch):
    """Test killpg is called for timeouts in new sessions."""
    # We can safely patch os.name here because we are skipping on Windows/NT
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(["cmd"], 1)
        proc.pid = 999
        mock_popen.return_value.__enter__.return_value = proc

        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=999):
                with pytest.raises(RuntimeError):
                    utils.run(["sleep"], timeout=0.1, capture=True)
                mock_killpg.assert_called_with(999, signal.SIGKILL)


def test_is_wsl(monkeypatch):
    uname_mock = MagicMock()
    uname_mock.release = "5.15.90.1-microsoft-standard-WSL2"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is True
    uname_mock.release = "generic"
    monkeypatch.setattr("platform.uname", lambda: uname_mock)
    assert utils.is_wsl() is False


def test_open_browser_wsl(monkeypatch):
    monkeypatch.setattr(utils, "is_wsl", lambda: True)
    with patch("shutil.which", side_effect=lambda x: "/bin/wslview" if x == "wslview" else None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            mock_run.assert_called_with(["wslview", "http://example.com"], check=True)

    with patch("shutil.which", return_value=None):
        with patch("subprocess.run") as mock_run:
            utils.open_browser("http://example.com")
            mock_run.assert_called_with(["explorer.exe", "http://example.com"], check=False)


def test_open_browser_native(monkeypatch):
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    with patch("webbrowser.open") as mock_web:
        utils.open_browser("http://example.com")
        mock_web.assert_called_with("http://example.com")


def test_open_browser_error(monkeypatch, mock_rich_console):
    monkeypatch.setattr(utils, "is_wsl", lambda: False)
    with patch("webbrowser.open", side_effect=Exception("Boom")):
        utils.open_browser("http://fail.com")
    assert "Could not open browser" in "".join(mock_rich_console.captured)


def test_print_kv_table(mock_rich_console):
    utils.print_kv_table("Title", {"Key": "Value"})
    out = "".join(mock_rich_console.captured)
    assert "Title" in out


def test_ensure_dir(tmp_path):
    d = tmp_path / "subdir"
    utils.ensure_dir(d)
    assert d.exists()


def test_debug_print(mock_rich_console):
    mock_rich_console.clear()
    utils.set_debug(True)
    utils.debug_print("test_debug")
    assert "test_debug" in "".join(mock_rich_console.captured)

    mock_rich_console.clear()
    utils.set_debug(False)
    utils.debug_print("hidden")
    assert "hidden" not in "".join(mock_rich_console.captured)


def test_force_stderr_lifecycle():
    with patch("os.isatty", return_value=False):
        with utils.ForceStderr() as fs:
            assert isinstance(fs, utils.ForceStderr)


def test_force_stderr_exceptions(monkeypatch):
    mock_stdout = MagicMock()
    mock_stdout.flush.side_effect = OSError
    monkeypatch.setattr(sys, "stdout", mock_stdout)
    with utils.ForceStderr():
        pass


def test_redact_cmd_mixed():
    cmd = ["cmd", "--access-token", "secret", "other"]
    out = utils._redact_cmd(cmd)
    assert "secret" not in out
    assert "[REDACTED]" in out
