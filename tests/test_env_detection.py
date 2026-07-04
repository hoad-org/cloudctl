# file: tests/test_env_detection.py
from unittest.mock import MagicMock

from cloudctl import shell, utils


def test_detect_shell_zsh(monkeypatch, tmp_path):
    """Verify that ZSH env correctly identifies .zshrc in the home directory."""
    monkeypatch.setenv("SHELL", "/bin/zsh")
    # [FIX] Patch the internal HOME variable or Path.home() depending on implementation
    monkeypatch.setattr(shell, "HOME", tmp_path)

    # Ensure the directory exists to satisfy internal logic
    assert shell.detect_shell_profile() == tmp_path / ".zshrc"


def test_detect_shell_bash_candidates(monkeypatch, tmp_path):
    """Verify Bash priority: .bash_profile > .bash_login > .profile."""
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr(shell, "HOME", tmp_path)

    # 1. Test lowest priority
    profile = tmp_path / ".profile"
    profile.touch()
    assert shell.detect_shell_profile() == profile

    # 2. Test higher priority candidate overshadows .profile
    bash_profile = tmp_path / ".bash_profile"
    bash_profile.touch()
    assert shell.detect_shell_profile() == bash_profile


def test_is_wsl_false(monkeypatch):
    """Verify WSL detection returns False for standard Linux kernels."""
    uname = MagicMock()
    # [FIX] Align with the specific platform check logic in utils.py
    # Logic looks for "microsoft" or "wsl" in the release string
    uname.release = "5.15.0-generic"
    monkeypatch.setattr("platform.uname", lambda: uname)
    assert utils.is_wsl() is False


def test_redact_cmd_mixed():
    """Verify that the redaction utility identifies and hides tokens/secrets."""
    cmd = ["cmd", "--access-token", "secret-value", "other-param"]
    out = utils._redact_cmd(cmd)

    # [FIX] Ensure we don't leak the actual value
    assert "secret-value" not in out
    # [FIX] Check that the exact redaction marker is used
    assert "[REDACTED]" in out
    # Ensure non-sensitive parts remain
    assert "cmd" in out
    assert "other-param" in out
