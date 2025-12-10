# file: tests/test_pagination_and_parsing.py
"""
Targeting low-coverage modules: use_exports, aws pagination, and core error paths.
"""

import json
import subprocess

# [FIX] Import datetime/timezone directly
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from awsctl import aws, core, sso_cache, use_exports

# --- USE_EXPORTS (Currently 17%) ---


def test_redact_args():
    args = ["cmd", "--access-token", "SECRET", "aws_session_token=SECRET", "--other"]
    safe = use_exports._redact_args(args)
    assert "SECRET" not in safe
    assert "REDACTED" in safe
    assert "--other" in safe


def test_aws_json_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 1)):
        with pytest.raises(SystemExit):
            use_exports._aws_json(["cmd"])


def test_aws_json_invalid_json():
    mock_proc = MagicMock(returncode=0, stdout="{bad")
    with patch("subprocess.run", return_value=mock_proc):
        with pytest.raises(SystemExit):
            use_exports._aws_json(["cmd"])


# --- AWS (Currently 57%) ---


def test_sso_list_account_roles_pagination(monkeypatch):
    """Test pagination for roles."""
    p1 = {"roleList": [{"roleName": "R1"}], "nextToken": "n"}
    p2 = {"roleList": [{"roleName": "R2"}]}

    def side_effect(args, **kwargs):
        if "n" in args:  # If next token passed
            return MagicMock(returncode=0, stdout=json.dumps(p2), stderr="")
        return MagicMock(returncode=0, stdout=json.dumps(p1), stderr="")

    monkeypatch.setattr(aws, "run_aws", side_effect)

    roles = aws.sso_list_account_roles("u", "1", "r")
    assert len(roles) == 2
    assert "R1" in roles
    assert "R2" in roles


def test_sso_list_account_roles_error(monkeypatch):
    monkeypatch.setattr(aws, "run_aws", lambda a: MagicMock(returncode=1, stderr="F"))
    with pytest.raises(RuntimeError):
        aws.sso_list_account_roles("u", "1", "r")


# --- CORE (Currently 61%) ---


def test_cmd_exec_token_expiry(monkeypatch, mock_rich_console):
    """Test session expiry during exec."""
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )

    # [FIX] Use standard datetime
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a: token)

    # Mock AWS CLI returning ExpiredToken exception
    monkeypatch.setattr(
        "awsctl.use_exports._aws_json",
        MagicMock(side_effect=SystemExit("ExpiredToken")),
    )

    assert core.cmd_exec(None, None, None, ["ls"]) == 1
    assert "Session expired" in "".join(mock_rich_console.captured)
