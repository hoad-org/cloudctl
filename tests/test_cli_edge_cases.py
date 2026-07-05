# file: tests/test_cli_edge_cases.py
# SPDX-License-Identifier: MIT
"""Supplemental tests to hit 100% coverage on CLI logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from cloudctl import cli, exit_codes


def test_whoami_error(monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any) -> None:
    """Verify whoami reports failure correctly when the AWS CLI returns an error.

    whoami routes AWS identity through provider.get_identity (real sts call),
    so patch the provider-module run_aws binding."""
    mock_run = MagicMock(
        return_value={"returncode": 1, "stdout": "", "stderr": "AccessDenied"}
    )
    monkeypatch.setattr("cloudctl.providers.aws.run_aws", mock_run)
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"provider": "aws"})
    monkeypatch.setattr(
        "cloudctl.config.get_org", lambda _n: {"name": "", "provider": "aws"}
    )

    # A failed STS call = no valid SSO session → AUTH exit code (2).
    # Force table format so the error is emitted as prose to the rich console;
    # in non-TTY contexts whoami now defaults to JSON (error goes to stdout).
    args = type("Args", (), {"format": "table"})()
    assert cli.cmd_whoami(args) == exit_codes.AUTH
    # Check unified console capture
    output = "".join(mock_rich_console.captured)
    assert "Failed to get identity" in output


def test_whoami_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """whoami never crashes if identity resolution fails. Under the honest-
    identity contract, an unverifiable AWS identity (get_identity raising, or
    returning None) is reported as AUTH (2) — cloudctl NEVER fabricates an
    identity from stored context."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"provider": "aws"})
    monkeypatch.setattr(
        "cloudctl.config.get_org", lambda _n: {"name": "", "provider": "aws"}
    )
    # get_identity blows up internally — whoami must still not crash.
    monkeypatch.setattr(
        "cloudctl.providers.aws.AwsProvider.get_identity",
        MagicMock(side_effect=Exception("Boom")),
    )

    # Force table format so the failure is emitted as prose to the rich console
    # (non-TTY whoami defaults to JSON, which routes to stdout).
    args = type("Args", (), {"format": "table"})()
    # No verified identity → AUTH (2), and whoami did not raise.
    assert cli.cmd_whoami(args) == exit_codes.AUTH
    output = "".join(mock_rich_console.captured)
    assert "identity" in output.lower()


def test_open_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """Verify the console opener reports configuration errors."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"current_org": "btavm"})
    # Fail during org loading
    monkeypatch.setattr(
        "cloudctl.core.get_org", MagicMock(side_effect=Exception("ConfigFail"))
    )

    # cmd_open handles console URL generation; exceptions should be trapped.
    assert cli.cmd_open() == 1
    assert "Error" in "".join(mock_rich_console.captured)


def test_cmd_login_chaining_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that login chaining (login -> switch) works even if resolution logic is complex."""
    # 1. Mock base login success
    monkeypatch.setattr("cloudctl.core.cmd_login", lambda o, **k: 0)
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {"current_org": "btavm"})
    monkeypatch.setattr(
        "cloudctl.core.load_orgs_config", lambda: {"orgs": [{"name": "btavm"}]}
    )

    # 2. Mock the org ref used for the switch bridge
    monkeypatch.setattr("cloudctl.cli._get_org_ref", lambda n: MagicMock())

    # 3. Simulate a failure in account resolution during chaining
    monkeypatch.setattr(
        "cloudctl.cli._resolve_account_id",
        MagicMock(side_effect=Exception("ResolveFail")),
    )

    # 4. Mock switch to verify it IS still attempted or handled
    mock_switch = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.cli.cmd_switch", mock_switch)

    # Provide full attribute set expected by argparse/dispatch
    args = type(
        "Args",
        (),
        {
            "org": "btavm",
            "account": "123",
            "role": "Admin",
            "region": "us-east-1",
            "force": False,
        },
    )

    cli.cmd_login(args)
    # Verification: Does the login dispatcher attempt to bridge to switch?
    assert mock_switch.called


def _force_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make cli._non_interactive see an interactive TTY (no CI/agent env),
    so the interactive-picker code path under test is actually reached."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)

    class _T:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("cloudctl.cli.sys.stdin", _T())


def test_cmd_switch_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """Verify that Ctrl+C in interactive mode returns a clean error."""
    _force_tty(monkeypatch)
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})
    monkeypatch.setattr(
        "cloudctl.interactive.run_interactive_use",
        MagicMock(side_effect=KeyboardInterrupt),
    )

    # Positional 'target' is None for interactive mode
    args = type(
        "Args",
        (),
        {"target": None, "account": None, "role": None, "region": None, "org": "btavm"},
    )

    assert cli.cmd_switch(args) == 1
    assert "Operation cancelled" in "".join(mock_rich_console.captured)


def test_cmd_switch_generic_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """Verify that unexpected failures in the switch logic are caught."""
    _force_tty(monkeypatch)
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})
    monkeypatch.setattr(
        "cloudctl.interactive.run_interactive_use",
        MagicMock(side_effect=Exception("RandomFail")),
    )

    args = type(
        "Args",
        (),
        {"target": None, "account": None, "role": None, "region": None, "org": "btavm"},
    )

    assert cli.cmd_switch(args) == 1
    assert "failed" in "".join(mock_rich_console.captured).lower()


def test_cmd_list_dispatch() -> None:
    """Verify the 'list' command shows configured organizations (shortcut for org list)."""
    # The list command is now a direct shortcut to OrgListCommand
    # Just verify it returns 0 (success) when called
    args = type("Args", (), {"json": False})
    # Should return 0 without error (even with no orgs configured, it returns 0)
    assert cli.cmd_list(args) == 0
