# file: tests/test_shell_injection.py
"""Final wave of coverage tests to hit 90%."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import aws, shell


def test_shell_injection_failure(monkeypatch):
    """Verify that shell injection raises OSError if the disk is full or temp creation fails."""
    monkeypatch.setattr("cloudctl.shell.detect_shell_profile", lambda: "rc")
    # mkstemp is used during the atomic write process in shell.py
    with patch("tempfile.mkstemp", side_effect=OSError("Disk Full")):
        with pytest.raises(OSError) as e:
            shell.inject_shell_function(MagicMock())
        assert "Disk Full" in str(e.value)


def test_aws_config_lock_stale_cleanup(tmp_path, monkeypatch):
    """Verify that stale config locks (> 1 hour) are automatically removed."""
    config_file = tmp_path / "config"
    lock_file = tmp_path / "config.lock"
    lock_file.touch()

    # Set the lock file time to 1 hour ago
    old_ts = time.time() - 3601
    os.utime(lock_file, (old_ts, old_ts))

    monkeypatch.setattr("cloudctl.aws.AWS_CONFIG", config_file)

    # The implementation of _config_file_lock should check for stale locks
    # and unlink them before yielding.
    with aws._config_file_lock(timeout=1):
        pass

    assert not lock_file.exists()


def test_clean_env_logic():
    """Verify that sensitive AWS credentials are scrubbed from the environment dictionary."""
    # We use a clean dict mock to ensure we aren't leaking from the developer's actual environment
    mock_env = {
        "AWS_ACCESS_KEY_ID": "secret",
        "AWS_SECRET_ACCESS_KEY": "hush",
        "AWS_SESSION_TOKEN": "token",
        "AWS_SECURITY_TOKEN": "old-token",
        "PATH": "/usr/bin",
        "HOME": "/home/user",
    }

    with patch.dict(os.environ, mock_env, clear=True):
        clean = aws.get_clean_env()

        # Security: Keys that MUST be removed
        assert "AWS_ACCESS_KEY_ID" not in clean
        assert "AWS_SECRET_ACCESS_KEY" not in clean
        assert "AWS_SESSION_TOKEN" not in clean
        assert "AWS_SECURITY_TOKEN" not in clean

        # Functionality: Keys that MUST remain
        assert clean.get("PATH") == "/usr/bin"
        assert clean.get("HOME") == "/home/user"


def test_detect_shell_fallback(monkeypatch, tmp_path):
    """Verify that if $SHELL is missing, we default to .bashrc in the home directory."""
    monkeypatch.delenv("SHELL", raising=False)
    # Ensure home directory is mocked to a temp path to avoid touching real dotfiles
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    profile = shell.detect_shell_profile()
    assert profile == tmp_path / ".bashrc"
