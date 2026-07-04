# file: tests/test_agent_contract_fixes.py
# SPDX-License-Identifier: MIT
"""
Regression tests for the agent-facing CLI contract fixes:

  1. argv `--` separator: top-level actions (--version/--eval/--help) after `--`
     must be passed to the child verbatim, never interpreted by cloudctl.
  2. error contract: unknown-org lookups return a clean NOT_FOUND (3) with an
     actionable message (json-aware), never the generic "UNEXPECTED ERROR" banner
     with a fictional GitHub URL.
  3. `open --url` prints the console URL to stdout and returns 0 (no browser).
  4. `whoami --format json` surfaces token expiry (expires_at / expires_in_seconds).
"""

from __future__ import annotations

import io
import json
import contextlib
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from cloudctl import cli, exit_codes


# ---------------------------------------------------------------------------
# 1. argv `--` separator no longer leaks top-level actions to cloudctl
# ---------------------------------------------------------------------------


def test_double_dash_does_not_print_version(monkeypatch, capsys):
    """`run ... -- echo --version` must NOT print cloudctl's version.

    The child command (echo --version) is what should run; cloudctl's own
    `--version` action must be inert because it lives after the `--`.
    """
    captured = {}

    def _fake_execute(self, args):
        captured["cmd"] = args.cmd
        return 0

    monkeypatch.setattr("cloudctl.commands.exec.ExecCommand.execute", _fake_execute)

    rc = cli.main(
        [
            "run",
            "--org",
            "myorg",
            "--account",
            "A",
            "--role",
            "R",
            "--region",
            "G",
            "--",
            "echo",
            "--version",
        ]
    )
    out = capsys.readouterr().out

    # The child argv is passed through verbatim, `--` stripped exactly once.
    assert captured["cmd"] == ["echo", "--version"]
    # cloudctl's version string must not have been emitted, and we must not have
    # short-circuited via the version action (which returns 0 without running).
    assert rc == 0  # the fake child returned 0
    assert cli._resolved_version() not in out


def test_double_dash_reaches_child_even_when_org_missing(capsys):
    """`run ... -- echo --version` for an unknown org fails on lookup, NOT on
    the version action: it must reach the exec path (NOT_FOUND), not print the
    version and exit 0."""
    rc = cli.main(
        [
            "run",
            "--org",
            "definitely-not-an-org",
            "--account",
            "A",
            "--role",
            "R",
            "--region",
            "G",
            "--",
            "echo",
            "--version",
        ]
    )
    out = capsys.readouterr().out
    # Reached the real exec path → org-not-found → NOT_FOUND. Never version/0.
    assert rc == exit_codes.NOT_FOUND
    assert cli._resolved_version() not in out


def test_double_dash_passes_eval_to_child(monkeypatch):
    """A `--eval` after `--` belongs to the child and must not enable EVAL mode
    or be stripped from the child argv."""
    captured = {}

    def _fake_execute(self, args):
        captured["cmd"] = args.cmd
        return 0

    monkeypatch.setattr("cloudctl.commands.exec.ExecCommand.execute", _fake_execute)

    cli.main(["run", "--org", "myorg", "--", "some-tool", "--eval", "--help"])
    assert captured["cmd"] == ["some-tool", "--eval", "--help"]


