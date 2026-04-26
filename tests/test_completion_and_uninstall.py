"""
tests/test_completion_and_uninstall.py

Tests for:
  - cloudctl completion  (print snippet / --install)
  - cloudctl uninstall   (dry-run, profile removal, package uninstall)
  - _remove_cloudctl_blocks helper (core removal logic)
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

import cloudctl.cli as cli
from cloudctl.cli import _remove_cloudctl_blocks


# ===========================================================================
# _remove_cloudctl_blocks — unit tests
# ===========================================================================

# Full cloudctl shell wrapper as it appears after `cloudctl init`
_WRAPPER_BLOCK = """\
# AWSCTL SHELL INTEGRATION
cloudctl() {
    local first="${1:-}" needs_eval=0 arg
    case "$first" in
        switch|use|logout) needs_eval=1 ;;
    esac
    if [[ $needs_eval -eq 1 ]]; then
        local tmp exit_code
        tmp=$(mktemp)
        AWSCTL_WRAPPER_ACTIVE=1 command cloudctl --eval "$@" > "$tmp"
        exit_code=$?
        rm -f "$tmp"
        return $exit_code
    else
        AWSCTL_WRAPPER_ACTIVE=1 command cloudctl "$@"
    fi
}
"""

_COMPLETION_BLOCK = """\
# cloudctl completion
eval "$(register-python-argcomplete cloudctl)"
"""

_FISH_COMPLETION_BLOCK = """\
# cloudctl completion
register-python-argcomplete --shell fish cloudctl | source
"""

_UNRELATED = """\
export PATH="$HOME/.local/bin:$PATH"
alias ll='ls -la'
"""


class TestRemoveAwsctlBlocks:
    MARKERS = ["# AWSCTL SHELL INTEGRATION", "# cloudctl completion"]

    def _lines(self, text):
        return text.splitlines(keepends=True)

    def test_removes_full_wrapper_function(self):
        profile = _UNRELATED + _WRAPPER_BLOCK + "\n" + _UNRELATED
        lines = self._lines(profile)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        joined = "".join(result)
        assert "cloudctl()" not in joined
        assert "AWSCTL SHELL INTEGRATION" not in joined
        # Unrelated content preserved
        assert "PATH" in joined
        assert "alias ll" in joined

    def test_removes_completion_eval_line(self):
        profile = _UNRELATED + _COMPLETION_BLOCK + _UNRELATED
        lines = self._lines(profile)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        joined = "".join(result)
        assert "register-python-argcomplete" not in joined
        assert "cloudctl completion" not in joined
        assert "PATH" in joined

    def test_removes_fish_completion_line(self):
        profile = _UNRELATED + _FISH_COMPLETION_BLOCK + _UNRELATED
        lines = self._lines(profile)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        joined = "".join(result)
        assert "register-python-argcomplete" not in joined

    def test_removes_both_blocks(self):
        profile = _UNRELATED + _WRAPPER_BLOCK + "\n" + _COMPLETION_BLOCK + _UNRELATED
        lines = self._lines(profile)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        joined = "".join(result)
        assert "cloudctl()" not in joined
        assert "register-python-argcomplete" not in joined
        assert "PATH" in joined

    def test_no_markers_returns_unchanged(self):
        lines = self._lines(_UNRELATED)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        assert result == lines

    def test_idempotent(self):
        """Removing twice produces the same result as removing once."""
        profile = _UNRELATED + _WRAPPER_BLOCK + _UNRELATED
        lines = self._lines(profile)
        once = _remove_cloudctl_blocks(lines, self.MARKERS)
        twice = _remove_cloudctl_blocks(once, self.MARKERS)
        assert once == twice

    def test_dollar_brace_in_function_not_confused_with_block_end(self):
        """${1:-} and similar shell expansions must not terminate block removal early."""
        profile = _UNRELATED + _WRAPPER_BLOCK + _UNRELATED
        lines = self._lines(profile)
        result = _remove_cloudctl_blocks(lines, self.MARKERS)
        joined = "".join(result)
        # Ensure the full function body was removed, not just the header
        assert "needs_eval" not in joined
        assert "AWSCTL_WRAPPER_ACTIVE" not in joined


# ===========================================================================
# cmd_completion
# ===========================================================================


class TestCmdCompletion:
    def _make_args(self, shell=None, install=False):
        return SimpleNamespace(shell=shell, install=install)

    def test_prints_bash_snippet(self):
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda *a, **_: messages.append(str(a[0]) if a else "")

        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            with patch.object(cli, "console", mock_console):
                rc = cli.cmd_completion(self._make_args())

        assert rc == 0
        combined = " ".join(messages)
        assert "register-python-argcomplete" in combined
        assert "bash" in combined.lower() or ".bashrc" in combined

    def test_prints_zsh_snippet(self):
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda *a, **_: messages.append(str(a[0]) if a else "")

        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch.object(cli, "console", mock_console):
                rc = cli.cmd_completion(self._make_args())

        assert rc == 0
        combined = " ".join(messages)
        assert ".zshrc" in combined

    def test_explicit_fish_shell(self):
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda *a, **_: messages.append(str(a[0]) if a else "")

        with patch.object(cli, "console", mock_console):
            rc = cli.cmd_completion(self._make_args(shell="fish"))

        assert rc == 0
        combined = " ".join(messages)
        assert "fish" in combined

    def test_install_writes_to_profile(self, tmp_path):
        profile = tmp_path / ".zshrc"
        profile.write_text("export FOO=bar\n")

        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch("os.path.expanduser", return_value=str(profile)):
                with patch.object(cli, "console", MagicMock()):
                    rc = cli.cmd_completion(self._make_args(install=True))

        assert rc == 0
        content = profile.read_text()
        assert "register-python-argcomplete" in content
        assert "# cloudctl completion" in content

    def test_install_is_idempotent(self, tmp_path):
        profile = tmp_path / ".zshrc"
        profile.write_text("export FOO=bar\n# cloudctl completion\neval \"$(register-python-argcomplete cloudctl)\"\n")

        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch("os.path.expanduser", return_value=str(profile)):
                with patch.object(cli, "console", MagicMock()):
                    rc = cli.cmd_completion(self._make_args(install=True))

        assert rc == 0
        content = profile.read_text()
        # Should not have added a second copy
        assert content.count("register-python-argcomplete") == 1


# ===========================================================================
# cmd_uninstall
# ===========================================================================


class TestCmdUninstall:
    def _make_args(self, dry_run=False, keep_config=False, package_only=False):
        return SimpleNamespace(dry_run=dry_run, keep_config=keep_config, package_only=package_only)

    def test_dry_run_prints_would_remove(self, tmp_path):
        profile = tmp_path / ".zshrc"
        profile.write_text(_WRAPPER_BLOCK + "export PATH=foo\n")
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda *a, **_: messages.append(str(a[0]) if a else "")

        with patch("os.path.expanduser", side_effect=lambda p: str(profile) if "zshrc" in p else "/nonexistent"):
            with patch.object(cli, "console", mock_console):
                with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
                    rc = cli.cmd_uninstall(self._make_args(dry_run=True))

        assert rc == 0
        # dry_run should NOT modify the file
        content = profile.read_text()
        assert "cloudctl()" in content

    def test_removes_wrapper_from_profile(self, tmp_path):
        profile = tmp_path / ".zshrc"
        profile.write_text("export FOO=bar\n" + _WRAPPER_BLOCK + "export BAZ=qux\n")

        with patch("os.path.expanduser", side_effect=lambda p: str(profile) if "zshrc" in p else "/nonexistent"):
            with patch.object(cli, "console", MagicMock()):
                with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
                    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
                        mock_confirm.return_value.execute.return_value = True
                        rc = cli.cmd_uninstall(self._make_args())

        content = profile.read_text()
        assert "cloudctl()" not in content
        assert "AWSCTL SHELL INTEGRATION" not in content
        assert "FOO" in content
        assert "BAZ" in content

    def test_keep_config_preserves_config_dir(self, tmp_path):
        config_dir = tmp_path / "cloudctl_config"
        config_dir.mkdir()
        (config_dir / "context.json").write_text('{"org": "test"}')

        with patch("os.path.expanduser", side_effect=lambda p: str(config_dir) if "config/cloudctl" in p else "/nonexistent"):
            with patch.object(cli, "console", MagicMock()):
                with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="")):
                    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
                        mock_confirm.return_value.execute.return_value = True
                        rc = cli.cmd_uninstall(self._make_args(keep_config=True))

        # Config should still exist
        assert config_dir.exists()

    def test_package_only_skips_profiles(self, tmp_path):
        profile = tmp_path / ".zshrc"
        profile.write_text(_WRAPPER_BLOCK)
        run_calls = []

        with patch("os.path.expanduser", side_effect=lambda p: str(profile) if "zshrc" in p else "/nonexistent"):
            with patch.object(cli, "console", MagicMock()):
                with patch("subprocess.run", side_effect=lambda cmd, **_: run_calls.append(cmd) or MagicMock(returncode=0, stdout="")):
                    with patch("InquirerPy.inquirer.confirm") as mock_confirm:
                        mock_confirm.return_value.execute.return_value = True
                        rc = cli.cmd_uninstall(self._make_args(package_only=True))

        # Profile should be untouched
        assert "cloudctl()" in profile.read_text()
        # Package uninstall should have been called
        assert any("pip" in str(c) or "pipx" in str(c) for c in run_calls)

    def test_cancelled_by_user_returns_0(self):
        with patch.object(cli, "console", MagicMock()):
            with patch("InquirerPy.inquirer.confirm") as mock_confirm:
                mock_confirm.return_value.execute.return_value = False
                rc = cli.cmd_uninstall(self._make_args())

        assert rc == 0

    def test_dispatch_uninstall_via_main(self):
        with patch("cloudctl.cli.cmd_uninstall", return_value=0) as mock_cmd:
            rc = cli.main(["uninstall", "--dry-run"])
        assert rc == 0
        mock_cmd.assert_called_once()

    def test_dispatch_completion_via_main(self):
        with patch("cloudctl.cli.cmd_completion", return_value=0) as mock_cmd:
            with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
                rc = cli.main(["completion"])
        assert rc == 0
        mock_cmd.assert_called_once()
