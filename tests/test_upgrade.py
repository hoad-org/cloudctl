"""
tests/test_upgrade.py — Unit tests for `awsctl upgrade`.
"""
import os
import sys
from unittest.mock import patch, MagicMock


import awsctl.cli as cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_upgrade(**env_overrides):
    """Call cmd_upgrade with a fake env and return (returncode, console_output)."""
    messages = []
    mock_console = MagicMock()
    mock_console.print.side_effect = lambda msg, **_kw: messages.append(msg)

    env = {k: v for k, v in os.environ.items()}
    env.update(env_overrides)
    env.pop("GITHUB_TOKEN", None)  # start clean
    for k, v in env_overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v

    with patch.dict(os.environ, env, clear=True):
        with patch.object(cli, "console", mock_console):
            args = MagicMock()
            rc = cli.cmd_upgrade(args)

    return rc, messages


# ---------------------------------------------------------------------------
# cmd_upgrade — authenticated path
# ---------------------------------------------------------------------------


class TestCmdUpgradeAuthenticated:
    def test_success_with_token(self):
        """With GITHUB_TOKEN set and pip succeeding, returns 0 and prints success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_testtoken"}, clear=False):
                messages = []
                mock_console = MagicMock()
                mock_console.print.side_effect = lambda m, **_: messages.append(m)
                with patch.object(cli, "console", mock_console):
                    rc = cli.cmd_upgrade(None)

        assert rc == 0
        assert any("upgraded" in str(m).lower() for m in messages)
        # Verify token is embedded in the index URL argument
        call_args = mock_run.call_args[0][0]  # positional argv list
        assert any("ghp_testtoken" in str(a) for a in call_args)
        assert any("pip.pkg.github.com" in str(a) for a in call_args)

    def test_pip_failure_returns_nonzero(self):
        """When pip returns non-zero, cmd_upgrade propagates that exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_testtoken"}, clear=False):
                messages = []
                mock_console = MagicMock()
                mock_console.print.side_effect = lambda m, **_: messages.append(m)
                with patch.object(cli, "console", mock_console):
                    rc = cli.cmd_upgrade(None)

        assert rc == 1
        assert any("failed" in str(m).lower() for m in messages)

    def test_authenticated_upgrade_uses_sys_executable(self):
        """cmd_upgrade must use the same Python interpreter (sys.executable), not 'python'."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}, clear=False):
                with patch.object(cli, "console", MagicMock()):
                    cli.cmd_upgrade(None)

        argv = mock_run.call_args[0][0]
        assert argv[0] == sys.executable, "Must use sys.executable, not 'python'"


# ---------------------------------------------------------------------------
# cmd_upgrade — unauthenticated / missing token
# ---------------------------------------------------------------------------


class TestCmdUpgradeNoToken:
    def test_warning_printed_without_token(self):
        """Without GITHUB_TOKEN, a yellow warning is printed before attempting upgrade."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            env_without_token = {
                k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"
            }
            with patch.dict(os.environ, env_without_token, clear=True):
                messages = []
                mock_console = MagicMock()
                mock_console.print.side_effect = lambda m, **_: messages.append(m)
                with patch.object(cli, "console", mock_console):
                    cli.cmd_upgrade(None)

        assert any("GITHUB_TOKEN" in str(m) for m in messages)

    def test_unauthenticated_index_url_has_no_token(self):
        """Without a token the index URL must not contain any credential string."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            env_without_token = {
                k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"
            }
            with patch.dict(os.environ, env_without_token, clear=True):
                with patch.object(cli, "console", MagicMock()):
                    cli.cmd_upgrade(None)

        argv = mock_run.call_args[0][0]
        index_url = next((a for a in argv if "pip.pkg.github.com" in str(a)), "")
        assert "@" not in index_url or "__token__:" not in index_url


# ---------------------------------------------------------------------------
# cmd_upgrade — dispatch path
# ---------------------------------------------------------------------------


class TestCmdUpgradeDispatch:
    def test_upgrade_in_dispatch_table(self):
        """'upgrade' must be registered in the _DISPATCH dict."""
        assert "upgrade" in cli._DISPATCH
        assert cli._DISPATCH["upgrade"] == "cmd_upgrade"

    def test_main_routes_upgrade(self):
        """main(['upgrade']) must invoke cmd_upgrade."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch.object(cli, "console", MagicMock()):
                rc = cli.main(["upgrade"])

        assert rc == 0
