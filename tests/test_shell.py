# file: tests/test_shell.py
from awsctl import shell


def test_wrapper_injection(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.touch()

    # 1. Inject fresh
    assert shell.inject_shell_function(rc) is True
    content = rc.read_text()
    assert "AWSCTL SHELL INTEGRATION" in content
    assert "awsctl()" in content
    assert "_awsctl_bin" in content

    # 2. Inject idempotent (should return False because already present)
    # This covers the 'return False' branch
    assert shell.inject_shell_function(rc) is False


def test_detect_shell_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    # Case 1: Zsh env var
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert shell.detect_shell_profile() == tmp_path / ".zshrc"

    # Case 2: Bash Profile exists
    monkeypatch.setenv("SHELL", "/bin/bash")
    (tmp_path / ".bash_profile").touch()
    assert shell.detect_shell_profile() == tmp_path / ".bash_profile"

    # Case 3: Default to bashrc
    (tmp_path / ".bash_profile").unlink()
    assert shell.detect_shell_profile() == tmp_path / ".bashrc"


def test_detect_shell_profile_fallbacks(monkeypatch, tmp_path):
    """
    [FIX] Verify new fallback logic for .bash_login and .profile
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/bash")

    # Ensure higher priority files don't exist
    for f in [".bash_profile", ".bashrc"]:
        p = tmp_path / f
        if p.exists():
            p.unlink()

    # Case 4: .bash_login exists
    (tmp_path / ".bash_login").touch()
    assert shell.detect_shell_profile() == tmp_path / ".bash_login"
    (tmp_path / ".bash_login").unlink()

    # Case 5: .profile exists
    (tmp_path / ".profile").touch()
    assert shell.detect_shell_profile() == tmp_path / ".profile"
    (tmp_path / ".profile").unlink()

    # Case 6: Fallback to .bashrc even if it doesn't exist
    assert shell.detect_shell_profile() == tmp_path / ".bashrc"
