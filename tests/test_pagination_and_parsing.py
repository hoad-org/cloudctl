# file: tests/test_pagination_and_parsing.py
"""
Targeting low-coverage modules: use_exports, aws pagination, and core error paths.
"""

import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import aws, core, sso_cache, use_exports

# --- USE_EXPORTS (Security & Parsing) ---


def test_redact_args():
    """Verify sensitive tokens are scrubbed from argument lists."""
    args = ["cmd", "--access-token", "SECRET", "aws_session_token=SECRET", "--other"]
    safe = use_exports._redact_args(args)
    assert "SECRET" not in safe
    # Implementation should replace secrets with the literal string 'REDACTED'
    assert any("REDACTED" in arg for arg in safe)
    assert "--other" in safe


def test_aws_json_timeout():
    """Verify subprocess timeouts trigger a SystemExit(1)."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 1)):
        with pytest.raises(SystemExit) as e:
            use_exports._aws_json(["cmd"])
        assert e.value.code == 1


def test_aws_json_invalid_json():
    """Verify malformed JSON from AWS CLI triggers SystemExit."""
    # We mock a successful returncode but corrupted stdout
    mock_proc = MagicMock(returncode=0, stdout="{bad_json: missing_quotes")
    with patch("subprocess.run", return_value=mock_proc):
        with pytest.raises(SystemExit):
            use_exports._aws_json(["cmd"])


# --- AWS (Pagination Logic) ---


def test_sso_list_account_roles_pagination(monkeypatch):
    """Test recursive/loop pagination for IAM roles."""
    p1 = {"roleList": [{"roleName": "R1"}], "nextToken": "n"}
    p2 = {"roleList": [{"roleName": "R2"}]}

    # Correct signature for run_aws includes capturing the args
    def side_effect(args):
        if "--next-token" in args:
            return {"returncode": 0, "stdout": json.dumps(p2), "stderr": ""}
        return {"returncode": 0, "stdout": json.dumps(p1), "stderr": ""}

    monkeypatch.setattr(aws, "run_aws", side_effect)

    # [FIX] Implementation requires a token object, not just a URL
    mock_token = sso_cache.SsoToken("tok", "url", "reg", datetime.now(), {})

    roles = aws.sso_list_account_roles(mock_token, "123456789012")
    assert len(roles) == 2
    assert any(r["roleName"] == "R1" for r in roles)
    assert any(r["roleName"] == "R2" for r in roles)


def test_sso_list_account_roles_error(monkeypatch):
    """Verify RuntimeError is raised on AWS CLI non-zero exit."""
    monkeypatch.setattr(
        aws, "run_aws", lambda a: {"returncode": 1, "stderr": "AccessDenied"}
    )

    mock_token = sso_cache.SsoToken("tok", "url", "reg", datetime.now(), {})
    with pytest.raises(RuntimeError) as e:
        aws.sso_list_account_roles(mock_token, "123456789012")
    assert "AccessDenied" in str(e.value)


# --- CORE (Error Interception) ---


def test_cmd_exec_token_expiry(monkeypatch, mock_rich_console):
    """Test session expiry handling during command execution."""
    # 1. Setup Active Context
    monkeypatch.setattr(
        "cloudctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "cloudctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )

    # 2. Setup Valid Token
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("cloudctl.core.load_active_sso_token", lambda *a: token)

    # 3. Mock AWS CLI returning ExpiredToken exception
    # [FIX] core.cmd_exec catches SystemExit and looks for the message in e.code or stderr
    monkeypatch.setattr(
        "cloudctl.use_exports.emit_exports",
        MagicMock(side_effect=SystemExit("ExpiredToken")),
    )

    # 4. Assert Command Returns Failure (1)
    assert core.cmd_exec(None, None, None, ["ls"]) == 1

    # 5. Verify the user-friendly error message
    output = "".join(mock_rich_console.captured)
    assert "Session expired" in output
