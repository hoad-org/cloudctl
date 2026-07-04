"""
Tests for --non-interactive flag on switch, login, and exec commands.

Agents cannot handle interactive prompts or browser popups. The --non-interactive
flag ensures agents can run commands without prompts, or fail fast with clear errors.
"""

import pytest
from unittest.mock import patch, MagicMock
from cloudctl.commands.exec import ExecCommand
from cloudctl import exit_codes


class TestExecNonInteractive:
    """Test --non-interactive flag on exec command."""

    def test_exec_noninteractive_fails_missing_org(self):
        """
        When --org is missing and no context exists, exec fails with the USAGE
        exit code (invalid arguments), not a generic error.
        """
        cmd = ExecCommand()
        args = MagicMock()
        args.non_interactive = True
        args.json_errors = False
        args.exec_org = None
        args.exec_account = None
        args.exec_role = None
        args.exec_region = None
        args.cmd = ["aws", "s3", "ls"]

        with patch("cloudctl.commands.exec.load_context", return_value={}):
            rc = cmd.execute(args)
            assert rc == exit_codes.USAGE

    def test_exec_noninteractive_fails_missing_account(self):
        """
        When --account is missing in a non-TTY context, exec fails fast with the
        USAGE exit code (cannot prompt for the missing argument).
        """
        cmd = ExecCommand()
        args = MagicMock()
        args.non_interactive = True
        args.json_errors = False
        args.exec_org = "bt-avm"
        args.exec_account = None  # Missing
        args.exec_role = "admin"
        args.exec_region = "us-east-1"
        args.cmd = ["aws", "s3", "ls"]

        with patch("sys.stdin.isatty", return_value=False):
            with patch("cloudctl.commands.exec.load_context", return_value={}):
                with patch(
                    "cloudctl.commands.exec.get_org", return_value={"name": "bt-avm"}
                ):
                    rc = cmd.execute(args)
                    assert rc == exit_codes.USAGE

    def test_exec_noninteractive_fails_missing_role(self):
        """
        When --role is missing in a non-TTY context, exec fails fast with the
        USAGE exit code (cannot prompt for the missing argument).
        """
        cmd = ExecCommand()
        args = MagicMock()
        args.non_interactive = True
        args.json_errors = False
        args.exec_org = "bt-avm"
        args.exec_account = "235494790978"
        args.exec_role = None  # Missing
        args.exec_region = "us-east-1"
        args.cmd = ["aws", "s3", "ls"]

        with patch("sys.stdin.isatty", return_value=False):
            with patch("cloudctl.commands.exec.load_context", return_value={}):
                with patch(
                    "cloudctl.commands.exec.get_org", return_value={"name": "bt-avm"}
                ):
                    rc = cmd.execute(args)
                    assert rc == exit_codes.USAGE

    def test_exec_noninteractive_success_all_args(self):
        """
        When --non-interactive and all required args are provided,
        exec should succeed without prompts.
        """
        cmd = ExecCommand()
        args = MagicMock()
        args.non_interactive = True
        args.exec_org = "bt-avm"
        args.exec_account = "235494790978"
        args.exec_role = "admin"
        args.exec_region = "us-east-1"
        args.cmd = ["aws", "s3", "ls"]

        with patch("cloudctl.commands.exec.load_context", return_value={}):
            with patch(
                "cloudctl.commands.exec.get_org",
                return_value={"name": "bt-avm", "provider": "aws"},
            ):
                # Mock the local import of get_provider
                mock_provider = MagicMock()
                mock_provider.get_credentials.return_value = {
                    "AWS_ACCESS_KEY_ID": "test"
                }

                with patch(
                    "cloudctl.providers.get_provider", return_value=mock_provider
                ):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value.returncode = 0

                        rc = cmd.execute(args)
                        assert rc == 0

    def test_exec_interactive_mode_with_missing_args(self):
        """
        Verify that without --non-interactive flag, missing args trigger interactive prompts.
        """
        cmd = ExecCommand()
        args = MagicMock()
        args.non_interactive = False  # Interactive mode
        args.exec_org = "bt-avm"
        args.exec_account = None  # Not provided; should trigger interactive
        args.exec_role = None
        args.exec_region = None
        args.cmd = ["aws", "s3", "ls"]

        # The interactive picker only runs with a TTY; simulate one here.
        with patch("sys.stdin.isatty", return_value=True):
            with patch("cloudctl.commands.exec.load_context", return_value={}):
                with patch(
                    "cloudctl.commands.exec.get_org", return_value={"name": "bt-avm"}
                ):
                    with patch(
                        "cloudctl.interactive.run_interactive_use"
                    ) as mock_interactive:
                        with patch(
                            "cloudctl.providers.get_provider"
                        ) as mock_get_provider:
                            with patch("subprocess.run") as mock_run:
                                mock_interactive.return_value = (
                                    "235494790978",
                                    "admin",
                                    "us-east-1",
                                )
                                mock_provider = MagicMock()
                                mock_provider.get_credentials.return_value = {
                                    "AWS_ACCESS_KEY_ID": "test"
                                }
                                mock_get_provider.return_value = mock_provider
                                mock_run.return_value.returncode = 0

                                rc = cmd.execute(args)

                                # Interactive mode should call run_interactive_use
                                assert mock_interactive.called
                                assert rc == 0


class TestExecHasNoNonInteractiveFlag:
    """exec takes NO --non-interactive flag — it is non-interactive by nature.

    --non-interactive belongs to login/switch (which can show pickers/prompts).
    exec simply runs a command with injected credentials; with full args it never
    prompts, and with incomplete args in a non-TTY context it fails fast (see
    test_exec_noninteractive_* above). Spark calls exec flagless, so this contract
    keeps cloudctl and Spark aligned.
    """

    def _exec_parser(self):
        import argparse

        cmd = ExecCommand()
        main_parser = argparse.ArgumentParser()
        subparsers = main_parser.add_subparsers(dest="command")
        cmd.configure_parser(subparsers)
        return main_parser

    def test_exec_rejects_noninteractive_flag(self):
        """exec must reject --non-interactive (it is a login/switch-only flag)."""
        parser = self._exec_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "exec",
                    "--non-interactive",
                    "--org",
                    "bt-avm",
                    "--",
                    "aws",
                    "s3",
                    "ls",
                ]
            )

    def test_exec_parses_without_noninteractive_flag(self):
        """exec parses normally without the flag, and defines no non_interactive arg."""
        parser = self._exec_parser()
        args = parser.parse_args(
            [
                "exec",
                "--org",
                "bt-avm",
                "--account",
                "123",
                "--role",
                "admin",
                "--",
                "aws",
                "s3",
                "ls",
            ]
        )
        assert args.exec_org == "bt-avm"
        assert not hasattr(args, "non_interactive")
