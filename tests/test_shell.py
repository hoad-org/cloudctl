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
    # [FIX] Enforce UTF-8 for cross-platform stability
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
    with patch.object(Path, "read_text", side_effect=FileNotFoundError):
        assert shell.inject_shell_function(rc) is True

    # [FIX] Explicit utf-8 encoding for Windows
    with open(rc, "r", encoding="utf-8") as f:
        assert "AWSCTL SHELL INTEGRATION" in f.read()


# --- New Tests for Full Coverage ---


def test_inject_shell_newline_insertion(tmp_path):
    """Ensure newline is added if file doesn't end with one."""
    rc = tmp_path / "rc_no_newline"
    # [FIX] Use UTF-8 explicitly
    rc.write_text("content_without_newline", encoding="utf-8")

    shell.inject_shell_function(rc)

    content = rc.read_text(encoding="utf-8")
    # The logic adds a newline if missing, plus a spacer newline, plus the wrapper
    assert "content_without_newline\n\n\n# AWSCTL SHELL INTEGRATION" in content


# [FIX] Skip on Windows as chmod behavior varies
@pytest.mark.skipif(os.name == "nt", reason="Permission preservation varies on Windows")
def test_inject_shell_permission_preservation(tmp_path, monkeypatch):
    """Ensure permissions are copied from original file."""
    rc = tmp_path / "rc_perms"
    rc.touch()

    # Mock stat to return specific mode
    mock_stat = MagicMock()
    mock_stat.st_mode = 0o777

    monkeypatch.setattr("pathlib.Path.stat", lambda self, *args, **kwargs: mock_stat)

    with patch("os.chmod") as mock_chmod:
        shell.inject_shell_function(rc)
        assert mock_chmod.called
        assert mock_chmod.call_args[0][1] == 0o777


def test_inject_shell_chmod_fallback(tmp_path, monkeypatch):
    """Ensure we fallback to 644 if chmod fails."""
    rc = tmp_path / "rc_perms_fail"
    rc.touch()

    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    # Mock stat to raise OSError when called
    monkeypatch.setattr("pathlib.Path.stat", MagicMock(side_effect=OSError))

    with patch("os.chmod") as mock_chmod:
        shell.inject_shell_function(rc)
        # Should be called with 0o644 default (decimal 420)
        assert mock_chmod.call_args[0][1] == 0o644


def test_remove_shell_function_file_missing(tmp_path):
    """Return False if file doesn't exist."""
    rc = tmp_path / "missing_rc"
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_read_error(monkeypatch, tmp_path):
    """Return False on read error."""
    rc = tmp_path / "readable_rc"
    rc.touch()
    with patch.object(Path, "read_text", side_effect=Exception("Read Error")):
        assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_not_present(tmp_path):
    """Return False if wrapper not in file."""
    rc = tmp_path / "clean_rc"
    rc.write_text("some content", encoding="utf-8")
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_dirty_removal(tmp_path):
    """Fail if simple string removal leaves artifacts (dirty edit)."""
    rc = tmp_path / "dirty_rc"

    dirty_content = shell.AWSCTL_WRAPPER.replace(
        "awsctl() {", "awsctl() {\n    # User modified this line"
    )

    rc.write_text(dirty_content, encoding="utf-8")

    # Should detect it (returns True for "contains") but fail to remove it clean
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_success(tmp_path):
    """Clean removal success."""
    rc = tmp_path / "valid_rc"
    rc.write_text(shell.AWSCTL_WRAPPER, encoding="utf-8")
    assert shell.remove_shell_function(rc) is True
    assert rc.read_text(encoding="utf-8") == ""
