# file: tests/test_shell.py
"""Tests for shell integration logic."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from awsctl import shell

# [FIX] Align fixture name with conftest.py (mock_home instead of mock_home_path)


def test_wrapper_injection(mock_home):
    rc = mock_home / ".zshrc"
    rc.touch()
    assert shell.inject_shell_function(rc) is True
    # [FIX] Enforce UTF-8 for cross-platform stability
    content = rc.read_text(encoding="utf-8")
    assert "AWSCTL SHELL INTEGRATION" in content
    # Second injection should return False (already present)
    assert shell.inject_shell_function(rc) is False


def test_detect_shell_profile(monkeypatch, mock_home):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert shell.detect_shell_profile() == mock_home / ".zshrc"

    monkeypatch.setenv("SHELL", "/bin/bash")
    (mock_home / ".bash_profile").touch()
    assert shell.detect_shell_profile() == mock_home / ".bash_profile"


def test_detect_shell_profile_fallbacks(monkeypatch, mock_home):
    monkeypatch.setenv("SHELL", "/bin/bash")
    # Clean up existing files
    for f in [".bash_profile", ".bashrc", ".profile"]:
        p = mock_home / f
        if p.exists():
            p.unlink()

    (mock_home / ".profile").touch()
    assert shell.detect_shell_profile() == mock_home / ".profile"
    (mock_home / ".profile").unlink()
    # If no files exist, default to .bashrc
    assert shell.detect_shell_profile() == mock_home / ".bashrc"


@pytest.mark.skipif(os.name == "nt", reason="Sudo logic is Posix only")
def test_inject_shell_no_sudo_uid(monkeypatch, tmp_path):
    rc = tmp_path / ".bashrc"
    rc.touch()
    # raising=False prevents error if geteuid doesn't exist on system
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    with patch("os.chown") as mock_chown:
        shell.inject_shell_function(rc)
        mock_chown.assert_not_called()


def test_shell_injection_failure(monkeypatch):
    # Ensure it raises OSError when the filesystem is "full" (mkstemp fails)
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: Path("rc"))
    with patch("tempfile.mkstemp", side_effect=OSError("Disk Full")):
        with pytest.raises(OSError):
            shell.inject_shell_function(Path("some_path"))


def test_shell_injection_read_fail(monkeypatch, tmp_path):
    rc = tmp_path / ".rc"
    rc.touch()
    # If read fails, the implementation should still try to append (force overwrite safety)
    with patch.object(Path, "read_text", side_effect=FileNotFoundError):
        assert shell.inject_shell_function(rc) is True

    assert "AWSCTL SHELL INTEGRATION" in rc.read_text(encoding="utf-8")


def test_inject_shell_newline_insertion(tmp_path):
    """Ensure newline is added if file doesn't end with one."""
    rc = tmp_path / "rc_no_newline"
    rc.write_text("existing_content", encoding="utf-8")

    shell.inject_shell_function(rc)

    content = rc.read_text(encoding="utf-8")
    # Should have: existing + \n + \n + spacer + wrapper
    assert "existing_content\n\n\n# AWSCTL SHELL INTEGRATION" in content


@pytest.mark.skipif(os.name == "nt", reason="Permission preservation varies on Windows")
def test_inject_shell_permission_preservation(tmp_path, monkeypatch):
    rc = tmp_path / "rc_perms"
    rc.touch()

    mock_stat = MagicMock()
    mock_stat.st_mode = 0o777
    # Use patch.object for more reliable Path.stat mocking
    with patch.object(Path, "stat", return_value=mock_stat):
        with patch("os.chmod") as mock_chmod:
            shell.inject_shell_function(rc)
            assert mock_chmod.called
            assert mock_chmod.call_args[0][1] == 0o777


def test_remove_shell_function_file_missing(tmp_path):
    rc = tmp_path / "missing_rc"
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_read_error(tmp_path):
    rc = tmp_path / "readable_rc"
    rc.touch()
    # [FIX] Implementation must catch Exception and return False
    with patch.object(Path, "read_text", side_effect=Exception("Read Error")):
        assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_not_present(tmp_path):
    rc = tmp_path / "clean_rc"
    rc.write_text("some content", encoding="utf-8")
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_dirty_removal(tmp_path):
    """Fail if simple string removal leaves artifacts (dirty edit)."""
    rc = tmp_path / "dirty_rc"
    # Create a wrapper that has been edited by the user
    dirty_content = shell.AWSCTL_WRAPPER.replace(
        "awsctl() {", "awsctl() {\n    # User modified this line"
    )
    rc.write_text(dirty_content, encoding="utf-8")

    # If the file contains the markers but not the exact string, it should return False
    assert shell.remove_shell_function(rc) is False


def test_remove_shell_function_success(tmp_path):
    rc = tmp_path / "valid_rc"
    rc.write_text(shell.AWSCTL_WRAPPER, encoding="utf-8")
    assert shell.remove_shell_function(rc) is True
    # Verify the file is effectively cleaned
    assert rc.read_text(encoding="utf-8").strip() == ""
