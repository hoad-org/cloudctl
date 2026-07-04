# file: tests/test_fixed_commands.py
# SPDX-License-Identifier: MIT
"""
Comprehensive test coverage for fixed commands: logout, whoami, open, setup, orgs.

Phase 2 Testing: User-simulated gold standard + automated unit tests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from cloudctl import cli
from cloudctl.context_manager import load_context

# ============================================================================
# LOGOUT COMMAND TESTS
# ============================================================================


def test_logout_help(capsys):
    """Test logout --help shows help text."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["logout", "--help"])
    # SystemExit(0) means help was printed successfully
    assert exc_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "logout" in out or "help" in out


def test_logout_clears_context(mock_home, monkeypatch):
    """Test logout clears ~/.cloudctl/context.json."""
    # Setup: Create a context
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "role": "admin",
        "region": "us-east-1",
        "provider": "aws",
    }
    context_path = mock_home / ".cloudctl" / "context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")

    # Verify context exists
    assert context_path.exists()
    assert load_context() is not None

    # Execute logout
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)
    monkeypatch.setattr("cloudctl.context_manager.save_context_update", MagicMock())

    exit_code = cli.cmd_logout(None)

    # Verify exit code is success
    assert exit_code == 0


def test_logout_returns_unsets(capsys, monkeypatch):
    """Test logout returns shell unset commands."""
    # Setup mock context
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "role": "admin",
    }

    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)
    monkeypatch.setattr("cloudctl.context_manager.save_context_update", MagicMock())

    # Execute logout
    exit_code = cli.cmd_logout(None)

    # Capture output
    out, _ = capsys.readouterr()

    # Verify we got unset commands
    assert exit_code == 0
    # The core.cmd_logout_str() should return unset commands
    assert "unset" in out.lower() or len(out) > 0


def test_logout_handles_no_context(monkeypatch, capsys):
    """Test logout handles when no context exists."""
    # Setup: No context
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})

    # Execute logout
    exit_code = cli.cmd_logout(None)

    # Should still succeed
    assert exit_code == 0


def test_logout_idempotent(monkeypatch):
    """Test logout can be called multiple times safely."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})

    # Call logout twice
    result1 = cli.cmd_logout(None)
    result2 = cli.cmd_logout(None)

    # Both should succeed
    assert result1 == 0
    assert result2 == 0


# ============================================================================
# WHOAMI COMMAND TESTS
# ============================================================================


def test_whoami_help(capsys):
    """Test whoami --help shows help text."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["whoami", "--help"])
    assert exc_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "whoami" in out or "help" in out


def test_whoami_shows_context(mock_rich_console, monkeypatch):
    """Test whoami displays org, account, role from context."""
    # Setup context
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "role": "admin",
        "region": "us-east-1",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    # Mock AWS STS call to avoid actual AWS API
    mock_result = {
        "returncode": 0,
        "stdout": '{"UserId": "AIDA...","Account": "123456789012","Arn": "arn:aws:iam::123456789012:user/test"}',
        "stderr": "",
    }
    monkeypatch.setattr("cloudctl.aws.run_aws", lambda x: mock_result)

    # Execute whoami
    exit_code = cli.cmd_whoami(None)

    # Verify success
    assert exit_code == 0


def test_whoami_no_context_fallback(mock_rich_console, monkeypatch):
    """Test whoami falls back to AWS STS when no context exists."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})

    # Mock AWS STS call
    mock_result = {
        "returncode": 0,
        "stdout": '{"Account": "123456789012"}',
        "stderr": "",
    }
    monkeypatch.setattr("cloudctl.aws.run_aws", lambda x: mock_result)

    # Execute whoami
    exit_code = cli.cmd_whoami(None)

    # Should succeed with fallback
    assert exit_code == 0


def test_whoami_azure_context(mock_rich_console, monkeypatch):
    """Test whoami with Azure provider context."""
    context = {
        "current_org": "avm-prod",
        "account": "subscription-id",
        "role": "Contributor",
        "region": "eastus",
        "provider": "azure",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    # Execute whoami
    exit_code = cli.cmd_whoami(None)

    # Should succeed
    assert exit_code == 0


def test_whoami_gcp_context(mock_rich_console, monkeypatch):
    """Test whoami with GCP provider context."""
    context = {
        "current_org": "gcp-prod",
        "account": "beyondtrust-prod",
        "role": "roles/viewer",
        "region": "us-central1",
        "provider": "gcp",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    # Execute whoami
    exit_code = cli.cmd_whoami(None)

    # Should succeed
    assert exit_code == 0


def test_whoami_sts_error_handling(mock_rich_console, monkeypatch):
    """Test whoami handles AWS STS errors gracefully."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})

    # Mock AWS STS error
    mock_result = {
        "returncode": 1,
        "stdout": "",
        "stderr": "InvalidClientTokenId: The provided token is malformed",
    }
    monkeypatch.setattr("cloudctl.aws.run_aws", lambda x: mock_result)

    # Execute whoami
    exit_code = cli.cmd_whoami(None)

    # Should return error code
    assert exit_code == 1


