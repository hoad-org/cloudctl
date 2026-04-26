# file: tests/test_cli_edge_cases.py
# SPDX-License-Identifier: MIT
"""Supplemental tests to hit 100% coverage on CLI logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from cloudctl import cli


def test_whoami_error(monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any) -> None:
    """Verify whoami reports failure correctly when the AWS CLI returns an error."""
    # [FIX] Implementation in core/aws expects a dict return, not a CompletedProcess
    mock_run = MagicMock(
        return_value={"returncode": 1, "stdout": "", "stderr": "AccessDenied"}
    )

    # [FIX] Dispatcher calls aws.run_aws or core.run_aws. Patch at the utility level.
    monkeypatch.setattr("cloudctl.aws.run_aws", mock_run)

    assert cli.cmd_whoami() == 1
    # Check unified console capture
    output = "".join(mock_rich_console.captured)
    assert "Failed to get identity" in output or "AccessDenied" in output


def test_whoami_exception(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """Verify whoami handles unexpected python exceptions during execution."""
    monkeypatch.setattr("cloudctl.aws.run_aws", MagicMock(side_effect=Exception("Boom")))

    assert cli.cmd_whoami() == 1
    output = "".join(mock_rich_console.captured)
    assert "Boom" in output


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


def test_cmd_switch_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, mock_rich_console: Any
) -> None:
    """Verify that Ctrl+C in interactive mode returns a clean error."""
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


def test_cmd_list_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the high-level 'list' command correctly dispatches to resource subcommands."""
    mock_orgs = MagicMock(return_value=0)
    # [FIX] Ensure we patch the location the dispatcher actually calls
    monkeypatch.setattr("cloudctl.cli.cmd_orgs", mock_orgs)

    # Mocking 'list orgs'
    args = type("Args", (), {"resource": "orgs", "json": False})
    cli.cmd_list(args)

    mock_orgs.assert_called_once()
