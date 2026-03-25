# file: tests/test_version_and_hooks.py
# SPDX-License-Identifier: MIT
"""
Supplemental tests to close coverage gaps.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from awsctl import use_exports
from awsctl.plugins import call_hook, load_plugins
from awsctl.sso_cache import SsoToken


def test_plugins_lifecycle():
    # [FIX] load_plugins returns a dict, not a list.
    assert load_plugins([]) == {}
    assert load_plugins(None) == {}

    call_hook([], "foo")

    dummy = MagicMock()
    # Dummy hook for call_hook to find
    dummy.pre_login = MagicMock(return_value="ok")

    call_hook([dummy], "pre_login", arg="val")
    dummy.pre_login.assert_called_with(arg="val")

    class Empty:
        pass

    # Ensure calling a non-existent hook on an empty class doesn't crash
    call_hook([Empty()], "pre_login")


def test_aws_json_success(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = '{"key": "val"}'
    monkeypatch.setattr("subprocess.run", mock_run)

    res = use_exports._aws_json(["cmd"])
    assert res == {"key": "val"}


def test_aws_json_failure(monkeypatch, capsys):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "error output"
    monkeypatch.setattr("subprocess.run", mock_run)

    # [FIX] SystemExit(1) usually doesn't wrap the string in the exception object
    # when sys.exit("msg") is called; it prints to stderr and exits with 1.
    with pytest.raises(SystemExit):
        use_exports._aws_json(["cmd"])

    captured = capsys.readouterr()
    assert "AWS CLI failed" in captured.err


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
    # Aligned with logic that uses shlex.quote or simple concatenation
    assert "export AWS_ACCESS_KEY_ID=AK" in out


def test_emit_exports_no_token(monkeypatch, capsys):
    monkeypatch.setattr("awsctl.use_exports.load_active_sso_token", lambda o: None)
    org = MagicMock()
    org.name = "btavm"

    with pytest.raises(SystemExit):
        use_exports.emit_exports(org, "123", "role", "r")

    captured = capsys.readouterr()
    assert "No valid SSO token" in captured.out


def test_emit_exports_no_creds(monkeypatch, capsys):
    mock_token = SsoToken("tok", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr(
        "awsctl.use_exports.load_active_sso_token", lambda o: mock_token
    )
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda args: {})
    org = MagicMock()

    with pytest.raises(SystemExit):
        use_exports.emit_exports(org, "123", "role", "r")

    captured = capsys.readouterr()
    assert "No role credentials" in captured.out
