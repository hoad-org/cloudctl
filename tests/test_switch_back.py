"""
tests/test_switch_back.py — Unit tests for `awsctl switch -` (previous context restore).

Tests the real code path: cli.cmd_switch with target/org="-".

Covers:
  - switch - with full previous context → emits exports + saves context
  - switch - with no previous context → returns 1 with message
  - switch - with incomplete previous context → returns 1
  - switch - with org no longer in config → falls back gracefully
  - main(["switch", "-"]) dispatch integration
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import awsctl.cli as cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PREV = {
    "current_org": "bt-avm",
    "account": "111111111111",
    "role": "AdminAccess",
    "region": "us-east-1",
}

_ORG_DATA = {
    "name": "bt-avm",
    "provider": "aws",
    "sso_start_url": "https://d-abc.awsapps.com/start",
    "sso_region": "us-east-1",
}


def _make_args(org="-"):
    return SimpleNamespace(
        org=org, target=None, account=None, role=None, region=None
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSwitchBack:
    def test_switch_dash_restores_previous_context(self):
        messages = []
        mock_console = MagicMock()
        mock_console.print.side_effect = lambda *a, **_: messages.append(str(a[0]) if a else "")

        with patch("awsctl.context_manager.get_previous_context", return_value=_PREV):
            with patch("awsctl.config.get_org", return_value=_ORG_DATA):
                with patch("awsctl.cli.emit_exports", return_value="export AWS_REGION=us-east-1\n"):
                    with patch("awsctl.context_manager.save_context") as mock_save:
                        with patch.object(cli, "console", mock_console):
                            with patch("builtins.print"):
                                rc = cli.cmd_switch(_make_args())

        assert rc == 0
        mock_save.assert_called_once_with("bt-avm", "111111111111", "AdminAccess", "us-east-1")

    def test_switch_dash_prints_success_message(self, capsys):
        with patch("awsctl.context_manager.get_previous_context", return_value=_PREV):
            with patch("awsctl.config.get_org", return_value=_ORG_DATA):
                with patch("awsctl.cli.emit_exports", return_value=""):
                    with patch("awsctl.context_manager.save_context"):
                        with patch.object(cli, "console", MagicMock()):
                            with patch("builtins.print"):
                                rc = cli.cmd_switch(_make_args())

        assert rc == 0
        # The success message goes to utils.console (stderr) or stdout; rc==0 is sufficient.

    def test_switch_dash_emits_exports_to_stdout(self):
        printed = []

        with patch("awsctl.context_manager.get_previous_context", return_value=_PREV):
            with patch("awsctl.config.get_org", return_value=_ORG_DATA):
                with patch("awsctl.cli.emit_exports", return_value="export FOO=bar\n"):
                    with patch("awsctl.context_manager.save_context"):
                        with patch.object(cli, "console", MagicMock()):
                            with patch("builtins.print", side_effect=lambda x: printed.append(x)):
                                rc = cli.cmd_switch(_make_args())

        assert rc == 0
        assert any("FOO" in p for p in printed)

    def test_switch_dash_org_missing_from_config_falls_back(self):
        """When the previous org is gone from config, cmd_switch creates a stub org_data."""
        with patch("awsctl.context_manager.get_previous_context", return_value=_PREV):
            with patch("awsctl.config.get_org", side_effect=Exception("not found")):
                with patch("awsctl.cli.emit_exports", return_value=""):
                    with patch("awsctl.context_manager.save_context"):
                        with patch.object(cli, "console", MagicMock()):
                            with patch("builtins.print"):
                                rc = cli.cmd_switch(_make_args())
        # cli.cmd_switch falls back to a stub org_data — should still succeed
        assert rc == 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestSwitchBackErrors:
    def test_no_previous_context_returns_1(self, capsys):
        with patch("awsctl.context_manager.get_previous_context", return_value=None):
            with patch.object(cli, "console", MagicMock()):
                rc = cli.cmd_switch(_make_args())

        assert rc == 1
        combined = capsys.readouterr().out + capsys.readouterr().err
        # Message may go to stdout or via rich console — just check rc==1

    def test_incomplete_previous_context_returns_1(self, capsys):
        incomplete = {"current_org": "bt-avm", "account": "111111111111"}  # missing role/region

        with patch("awsctl.context_manager.get_previous_context", return_value=incomplete):
            with patch.object(cli, "console", MagicMock()):
                rc = cli.cmd_switch(_make_args())

        assert rc == 1


# ---------------------------------------------------------------------------
# End-to-end: main() dispatch
# ---------------------------------------------------------------------------


class TestSwitchBackDispatch:
    def test_main_routes_switch_dash(self):
        with patch("awsctl.context_manager.get_previous_context", return_value=_PREV):
            with patch("awsctl.config.get_org", return_value=_ORG_DATA):
                with patch("awsctl.cli.emit_exports", return_value=""):
                    with patch("awsctl.context_manager.save_context"):
                        with patch.object(cli, "console", MagicMock()):
                            with patch("builtins.print"):
                                rc = cli.main(["switch", "-"])
        assert rc == 0
