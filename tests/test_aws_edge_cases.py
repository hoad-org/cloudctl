# file: tests/test_aws_edge_cases.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from awsctl import aws, core, sso_cache, utils


def test_sso_token_validation_branches(tmp_path, monkeypatch):
    monkeypatch.setattr(aws, "SSO_CACHE_DIR", tmp_path)
    (tmp_path / "big.json").write_bytes(b"0" * (1024 * 1024 + 100))
    (tmp_path / "bad.json").write_text("{bad")
    org = sso_cache.OrgRef("test", "https://target", "eu-west-1")
    assert (
        sso_cache.load_active_sso_token(org, cache_dir=tmp_path, raise_error=False)
        is None
    )


def test_aws_parse_iso8601_bad_input():
    assert aws._parse_iso8601("not-a-date") is None
    dt = aws._parse_iso8601("2023-01-01T12:00:00Z")
    assert dt.year == 2023


def test_utils_run_encoding_fallback():
    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.return_value = ("output", "error")
        proc.returncode = 0
        mock_popen.return_value.__enter__.return_value = proc
        res = utils.run(["cmd"])
        assert res.stdout == "output"


def test_utils_run_no_check():
    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.return_value = ("out", "err")
        proc.returncode = 1
        mock_popen.return_value.__enter__.return_value = proc
        res = utils.run(["cmd"], check=False)
        assert res.returncode == 1


def test_core_login_subprocess_error(mock_rich_console, monkeypatch):
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "prof")
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: None)
    monkeypatch.setattr(
        "awsctl.utils.run", MagicMock(side_effect=Exception("Subprocess Fail"))
    )
    assert core.cmd_login("o") == 1
    assert "Login failed" in "".join(mock_rich_console.captured)


def test_cmd_exec_missing_creds(mock_rich_console, monkeypatch):
    """Test exec when AWS CLI returns empty credentials."""
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a: token)

    # Return empty creds
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: {})

    assert core.cmd_exec(None, None, None, ["ls"]) == 1
    assert "Failed to get credentials" in "".join(mock_rich_console.captured)


def test_cmd_exec_subprocess_fail(mock_rich_console, monkeypatch):
    """Test exec when os.execvpe fails."""
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a: token)

    creds = {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "ST",
        }
    }
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: creds)

    # Fail execution
    with patch("os.execvpe", side_effect=FileNotFoundError):
        assert core.cmd_exec(None, None, None, ["missing-cmd"]) == 127

    assert "Command not found" in "".join(mock_rich_console.captured)