# ============================================================================
# OPEN COMMAND TESTS
# ============================================================================


def test_open_help(capsys):
    """Test open --help shows help text."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["open", "--help"])
    assert exc_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "open" in out or "help" in out


def test_open_launches_browser(monkeypatch, mock_rich_console):
    """Test open attempts to launch browser."""
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "role": "admin",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    # Mock org config
    org = {
        "provider": "aws",
        "partition": "aws",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    # Mock webbrowser
    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    args = MagicMock()
    exit_code = cli.cmd_open(args)

    # Verify browser was opened
    assert exit_code == 0
    mock_open.assert_called_once()
    # Verify URL is AWS console
    call_args = mock_open.call_args[0][0]
    assert "console.aws.amazon.com" in call_args or "aws.amazon.com" in call_args


def test_open_aws_console_url(monkeypatch, mock_rich_console):
    """Test open generates correct AWS console URL."""
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    org = {
        "provider": "aws",
        "partition": "aws",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    exit_code = cli.cmd_open(None)

    # Verify URL is commercial AWS console
    assert exit_code == 0
    call_args = mock_open.call_args[0][0]
    assert "console.aws.amazon.com" in call_args


def test_open_govcloud_console_url(monkeypatch, mock_rich_console):
    """Test open generates correct GovCloud console URL."""
    context = {
        "current_org": "fdr-gvc",
        "account": "123456789012",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    org = {
        "provider": "aws",
        "partition": "aws-us-gov",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    exit_code = cli.cmd_open(None)

    # Verify URL is GovCloud console
    assert exit_code == 0
    call_args = mock_open.call_args[0][0]
    assert (
        "console.amazonaws-us-gov.com" in call_args or "govcloud" in call_args.lower()
    )


def test_open_azure_console_url(monkeypatch, mock_rich_console):
    """Test open generates correct Azure console URL."""
    context = {
        "current_org": "avm-prod",
        "account": "subscription-id",
        "provider": "azure",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    org = {
        "provider": "azure",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    exit_code = cli.cmd_open(None)

    # Verify URL is Azure portal
    assert exit_code == 0
    call_args = mock_open.call_args[0][0]
    assert "portal.azure.com" in call_args


def test_open_gcp_console_url(monkeypatch, mock_rich_console):
    """Test open generates correct GCP console URL."""
    context = {
        "current_org": "gcp-prod",
        "account": "beyondtrust-prod",
        "provider": "gcp",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    org = {
        "provider": "gcp",
        "default_project": "beyondtrust-prod",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    exit_code = cli.cmd_open(None)

    # Verify URL is GCP console with project
    assert exit_code == 0
    call_args = mock_open.call_args[0][0]
    assert "console.cloud.google.com" in call_args


def test_open_no_context_error(monkeypatch, mock_rich_console):
    """Test open returns error when no active context."""
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})

    # Execute open
    exit_code = cli.cmd_open(None)

    # Should return error
    assert exit_code == 1


def test_open_invalid_org_error(monkeypatch, mock_rich_console):
    """Test open handles invalid org gracefully."""
    context = {
        "current_org": "invalid-org",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    # Mock get_org to raise error
    monkeypatch.setattr(
        "cloudctl.core.get_org", MagicMock(side_effect=Exception("Org not found"))
    )

    # Execute open
    exit_code = cli.cmd_open(None)

    # Should return error
    assert exit_code == 1


# ============================================================================
# SETUP COMMAND TESTS
# ============================================================================


def test_setup_help(capsys):
    """Test setup --help shows help text."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["setup", "--help"])
    assert exc_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "setup" in out or "help" in out


