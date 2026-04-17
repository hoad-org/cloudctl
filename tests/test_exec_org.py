"""
tests/test_exec_org.py — Unit tests for `awsctl exec --org`.

Covers:
  - --org without --account/--role triggers interactive picker
  - --org with --account and --role skips interactive picker
  - --org with unknown org returns 1
  - No org and no context returns 1 with helpful message
  - exec runs subprocess with injected credentials
  - subprocess FileNotFoundError returns 127
  - subprocess non-zero exit code is propagated
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from awsctl.commands.exec import ExecCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_DATA = {"name": "bt-avm", "provider": "aws"}
_CREDS = {
    "AWS_ACCESS_KEY_ID": "AKID",
    "AWS_SECRET_ACCESS_KEY": "SECRET",
    "AWS_SESSION_TOKEN": "TOKEN",
    "AWS_REGION": "us-east-1",
}


def _make_cmd():
    cmd = ExecCommand()
    cmd.console = MagicMock()
    return cmd


def _make_args(
    org=None, account=None, role=None, region=None, cmd=None
):
    return SimpleNamespace(
        exec_org=org,
        exec_account=account,
        exec_role=role,
        exec_region=region,
        cmd=cmd or ["terraform", "plan"],
    )


# ---------------------------------------------------------------------------
# No context / no org
# ---------------------------------------------------------------------------


class TestExecNoContext:
    def test_no_org_no_context_returns_1(self):
        ec = _make_cmd()
        args = _make_args()
        messages = []
        ec.console.print.side_effect = lambda m, **_: messages.append(str(m))

        with patch("awsctl.commands.exec.load_context", return_value={}):
            rc = ec.execute(args)

        assert rc == 1
        assert any("No org" in m or "context" in m.lower() for m in messages)

    def test_helpful_message_suggests_exec_org(self):
        ec = _make_cmd()
        args = _make_args()
        messages = []
        ec.console.print.side_effect = lambda m, **_: messages.append(str(m))

        with patch("awsctl.commands.exec.load_context", return_value={}):
            rc = ec.execute(args)

        assert rc == 1
        combined = " ".join(messages)
        assert "--org" in combined or "exec --org" in combined


# ---------------------------------------------------------------------------
# --org flag
# ---------------------------------------------------------------------------


class TestExecOrgFlag:
    def test_org_with_account_and_role_skips_interactive(self):
        ec = _make_cmd()
        args = _make_args(org="bt-avm", account="111111111111", role="AdminAccess", region="us-east-1")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_provider = MagicMock()
        mock_provider.get_credentials.return_value = _CREDS

        with patch("awsctl.commands.exec.load_context", return_value={}):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch("subprocess.run", return_value=mock_result):
                        with patch("awsctl.interactive.run_interactive_use") as mock_interactive:
                            rc = ec.execute(args)

        # Interactive should NOT be called when account+role are provided
        mock_interactive.assert_not_called()
        assert rc == 0

    def test_org_without_account_triggers_interactive(self):
        ec = _make_cmd()
        args = _make_args(org="bt-avm")  # no account/role
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_provider = MagicMock()
        mock_provider.get_credentials.return_value = _CREDS

        with patch("awsctl.commands.exec.load_context", return_value={}):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch("subprocess.run", return_value=mock_result):
                        with patch(
                            "awsctl.interactive.run_interactive_use",
                            return_value=("111111111111", "AdminAccess", "us-east-1"),
                        ) as mock_interactive:
                            rc = ec.execute(args)

        mock_interactive.assert_called_once()
        assert rc == 0

    def test_unknown_org_returns_1(self):
        ec = _make_cmd()
        args = _make_args(org="nonexistent", account="111", role="Role", region="us-east-1")

        with patch("awsctl.commands.exec.load_context", return_value={}):
            with patch("awsctl.commands.exec.get_org", side_effect=Exception("not found")):
                rc = ec.execute(args)

        assert rc == 1

    def test_interactive_cancelled_returns_1(self):
        ec = _make_cmd()
        args = _make_args(org="bt-avm")

        with patch("awsctl.commands.exec.load_context", return_value={}):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch(
                    "awsctl.interactive.run_interactive_use",
                    return_value=(None, None, None),
                ):
                    rc = ec.execute(args)

        assert rc == 1


# ---------------------------------------------------------------------------
# Subprocess behavior
# ---------------------------------------------------------------------------


class TestExecSubprocess:
    def _setup_exec(self, cmd_list, returncode=0):
        ec = _make_cmd()
        args = _make_args(account="111111111111", role="AdminAccess", region="us-east-1", cmd=cmd_list)
        ctx = {"current_org": "bt-avm", "account": "111111111111", "role": "AdminAccess", "region": "us-east-1"}
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_provider = MagicMock()
        mock_provider.get_credentials.return_value = _CREDS
        return ec, args, ctx, mock_result, mock_provider

    def test_credentials_injected_into_subprocess_env(self):
        ec, args, ctx, mock_result, mock_provider = self._setup_exec(["aws", "s3", "ls"])
        called_env = {}

        def _capture_run(cmd, env):
            called_env.update(env)
            return mock_result

        with patch("awsctl.commands.exec.load_context", return_value=ctx):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch("subprocess.run", side_effect=_capture_run):
                        rc = ec.execute(args)

        assert rc == 0
        assert called_env.get("AWS_ACCESS_KEY_ID") == "AKID"
        assert called_env.get("AWS_SESSION_TOKEN") == "TOKEN"

    def test_nonzero_returncode_propagated(self):
        ec, args, ctx, mock_result, mock_provider = self._setup_exec(["false"], returncode=2)

        with patch("awsctl.commands.exec.load_context", return_value=ctx):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch("subprocess.run", return_value=mock_result):
                        rc = ec.execute(args)

        assert rc == 2

    def test_file_not_found_returns_127(self):
        ec, args, ctx, _, mock_provider = self._setup_exec(["nonexistent-cmd"])

        with patch("awsctl.commands.exec.load_context", return_value=ctx):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch("subprocess.run", side_effect=FileNotFoundError):
                        rc = ec.execute(args)

        assert rc == 127

    def test_credential_error_returns_1(self):
        ec = _make_cmd()
        args = _make_args(account="111111111111", role="AdminAccess", region="us-east-1")
        ctx = {"current_org": "bt-avm", "account": "111111111111", "role": "AdminAccess", "region": "us-east-1"}
        mock_provider = MagicMock()
        mock_provider.get_credentials.side_effect = RuntimeError("STS error")

        with patch("awsctl.commands.exec.load_context", return_value=ctx):
            with patch("awsctl.commands.exec.get_org", return_value=_ORG_DATA):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    rc = ec.execute(args)

        assert rc == 1
