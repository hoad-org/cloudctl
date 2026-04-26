"""
tests/test_watch.py — Unit tests for `cloudctl watch`.

Covers:
  - _check_and_refresh: no token triggers login
  - _check_and_refresh: expired token triggers refresh
  - _check_and_refresh: token within threshold triggers refresh
  - _check_and_refresh: healthy token returns status without refresh
  - _check_and_refresh: token without expiresAt
  - WatchCommand.execute: --once exits after single check
  - WatchCommand.execute: no org, no context → exit 1
  - WatchCommand.execute: unknown org → exit 1
"""

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloudctl.commands.watch import WatchCommand, _check_and_refresh


# ---------------------------------------------------------------------------
# _check_and_refresh unit tests
# ---------------------------------------------------------------------------


def _make_provider(token=None, login_rc=0, expiry=None):
    provider = MagicMock()
    provider.load_token.return_value = token
    provider.login.return_value = login_rc
    # Default None so _check_and_refresh falls back to token.expiresAt
    provider.get_token_expiry.return_value = expiry
    return provider


def _make_token(seconds_remaining):
    token = MagicMock(spec=["expiresAt"])
    token.expiresAt = datetime.now(timezone.utc) + timedelta(seconds=seconds_remaining)
    return token


class TestCheckAndRefresh:
    def test_no_token_triggers_login(self):
        provider = _make_provider(token=None, login_rc=0)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is True
        provider.login.assert_called_once()

    def test_no_token_login_fails(self):
        provider = _make_provider(token=None, login_rc=1)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is False
        assert "failed" in msg.lower() or "login" in msg.lower()

    def test_expired_token_triggers_refresh(self):
        token = _make_token(-60)  # expired 1 minute ago
        provider = _make_provider(token=token, login_rc=0)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is True
        # msg is either "Token expired — re-authenticated" or "Token had 0m left — refreshed proactively"
        assert "expired" in msg.lower() or "refresh" in msg.lower()

    def test_token_within_threshold_triggers_refresh(self):
        token = _make_token(300)  # 5 minutes left, threshold=900
        provider = _make_provider(token=token, login_rc=0)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is True
        assert "proactively" in msg.lower() or "refresh" in msg.lower()

    def test_token_within_threshold_refresh_fails(self):
        token = _make_token(300)
        provider = _make_provider(token=token, login_rc=1)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is False
        assert "failed" in msg.lower()

    def test_healthy_token_returns_valid_status(self):
        token = _make_token(7200)  # 2 hours left
        provider = _make_provider(token=token)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is False
        assert "valid" in msg.lower()
        assert provider.login.call_count == 0

    def test_healthy_token_shows_hours_and_minutes(self):
        token = _make_token(5430)  # 1h30m30s
        provider = _make_provider(token=token)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert "h" in msg

    def test_healthy_token_minutes_only_when_under_one_hour(self):
        token = _make_token(3000)  # 50 minutes, above 900s threshold
        provider = _make_provider(token=token)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert "h" not in msg
        # Something like "50m" or "49m"

    def test_token_without_expiry_attr(self):
        token = MagicMock(spec=[])  # no expiresAt attribute
        provider = _make_provider(token=token)
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is False
        assert "unknown" in msg.lower()

    def test_load_token_exception_returns_error(self):
        provider = MagicMock()
        provider.load_token.side_effect = RuntimeError("token cache corrupt")
        refreshed, msg = _check_and_refresh({}, provider, 900)
        assert refreshed is False
        assert "could not load" in msg.lower()


# ---------------------------------------------------------------------------
# WatchCommand.execute — integration tests
# ---------------------------------------------------------------------------


class TestWatchCommandExecute:
    def _make_cmd(self):
        cmd = WatchCommand()
        cmd.console = MagicMock()
        return cmd

    def _make_args(self, org=None, interval=60, threshold=900, once=False):
        return SimpleNamespace(org=org, interval=interval, threshold=threshold, once=once)

    def test_once_checks_and_exits(self):
        cmd = self._make_cmd()
        args = self._make_args(org="bt-avm", once=True)
        org_data = {"name": "bt-avm", "provider": "aws"}
        token = _make_token(7200)
        mock_provider = _make_provider(token=token)

        with patch("cloudctl.config.get_org", return_value=org_data):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                rc = cmd.execute(args)

        assert rc == 0

    def test_no_org_no_context_returns_1(self):
        cmd = self._make_cmd()
        args = self._make_args(org=None)

        with patch("cloudctl.context_manager.load_context", return_value={}):
            rc = cmd.execute(args)

        assert rc == 1

    def test_no_org_uses_context_org(self):
        cmd = self._make_cmd()
        args = self._make_args(org=None, once=True)
        org_data = {"name": "bt-avm", "provider": "aws"}
        token = _make_token(7200)
        mock_provider = _make_provider(token=token)

        with patch("cloudctl.context_manager.load_context", return_value={"current_org": "bt-avm"}):
            with patch("cloudctl.config.get_org", return_value=org_data):
                with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                    rc = cmd.execute(args)

        assert rc == 0

    def test_unknown_org_returns_1(self):
        cmd = self._make_cmd()
        args = self._make_args(org="nonexistent")

        with patch("cloudctl.config.get_org", side_effect=Exception("not found")):
            rc = cmd.execute(args)

        assert rc == 1

    def test_keyboard_interrupt_returns_0(self):
        cmd = self._make_cmd()
        args = self._make_args(org="bt-avm", once=False, interval=0)
        org_data = {"name": "bt-avm", "provider": "aws"}
        token = _make_token(7200)
        mock_provider = _make_provider(token=token)

        call_count = [0]

        def _fake_check(*a, **kw):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt
            return False, "Token valid"

        with patch("cloudctl.config.get_org", return_value=org_data):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                with patch("cloudctl.commands.watch._check_and_refresh", side_effect=_fake_check):
                    with patch("time.sleep"):
                        rc = cmd.execute(args)

        assert rc == 0