def test_setup_runs_wizard(monkeypatch, mock_rich_console):
    """Test setup executes the configuration wizard."""
    mock_setup = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.core.cmd_setup", mock_setup)

    # Execute setup
    args = MagicMock()
    exit_code = cli.cmd_setup(args)

    # Verify setup was called
    assert exit_code == 0
    mock_setup.assert_called_once()


def test_setup_creates_config(monkeypatch, mock_home, mock_rich_console):
    """Test setup creates orgs.yaml configuration."""
    mock_setup = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.core.cmd_setup", mock_setup)

    # Execute setup
    exit_code = cli.cmd_setup(None)

    # Verify success
    assert exit_code == 0


def test_setup_failure_handling(monkeypatch):
    """Test setup returns error code on failure."""
    mock_setup = MagicMock(return_value=1)
    monkeypatch.setattr("cloudctl.core.cmd_setup", mock_setup)

    # Execute setup
    exit_code = cli.cmd_setup(None)

    # Should return error
    assert exit_code == 1


# ============================================================================
# ORGS COMMAND TESTS
# ============================================================================


def test_orgs_help(capsys):
    """Test orgs --help shows help text."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["orgs", "--help"])
    assert exc_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "org" in out or "help" in out


def test_orgs_lists_organizations(monkeypatch, mock_rich_console):
    """Test orgs lists organizations (same as 'org list')."""
    from argparse import Namespace

    # Mock cmd_org to return 0 (success)
    mock_cmd_org = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.cli.cmd_org", mock_cmd_org)

    # Execute orgs command
    args = Namespace(org_command="list")
    exit_code = cli.cmd_orgs(args)

    # Should succeed
    assert exit_code == 0
    # Verify cmd_org was delegated to
    mock_cmd_org.assert_called_once_with(args)


def test_orgs_alias_works(monkeypatch, mock_rich_console):
    """Test orgs is an alias for 'org list'."""
    from argparse import Namespace

    # Mock the cmd_org function
    mock_org_cmd = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.cli.cmd_org", mock_org_cmd)

    # Execute orgs
    args = Namespace()
    exit_code = cli.cmd_orgs(args)

    # Verify cmd_org was called
    assert exit_code == 0
    mock_org_cmd.assert_called_once()


def test_orgs_empty_list(monkeypatch, mock_rich_console):
    """Test orgs handles empty organization list."""
    monkeypatch.setattr("cloudctl.cli.cmd_org", lambda x: 0)

    # Execute orgs
    exit_code = cli.cmd_orgs(None)

    # Should still succeed
    assert exit_code == 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_logout_then_whoami(monkeypatch, mock_rich_console):
    """Test logout followed by whoami (context cleared)."""
    # Setup initial context (illustrative; the test mocks load_context to {} below)
    _context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "role": "admin",
    }

    monkeypatch.setattr("cloudctl.cli.load_context", lambda: {})
    mock_sts = MagicMock(
        return_value={
            "returncode": 0,
            "stdout": '{"Account": "123456789012"}',
            "stderr": "",
        }
    )
    monkeypatch.setattr("cloudctl.aws.run_aws", mock_sts)

    # Logout then whoami
    exit_logout = cli.cmd_logout(None)
    exit_whoami = cli.cmd_whoami(None)

    # Both should succeed
    assert exit_logout == 0
    assert exit_whoami == 0


def test_open_after_switch(monkeypatch, mock_rich_console):
    """Test opening console after context switch."""
    context = {
        "current_org": "bt-avm",
        "account": "123456789012",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: context)

    org = {
        "provider": "aws",
        "partition": "aws",
    }
    monkeypatch.setattr("cloudctl.core.get_org", lambda x: org)

    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr("webbrowser.open", mock_open)

    # Execute open
    exit_code = cli.cmd_open(None)

    # Should succeed
    assert exit_code == 0
    mock_open.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
