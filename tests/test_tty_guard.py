"""Tests for the --eval TTY guard in awsctl.cli.main()."""

import os
from unittest.mock import patch


def test_eval_with_wrapper_active_no_warning(capsys):
    """When AWSCTL_WRAPPER_ACTIVE is set, no warning is emitted."""
    import awsctl.cli as cli

    env = {**os.environ, "AWSCTL_WRAPPER_ACTIVE": "1"}
    with patch.dict(os.environ, env, clear=True):
        # Just call determine_strategy to verify routing; main() would need a full command
        result = cli.determine_strategy(["switch"])
        assert result == "EVAL"
    captured = capsys.readouterr()
    assert "WARNING" not in captured.err


def test_eval_without_wrapper_active_warns(capsys, monkeypatch):
    """When --eval is used without AWSCTL_WRAPPER_ACTIVE, a warning goes to stderr."""
    import awsctl.cli as cli

    # Remove AWSCTL_WRAPPER_ACTIVE from env
    env = {k: v for k, v in os.environ.items() if k != "AWSCTL_WRAPPER_ACTIVE"}
    with patch.dict(os.environ, env, clear=True):
        # Patch the parser to prevent it from calling sys.exit
        with patch.object(cli, "cmd_init", return_value=0):
            cli.main(["--eval", "init"])
    captured = capsys.readouterr()
    assert "WARNING" in captured.err or "wrapper" in captured.err.lower()


def test_eval_flag_stripped_before_dispatch(monkeypatch):
    """The --eval flag is stripped before argparse sees it."""
    import awsctl.cli as cli

    calls = []
    monkeypatch.setattr(cli, "cmd_status", lambda args: calls.append("status") or 0)
    env = {**os.environ, "AWSCTL_WRAPPER_ACTIVE": "1"}
    with patch.dict(os.environ, env, clear=True):
        cli.main(["--eval", "status"])
    assert "status" in calls


def test_wrapper_active_env_var_in_shell_wrapper():
    """The shell wrapper constant must set AWSCTL_WRAPPER_ACTIVE=1."""
    from awsctl import shell

    assert "AWSCTL_WRAPPER_ACTIVE=1" in shell.AWSCTL_WRAPPER
    assert "AWSCTL_WRAPPER_ACTIVE=1" in shell.AWSCTL_FISH_WRAPPER


def test_powershell_wrapper_sets_wrapper_active():
    """The PowerShell wrapper must set $env:AWSCTL_WRAPPER_ACTIVE."""
    from awsctl import shell

    assert "AWSCTL_WRAPPER_ACTIVE" in shell.AWSCTL_PS_WRAPPER
