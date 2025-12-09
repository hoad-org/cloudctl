# file: tests/test_shell.py
"""Tests for shell integration logic."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from awsctl import shell


def test_wrapper_injection(mock_home_path):
    rc = mock_home_path / ".zshrc"
    rc.touch()
    assert shell.inject_shell_function(rc) is True
    content = rc.read_text(encoding="utf-8")
    assert "AWSCTL SHELL INTEGRATION" in content
    assert shell.inject_shell_function(rc) is False


def test_detect_shell_profile(monkeypatch, mock_home_path):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert shell.detect_shell_profile() == mock_home_path / ".zshrc"

    monkeypatch.setenv("SHELL", "/bin/bash")
    (mock_home_path / ".bash_profile").touch()
    assert shell.detect_shell_profile() == mock_home_path / ".bash_profile"


def test_detect_shell_profile_fallbacks(monkeypatch, mock_home_path):
    monkeypatch.setenv("SHELL", "/bin/bash")
    for f in [".bash_profile", ".bashrc"]:
        p = mock_home_path / f
        if p.exists():
            p.unlink()

    (mock_home_path / ".profile").touch()
    assert shell.detect_shell_profile() == mock_home_path / ".profile"
    (mock_home_path / ".profile").unlink()
    assert shell.detect_shell_profile() == mock_home_path / ".bashrc"


@pytest.mark.skipif(os.name == "nt", reason="Sudo logic is Posix only")
def test_inject_shell_sudo_chown(monkeypatch, tmp_path):
    rc = tmp_path / ".bashrc"
    rc.touch()
    # Mock os.geteuid which might not exist on Windows
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setenv("SUDO_UID", "1000")
    monkeypatch.setenv("SUDO_GID", "1000")
    with patch("os.chown") as mock_chown:
        shell.inject_shell_function(rc)
        mock_chown.assert_called()


@pytest.mark.skipif(os.name == "nt", reason="Sudo logic is Posix only")
def test_inject_shell_no_sudo_uid(monkeypatch, tmp_path):
    rc = tmp_path / ".bashrc"
    rc.touch()
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    with patch("os.chown") as mock_chown:
        shell.inject_shell_function(rc)
        mock_chown.assert_not_called()


def test_shell_injection_failure(monkeypatch):
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: "rc")
    with patch("tempfile.mkstemp", side_effect=OSError("Disk Full")):
        with pytest.raises(OSError):
            shell.inject_shell_function(MagicMock())


def test_shell_injection_read_fail(monkeypatch, tmp_path):
    rc = tmp_path / ".rc"
    rc.touch()
    # Mock Read failure
    # We patch pathlib.Path.read_text.
    with patch.object(Path, "read_text", side_effect=FileNotFoundError):
        assert shell.inject_shell_function(rc) is True

    # [FIX] Explicit utf-8 encoding for Windows
    with open(rc, "r", encoding="utf-8") as f:
        assert "AWSCTL SHELL INTEGRATION" in f.read()
