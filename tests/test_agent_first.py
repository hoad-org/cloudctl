# file: tests/test_agent_first.py
"""
Tests for the agent-first hardening pass:

  1. JSON output for `whoami --format json`.
  2. Real exit codes (2=auth, 3=not-found, 4=denied, 5=usage) at their obvious
     sites, plus `exec --json-errors` one-line JSON on stderr.
  3. Stdout/stderr discipline: human/error chatter → stderr, machine data →
     stdout.

These deliberately use `capsys` (real stdout/stderr streams) rather than the
`mock_rich_console` fixture, because the point is to verify WHICH stream the
output lands on.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cloudctl import cli, exit_codes, utils
from cloudctl.commands.exec import ExecCommand


# ---------------------------------------------------------------------------
# 1 + 3. whoami --format json
# ---------------------------------------------------------------------------


def test_whoami_json_aws_emits_object_on_stdout(monkeypatch, capsys):
    """whoami --format json prints a parseable object with STS identity to stdout."""
    ctx = {
        "current_org": "myorg",
        "account": "123456789012",
        "role": "AdministratorAccess",
        "region": "us-east-1",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: ctx)
    monkeypatch.setattr(
        "cloudctl.aws.run_aws",
        lambda _cmd: {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "UserId": "AIDA...",
                    "Account": "123456789012",
                    "Arn": "arn:aws:iam::123456789012:role/Admin",
                }
            ),
            "stderr": "",
        },
    )

    args = SimpleNamespace(format="json")
    rc = cli.cmd_whoami(args)
    assert rc == exit_codes.OK

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["provider"] == "aws"
    assert payload["org"] == "myorg"
    assert payload["account"] == "123456789012"
    assert payload["role"] == "AdministratorAccess"
    assert payload["region"] == "us-east-1"
    # STS caller-identity fields live under `identity`.
    assert payload["identity"]["Account"] == "123456789012"


def test_whoami_json_auth_failure_exit_2(monkeypatch, capsys):
    """A failed STS call in json mode still emits JSON and returns AUTH (2)."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"provider": "aws"})
    monkeypatch.setattr(
        "cloudctl.aws.run_aws",
        lambda _cmd: {"returncode": 1, "stdout": "", "stderr": "ExpiredToken"},
    )

    rc = cli.cmd_whoami(SimpleNamespace(format="json"))
    assert rc == exit_codes.AUTH
    payload = json.loads(capsys.readouterr().out)
    assert payload["identity"] is None
    assert "error" in payload


def test_whoami_json_gcp(monkeypatch, capsys):
    """Non-AWS providers emit known context under `identity`."""
    ctx = {
        "current_org": "gcp-terrorgems",
        "account": "asatst-gemini-api-v2",
        "role": "roles/viewer",
        "region": "us-central1",
        "provider": "gcp",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: ctx)

    rc = cli.cmd_whoami(SimpleNamespace(format="json"))
    assert rc == exit_codes.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "gcp"
    assert payload["account"] == "asatst-gemini-api-v2"
    assert payload["identity"]["role"] == "roles/viewer"


# ---------------------------------------------------------------------------
# 2. exec exit codes + --json-errors
# ---------------------------------------------------------------------------

_ORG_DATA = {"name": "myorg", "provider": "aws"}


def _exec_args(**kw):
    base = dict(
        exec_org=None,
        exec_account=None,
        exec_role=None,
        exec_region=None,
        json_errors=False,
        cmd=["aws", "sts", "get-caller-identity"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_exec_no_context_is_usage_and_nonzero():
    ec = ExecCommand()
    ec.console = MagicMock()
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        rc = ec.execute(_exec_args())
    assert rc == exit_codes.USAGE
    assert rc != 0


def test_exec_unknown_org_is_not_found():
    ec = ExecCommand()
    ec.console = MagicMock()
    args = _exec_args(
        exec_org="ghost", exec_account="1", exec_role="R", exec_region="r"
    )
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", side_effect=Exception("nope")):
            rc = ec.execute(args)
    assert rc == exit_codes.NOT_FOUND


def test_exec_auth_required_when_provider_raises_systemexit():
    ec = ExecCommand()
    ec.console = MagicMock()
    args = _exec_args(
        exec_org="myorg", exec_account="1", exec_role="R", exec_region="r"
    )
    provider = MagicMock()
    provider.get_credentials.side_effect = SystemExit(1)
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", return_value=_ORG_DATA):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                rc = ec.execute(args)
    assert rc == exit_codes.AUTH


def test_exec_json_errors_writes_one_line_json_to_stderr(capsys):
    """--json-errors: failures print {"error","code"} on stderr, nothing on stdout."""
    ec = ExecCommand()
    # Use a real Console(stderr=True) so we exercise the true stream routing.
    args = _exec_args(json_errors=True)
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        rc = ec.execute(args)

    assert rc == exit_codes.USAGE
    captured = capsys.readouterr()
    # Machine JSON on stderr, single line, parseable.
    line = captured.err.strip()
    payload = json.loads(line)
    assert payload["code"] == exit_codes.USAGE
    assert payload["error"]
    # Nothing leaked to stdout.
    assert captured.out == ""


def test_exec_json_errors_not_found_payload(capsys):
    ec = ExecCommand()
    args = _exec_args(
        exec_org="ghost",
        exec_account="1",
        exec_role="R",
        exec_region="r",
        json_errors=True,
    )
    with patch("cloudctl.commands.exec.load_context", return_value={}):
        with patch("cloudctl.commands.exec.get_org", side_effect=Exception("nope")):
            rc = ec.execute(args)
    assert rc == exit_codes.NOT_FOUND
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["code"] == exit_codes.NOT_FOUND


def test_exec_success_path_unchanged(capsys):
    """Success path is untouched: child return code propagates, no error JSON."""
    ec = ExecCommand()
    ec.console = MagicMock()
    ctx = {
        "current_org": "myorg",
        "account": "1",
        "role": "R",
        "region": "r",
    }
    provider = MagicMock()
    provider.get_credentials.return_value = {"AWS_ACCESS_KEY_ID": "x"}
    result = MagicMock()
    result.returncode = 0
    with patch("cloudctl.commands.exec.load_context", return_value=ctx):
        with patch("cloudctl.commands.exec.get_org", return_value=_ORG_DATA):
            with patch("cloudctl.providers.get_provider", return_value=provider):
                with patch("subprocess.run", return_value=result):
                    rc = ec.execute(_exec_args(json_errors=True))
    assert rc == 0
    # Success emits no error JSON.
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# 3. Stdout/stderr discipline in utils
# ---------------------------------------------------------------------------


def test_utils_console_is_stderr():
    """Human/status/error chatter must route to stderr."""
    assert utils.console.stderr is True


def test_utils_stdout_console_is_stdout():
    """Machine data + eval `export` lines must route to stdout."""
    assert utils.stdout_console.stderr is False
