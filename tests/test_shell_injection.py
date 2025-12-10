# file: tests/test_shell_injection.py
"""Final wave of coverage tests to hit 90%."""

import os
from unittest.mock import MagicMock, patch

import pytest

from awsctl import aws, shell


def test_shell_injection_failure(monkeypatch):
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: "rc")
    with patch("tempfile.mkstemp", side_effect=OSError("Disk Full")):
        with pytest.raises(OSError):
            shell.inject_shell_function(MagicMock())


def test_aws_config_lock_stale_cleanup(tmp_path, monkeypatch):
    config_file = tmp_path / "config"
    lock_file = tmp_path / "config.lock"
    lock_file.touch()
    old_ts = 10000
    os.utime(lock_file, (old_ts, old_ts))
    monkeypatch.setattr("awsctl.aws.AWS_CONFIG", config_file)
    with patch("time.time", return_value=old_ts + 3600):
        with aws._config_file_lock(timeout=1):
            pass
    assert not lock_file.exists()


def test_clean_env_logic():
    with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "secret", "PATH": "ok"}):
        clean = aws._clean_env()
        assert "AWS_ACCESS_KEY_ID" not in clean
        assert "PATH" in clean


def test_detect_shell_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELL", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert shell.detect_shell_profile() == tmp_path / ".bashrc"