def test_top_level_help_still_works(capsys):
    """A bare top-level `--help` (no subcommand, no `--`) still prints root help."""
    rc = cli.main(["--help"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "cloudctl" in err


def test_top_level_version_still_works(capsys):
    """A bare `--version` (no `--`) still prints the version and exits 0."""
    rc = cli.main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert cli._resolved_version() in out


def test_run_help_documents_double_dash(capsys):
    """`run --help` must document the `--` separator with a worked example."""
    parser = cli._build_parser()
    # Find the run subparser and render its help.
    import pytest

    with contextlib.redirect_stdout(io.StringIO()) as buf:
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--help"])
    help_text = buf.getvalue()
    assert "--" in help_text
    assert "aws sts get-caller-identity" in help_text


def test_login_help_defines_eval_mode(capsys):
    """`login --help` must define EVAL mode in one line."""
    parser = cli._build_parser()
    import pytest

    with contextlib.redirect_stdout(io.StringIO()) as buf:
        with pytest.raises(SystemExit):
            parser.parse_args(["login", "--help"])
    help_text = buf.getvalue().lower()
    assert "eval mode" in help_text
    assert "export" in help_text


# ---------------------------------------------------------------------------
# 2. error contract: unknown org → clean NOT_FOUND, never "UNEXPECTED ERROR"
# ---------------------------------------------------------------------------


def test_accounts_bogus_org_json_is_valid_json_and_exit_3(capsys, monkeypatch):
    """`accounts bogus-org --format json` → valid JSON on stdout + exit 3.

    NOT the "UNEXPECTED ERROR" banner, NOT exit 1.
    """
    # get_org raises for an unknown org (real behaviour).
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_org",
        lambda name: (_ for _ in ()).throw(ValueError(f"Organization '{name}' not found")),
    )
    rc = cli.cmd_accounts(
        Namespace(org="bogus-org", org_flag=None, sync=False, format="json")
    )
    captured = capsys.readouterr()
    assert rc == exit_codes.NOT_FOUND
    payload = json.loads(captured.out.strip())
    assert payload["code"] == exit_codes.NOT_FOUND
    assert "bogus-org" in payload["error"]
    # Must never render the generic bug banner.
    assert "UNEXPECTED ERROR" not in (captured.out + captured.err)
    assert "github.com" not in (captured.out + captured.err).lower()


def test_accounts_bogus_org_table_returns_not_found(capsys, monkeypatch):
    """Table mode: unknown org prints a red prose line to stderr, exit 3."""
    monkeypatch.setattr(
        "cloudctl.commands.accounts.get_org",
        lambda name: (_ for _ in ()).throw(ValueError("nope")),
    )
    rc = cli.cmd_accounts(
        Namespace(org="bogus-org", org_flag=None, sync=False, format="table")
    )
    captured = capsys.readouterr()
    assert rc == exit_codes.NOT_FOUND
    assert "bogus-org" in captured.err


def test_list_roles_bogus_org_json_exit_3(capsys, monkeypatch):
    """`roles bogus --format json` → valid JSON error on stdout + exit 3."""
    from cloudctl.commands.list_roles import ListRolesCommand

    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda name: (_ for _ in ()).throw(ValueError("nope")),
    )
    args = Namespace(org="bogus-org", org_flag=None, account=None, assigned=False, format="json")
    rc = ListRolesCommand().execute(args)
    captured = capsys.readouterr()
    assert rc == exit_codes.NOT_FOUND
    payload = json.loads(captured.out.strip())
    assert payload["code"] == exit_codes.NOT_FOUND
    assert "bogus-org" in payload["error"]


def test_generic_handler_maps_cloudctl_error_exit_code(capsys, monkeypatch):
    """A raised CloudCtlError is mapped to its documented exit code (not 1)."""
    from cloudctl.errors import InvalidOrgError

    def _boom(args):
        raise InvalidOrgError("nope")

    monkeypatch.setattr(cli, "cmd_whoami", _boom)
    rc = cli.main(["whoami"])
    err = capsys.readouterr().err
    # InvalidOrgError.exit_code == 3 (NOT_FOUND); must never say UNEXPECTED ERROR.
    assert rc == 3
    assert "UNEXPECTED ERROR" not in err


def test_generic_handler_has_no_fictional_github_url(capsys, monkeypatch):
    """A genuinely unexpected error no longer prints the fictional BT GitHub URL."""

    def _boom(args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "cmd_whoami", _boom)
    rc = cli.main(["whoami"])
    err = capsys.readouterr().err
    assert rc == exit_codes.ERROR
    assert "UNEXPECTED ERROR" in err  # genuine bug → banner is fine here
    assert "BT-IT-Infrastructure-CloudOps" not in err


