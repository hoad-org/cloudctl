# file: tests/test_version_and_hooks.py
# SPDX-License-Identifier: MIT
"""
Supplemental tests to close coverage gaps.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# [FIX] Removed _version_cli import as the file was deleted
from awsctl import use_exports
from awsctl.plugins import call_hook, load_plugins
from awsctl.sso_cache import SsoToken


def test_plugins_lifecycle():
    assert load_plugins([]) == []
    assert load_plugins(None) == []
    call_hook([], "foo")
    dummy = MagicMock()
    call_hook([dummy], "pre_login", arg="val")
    dummy.pre_login.assert_called_with(arg="val")

    class Empty:
        pass

    call_hook([Empty()], "pre_login")


def test_aws_json_success(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"key": "val"}'
    monkeypatch.setattr("subprocess.run", mock_run)
    res = use_exports._aws_json(["cmd"])
    assert res == {"key": "val"}


def test_aws_json_failure(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "error output"
    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(SystemExit) as e:
        use_exports._aws_json(["cmd"])
    assert "AWS CLI failed" in str(e.value)


def test_emit_exports_success(monkeypatch):
    mock_token = SsoToken("tok", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr(
        "awsctl.use_exports.load_active_sso_token", lambda o: mock_token
    )

    creds = {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "ST",
        }
    }
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda args: creds)

    org = MagicMock()
    org.name = "btavm"
    org.region = "us-east-1"

    out = use_exports.emit_exports(org, "123", "role", "us-east-1")
    # [FIX] shlex.quote("AK") -> "AK" (no quotes).
    assert "export AWS_ACCESS_KEY_ID=AK" in out


def test_emit_exports_no_token(monkeypatch):
    monkeypatch.setattr("awsctl.use_exports.load_active_sso_token", lambda o: None)
    org = MagicMock()
    org.name = "btavm"
    with pytest.raises(SystemExit) as e:
        use_exports.emit_exports(org, "123", "role", "r")
    assert "No valid SSO token" in str(e.value)


def test_emit_exports_no_creds(monkeypatch):
    mock_token = SsoToken("tok", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr(
        "awsctl.use_exports.load_active_sso_token", lambda o: mock_token
    )
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda args: {})
    org = MagicMock()
    with pytest.raises(SystemExit) as e:
        use_exports.emit_exports(org, "123", "role", "r")
    assert "No role credentials" in str(e.value)
