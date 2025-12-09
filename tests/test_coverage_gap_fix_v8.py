# file: tests/test_coverage_gap_fix_v8.py
from unittest.mock import MagicMock

from awsctl import shell, utils


def test_detect_shell_zsh(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert shell.detect_shell_profile() == tmp_path / ".zshrc"


def test_detect_shell_bash_candidates(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / ".profile").touch()
    assert shell.detect_shell_profile() == tmp_path / ".profile"


def test_is_wsl_false(monkeypatch):
    uname = MagicMock()
    uname.release = "generic-linux"
    monkeypatch.setattr("platform.uname", lambda: uname)
    assert utils.is_wsl() is False


def test_redact_cmd_mixed():
    cmd = ["cmd", "--access-token", "secret", "other"]
    out = utils._redact_cmd(cmd)
    assert "secret" not in out
    assert "[REDACTED]" in out