# ---------------------------------------------------------------------------
# 3. `open --url` prints the URL and returns 0 (no browser)
# ---------------------------------------------------------------------------


def test_open_url_prints_url_and_no_browser(monkeypatch, capsys):
    """`open --url` prints the console URL to stdout, exit 0, no browser call."""
    monkeypatch.setattr(
        "cloudctl.cli.load_context", lambda: {"current_org": "myorg", "provider": "aws"}
    )
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: {"provider": "aws", "partition": "aws"})
    mock_open = MagicMock()
    monkeypatch.setattr("webbrowser.open", mock_open)

    rc = cli.cmd_open(Namespace(url=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "aws.amazon.com" in out
    mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# 4. whoami surfaces token expiry
# ---------------------------------------------------------------------------


def test_whoami_json_includes_expiry(monkeypatch, capsys):
    """`whoami --format json` includes expires_at + expires_in_seconds from the
    provider's get_token_expiry()."""
    ctx = {
        "current_org": "myorg",
        "account": "123456789012",
        "role": "Admin",
        "region": "us-east-1",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: ctx)
    monkeypatch.setattr(
        "cloudctl.aws.run_aws",
        lambda x: {"returncode": 0, "stdout": '{"Account": "123456789012"}', "stderr": ""},
    )

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    fake_provider = MagicMock()
    fake_provider.get_token_expiry.return_value = future
    monkeypatch.setattr("cloudctl.providers.get_provider", lambda org: fake_provider)
    monkeypatch.setattr("cloudctl.config.get_org", lambda name: {"name": name, "provider": "aws"})

    rc = cli.main(["whoami", "--format", "json"])
    payload = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert payload["expires_at"] is not None
    assert payload["expires_in_seconds"] is not None
    # ~3600s, allow slack for test execution time.
    assert 3400 <= payload["expires_in_seconds"] <= 3600


def test_whoami_json_expiry_null_when_unknown(monkeypatch, capsys):
    """expires_at/expires_in_seconds are null when the provider has no expiry."""
    ctx = {
        "current_org": "myorg",
        "account": "123456789012",
        "role": "Admin",
        "region": "us-east-1",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: ctx)
    monkeypatch.setattr(
        "cloudctl.aws.run_aws",
        lambda x: {"returncode": 0, "stdout": "{}", "stderr": ""},
    )
    fake_provider = MagicMock()
    fake_provider.get_token_expiry.return_value = None
    monkeypatch.setattr("cloudctl.providers.get_provider", lambda org: fake_provider)
    monkeypatch.setattr("cloudctl.config.get_org", lambda name: {"name": name, "provider": "aws"})

    cli.main(["whoami", "--format", "json"])
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["expires_at"] is None
    assert payload["expires_in_seconds"] is None


# ---------------------------------------------------------------------------
# doctor --format json
# ---------------------------------------------------------------------------


def test_doctor_format_json_emits_valid_json(capsys, monkeypatch):
    """`doctor --format json` emits a valid JSON summary of the checks."""
    # Keep the checks fast/deterministic.
    monkeypatch.setattr("cloudctl.doctor.check_aws_version", lambda: (True, "v2"))
    monkeypatch.setattr("cloudctl.doctor.check_shell_integration", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_permissions", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_network_ssl", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.check_time_sync", lambda: (True, "ok"))
    monkeypatch.setattr("cloudctl.doctor.is_wsl", lambda: False)
    monkeypatch.setattr(
        "cloudctl.config.load_raw_config",
        lambda: {"organizations": {"demo": {"provider": "aws"}}},
    )

    rc = cli.cmd_doctor(Namespace(fix_path=False, format="json"))
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)  # must be valid JSON
    assert "ok" in payload
    assert "checks" in payload
    assert isinstance(payload["checks"], list)
    # Multi-cloud presence checks are included.
    names = [c["name"] for c in payload["checks"]]
    assert any("gcloud" in n for n in names)
    assert any("az" in n for n in names)
    assert rc == 0
