"""
tests/test_context_expiry.py — Tests for token expiry display in context_manager.

Covers:
  - _format_expiry: green for >1h remaining
  - _format_expiry: yellow for <1h remaining
  - _format_expiry: red warning for <15m remaining
  - _format_expiry: red EXPIRED for expired token
  - _format_expiry: empty string when no expiresAt attribute
  - print_status: shows expiry inline with status
  - print_status: shows previous context hint when available
  - print_status: no context prints warning
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from awsctl.context_manager import _format_expiry


# ---------------------------------------------------------------------------
# _format_expiry
# ---------------------------------------------------------------------------


class TestFormatExpiry:
    def _make_token(self, seconds_remaining):
        token = MagicMock()
        token.expiresAt = datetime.now(timezone.utc) + timedelta(seconds=seconds_remaining)
        return token

    def test_green_for_more_than_one_hour(self):
        token = self._make_token(7200)  # 2 hours
        result = _format_expiry(token)
        assert "green" in result
        assert "h" in result

    def test_yellow_for_under_one_hour(self):
        token = self._make_token(1800)  # 30 minutes, above 15m threshold
        result = _format_expiry(token)
        assert "yellow" in result

    def test_red_warning_for_under_15_minutes(self):
        token = self._make_token(600)  # 10 minutes
        result = _format_expiry(token)
        assert "red" in result
        assert "⚠" in result or "expires in" in result

    def test_red_expired_for_past_token(self):
        token = self._make_token(-60)
        result = _format_expiry(token)
        assert "red" in result
        assert "EXPIRED" in result.upper() or "expire" in result.lower()

    def test_empty_when_no_expires_at_attr(self):
        token = MagicMock(spec=[])  # no expiresAt
        result = _format_expiry(token)
        assert result == ""

    def test_empty_on_exception(self):
        token = MagicMock()
        token.expiresAt = "not-a-datetime"
        result = _format_expiry(token)
        assert result == ""


# ---------------------------------------------------------------------------
# print_status
# ---------------------------------------------------------------------------


class TestPrintStatus:
    def _make_ctx(self, **overrides):
        ctx = {
            "provider": "aws",
            "current_org": "bt-avm",
            "account": "111111111111",
            "role": "AdminAccess",
            "region": "us-east-1",
        }
        ctx.update(overrides)
        return ctx

    def test_no_context_prints_warning(self):
        from awsctl import utils
        messages = []

        with patch("awsctl.context_manager.load_context", return_value={}):
            with patch.object(utils.console, "print", side_effect=lambda *a, **_: messages.append(str(a[0]) if a else "")):
                from awsctl.context_manager import print_status
                print_status()

        combined = " ".join(messages)
        assert "No active" in combined or "context" in combined.lower()

    def test_status_shows_org_and_account(self):
        from awsctl import utils
        messages = []
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = None

        with patch("awsctl.context_manager.load_context", return_value=self._make_ctx()):
            with patch("awsctl.config.get_org", return_value={"provider": "aws"}):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch.object(utils.console, "print", side_effect=lambda *a, **_: messages.append(str(a[0]) if a else "")):
                        from awsctl.context_manager import print_status
                        print_status()

        combined = " ".join(messages)
        assert "bt-avm" in combined
        assert "111111111111" in combined

    def test_previous_context_hint_shown(self):
        from awsctl import utils
        messages = []
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = None

        ctx = self._make_ctx(previous={
            "current_org": "fdr-gvc",
            "account": "222222222222",
            "role": "ReadOnly",
            "region": "us-gov-east-1",
        })

        with patch("awsctl.context_manager.load_context", return_value=ctx):
            with patch("awsctl.config.get_org", return_value={"provider": "aws"}):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch.object(utils.console, "print", side_effect=lambda *a, **_: messages.append(str(a[0]) if a else "")):
                        from awsctl.context_manager import print_status
                        print_status()

        combined = " ".join(messages)
        assert "fdr-gvc" in combined
        assert "switch -" in combined or "switch" in combined

    def test_expiry_shown_when_token_has_expiry(self):
        from awsctl import utils
        messages = []
        mock_token = MagicMock()
        mock_token.expiresAt = datetime.now(timezone.utc) + timedelta(hours=2)
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = mock_token

        with patch("awsctl.context_manager.load_context", return_value=self._make_ctx()):
            with patch("awsctl.config.get_org", return_value={"provider": "aws"}):
                with patch("awsctl.providers.get_provider", return_value=mock_provider):
                    with patch.object(utils.console, "print", side_effect=lambda *a, **_: messages.append(str(a[0]) if a else "")):
                        from awsctl.context_manager import print_status
                        print_status()

        combined = " ".join(messages)
        # Expiry string should be somewhere in the output
        assert "h" in combined or "expires" in combined.lower()
