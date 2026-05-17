"""
tests/test_prompt.py — Unit tests for `cloudctl prompt`.

Covers:
  - full output format
  - --short mode
  - --json mode
  - --no-icon flag
  - --starship / --p10k snippet modes
  - --warn-expiry threshold
  - no active context → silent exit 0
  - _expiry_label helper
  - _parse_expiry_minutes helper
"""

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from cloudctl.commands.prompt import (
    PromptCommand,
    _expiry_label,
    _parse_expiry_minutes,
    _print_starship_snippet,
    _print_p10k_snippet,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CTX = {
    "provider": "aws",
    "current_org": "bt-avm",
    "account": "111111111111",
    "role": "AdminAccess",
    "region": "us-east-1",
}


def _make_args(**kwargs):
    defaults = dict(
        short=False,
        json=False,
        starship=False,
        p10k=False,
        format="plain",
        no_icon=False,
        warn_expiry=15,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _run(args, ctx=None, capture=True):
    """Execute PromptCommand, capture stdout. Returns (rc, output_str)."""
    cmd = PromptCommand()
    ctx = ctx if ctx is not None else _CTX
    buf = io.StringIO()
    with patch("cloudctl.context_manager.load_context", return_value=ctx):
        with patch("sys.stdout", buf):
            rc = cmd.execute(args)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# Full mode (default)
# ---------------------------------------------------------------------------


class TestPromptFull:
    def test_full_output_contains_org_and_account(self):
        rc, out = _run(_make_args())
        assert rc == 0
        assert "bt-avm" in out
        assert "111111111111" in out
        assert "AdminAccess" in out
        assert "us-east-1" in out

    def test_full_output_contains_cloud_icon(self):
        rc, out = _run(_make_args())
        assert "☁" in out

    def test_no_icon_omits_symbol(self):
        rc, out = _run(_make_args(no_icon=True))
        assert "☁" not in out
        assert "bt-avm" in out

    def test_azure_icon(self):
        ctx = {**_CTX, "provider": "azure"}
        rc, out = _run(_make_args(), ctx=ctx)
        assert "⬡" in out

    def test_gcp_icon(self):
        ctx = {**_CTX, "provider": "gcp"}
        rc, out = _run(_make_args(), ctx=ctx)
        assert "◆" in out


# ---------------------------------------------------------------------------
# Short mode
# ---------------------------------------------------------------------------


class TestPromptShort:
    def test_short_contains_org(self):
        rc, out = _run(_make_args(short=True))
        assert rc == 0
        assert "bt-avm" in out

    def test_short_omits_account_detail(self):
        rc, out = _run(_make_args(short=True))
        assert "111111111111" not in out


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------


class TestPromptJson:
    def test_json_output_is_valid_json(self):
        rc, out = _run(_make_args(json=True))
        assert rc == 0
        data = json.loads(out)
        assert data["org"] == "bt-avm"
        assert data["account"] == "111111111111"
        assert data["region"] == "us-east-1"
        assert data["provider"] == "aws"

    def test_json_no_expiry_when_unavailable(self):
        with patch("cloudctl.commands.prompt._expiry_label", return_value=None):
            rc, out = _run(_make_args(json=True))
        data = json.loads(out)
        assert "expires_in" not in data

    def test_json_includes_expiry_when_available(self):
        with patch("cloudctl.commands.prompt._expiry_label", return_value="47m"):
            rc, out = _run(_make_args(json=True))
        data = json.loads(out)
        assert data["expires_in"] == "47m"


# ---------------------------------------------------------------------------
# No context → silent
# ---------------------------------------------------------------------------


class TestPromptNoContext:
    def test_empty_context_returns_0_silently(self):
        rc, out = _run(_make_args(), ctx={})
        assert rc == 0
        assert out == ""


# ---------------------------------------------------------------------------
# Snippet modes
# ---------------------------------------------------------------------------


class TestPromptSnippets:
    def test_starship_flag_prints_snippet(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cmd = PromptCommand()
            rc = cmd.execute(_make_args(starship=True))
        out = buf.getvalue()
        assert rc == 0
        assert "starship.toml" in out.lower() or "cloudctl" in out.lower()
        assert "cloudctl prompt" in out

    def test_p10k_flag_prints_snippet(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cmd = PromptCommand()
            rc = cmd.execute(_make_args(p10k=True))
        out = buf.getvalue()
        assert rc == 0
        assert "p10k" in out.lower() or "powerlevel" in out.lower()
        assert "prompt_cloudctl" in out

    def test_starship_snippet_standalone(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _print_starship_snippet()
        out = buf.getvalue()
        assert "[custom.cloudctl]" in out

    def test_p10k_snippet_standalone(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _print_p10k_snippet()
        out = buf.getvalue()
        assert "function prompt_cloudctl" in out
        assert "instant_prompt_cloudctl" in out


# ---------------------------------------------------------------------------
# Expiry warning
# ---------------------------------------------------------------------------


class TestPromptExpiryWarning:
    def test_warn_shown_when_near_expiry(self):
        with patch("cloudctl.commands.prompt._expiry_label", return_value="10m"):
            rc, out = _run(_make_args(short=True, warn_expiry=15))
        assert "⚠" in out or "10m" in out

    def test_warn_not_shown_when_ample_time(self):
        with patch("cloudctl.commands.prompt._expiry_label", return_value="2h30m"):
            rc, out = _run(_make_args(short=True, warn_expiry=15))
        assert "⚠" not in out

    def test_expired_shows_expired_marker(self):
        with patch("cloudctl.commands.prompt._expiry_label", return_value="expired"):
            rc, out = _run(_make_args(short=True))
        assert "expired" in out


# ---------------------------------------------------------------------------
# _parse_expiry_minutes
# ---------------------------------------------------------------------------


class TestParseExpiryMinutes:
    def test_minutes_only(self):
        assert _parse_expiry_minutes("47m") == 47

    def test_hours_and_minutes(self):
        assert _parse_expiry_minutes("1h23m") == 83

    def test_hours_only(self):
        assert _parse_expiry_minutes("2h") == 120

    def test_invalid_returns_none(self):
        assert _parse_expiry_minutes("xyz") is None


# ---------------------------------------------------------------------------
# _expiry_label — unit tests
# ---------------------------------------------------------------------------


class TestExpiryLabel:
    def test_returns_none_for_azure(self):
        ctx = {**_CTX, "provider": "azure"}
        result = _expiry_label(ctx)
        assert result is None

    def test_returns_none_when_no_org(self):
        result = _expiry_label({})
        assert result is None

    def test_returns_none_when_no_token(self):
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = None
        with patch("cloudctl.config.get_org", return_value={}):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                result = _expiry_label(_CTX)
        assert result is None

    def test_returns_expired_for_past_token(self):
        from datetime import datetime, timezone, timedelta

        mock_token = MagicMock()
        mock_token.expiresAt = datetime.now(timezone.utc) - timedelta(seconds=60)
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = mock_token
        with patch("cloudctl.config.get_org", return_value={}):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                result = _expiry_label(_CTX)
        assert result == "expired"

    def test_returns_minutes_for_short_remaining(self):
        from datetime import datetime, timezone, timedelta

        mock_token = MagicMock()
        mock_token.expiresAt = datetime.now(timezone.utc) + timedelta(minutes=47)
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = mock_token
        with patch("cloudctl.config.get_org", return_value={}):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                result = _expiry_label(_CTX)
        # Allow ±1 minute rounding
        assert result in ("46m", "47m", "48m")

    def test_returns_hours_for_long_remaining(self):
        from datetime import datetime, timezone, timedelta

        mock_token = MagicMock()
        mock_token.expiresAt = datetime.now(timezone.utc) + timedelta(
            hours=2, minutes=30
        )
        mock_provider = MagicMock()
        mock_provider.load_token.return_value = mock_token
        with patch("cloudctl.config.get_org", return_value={}):
            with patch("cloudctl.providers.get_provider", return_value=mock_provider):
                result = _expiry_label(_CTX)
        assert result is not None
        assert "h" in result
