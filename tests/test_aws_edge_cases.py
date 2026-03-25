# file: tests/test_aws_edge_cases.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from awsctl import aws, core, sso_cache, utils


def test_sso_token_validation_branches(tmp_path, monkeypatch):
    """Verify robust skipping of oversized or corrupted cache files."""
    monkeypatch.setattr(aws, "SSO_CACHE_DIR", tmp_path)
    # 1. Create a file exceeding MAX_REGISTRY_SIZE (simulated for sso_cache)
    (tmp_path / "big.json").write_bytes(b"0" * (1024 * 1024 + 100))
    # 2. Create a malformed JSON file
    (tmp_path / "bad.json").write_text("{bad")

    org = sso_cache.OrgRef("test", "https://target", "eu-west-1")

    # Implementation should skip these and return None (no valid token found)
    assert (
        sso_cache.load_active_sso_token(org, cache_dir=tmp_path, raise_error=False)
        is None
    )


def test_aws_parse_iso8601_bad_input():
    """Verify ISO8601 parsing handles Zulu time and bad inputs gracefully."""
    # [FIX] If input is invalid, implementation should catch ValueError and return None
    assert aws._parse_iso8601("not-a-date") is None

    dt = aws._parse_iso8601("2023-01-01T12:00:00Z")
    assert dt.year == 2023
    assert dt.tzinfo is not None


def test_utils_run_encoding_fallback():
    """Verify utils.run handles output correctly using the dict return structure."""
    # [FIX] Implementation uses subprocess.run, not Popen
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="output", stderr="error", returncode=0)
        res = utils.run(["cmd"])
        # res is a dict: {"stdout": ..., "stderr": ..., "returncode": ...}
        assert res["stdout"] == "output"


def test_utils_run_no_check():
    """Verify return code is preserved when check=False."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="out", stderr="err", returncode=1)
        res = utils.run(["cmd"], check=False)
        assert res["returncode"] == 1


def test_core_login_subprocess_error(mock_rich_console, monkeypatch):
    """Verify error reporting when the underlying AWS SSO process fails."""
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    monkeypatch.setattr("awsctl.aws.ensure_sso_base_profile", lambda x: "prof")
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: None)

    # Simulate a generic failure in the run utility
    monkeypatch.setattr(
        "awsctl.utils.run", MagicMock(side_effect=Exception("Subprocess Fail"))
    )

    assert core.cmd_login("o") == 1
    # [FIX] Unified console capture
    assert "Login failed" in "".join(mock_rich_console.captured)


def test_cmd_exec_missing_creds(mock_rich_console, monkeypatch):
    """Test exec behavior when AWS returns empty or malformed credentials."""
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})

    # [FIX] core module now re-exports load_active_sso_token from sso_cache
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: token)

    # Simulate AWS CLI returning empty JSON/dict
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: {})

    assert core.cmd_exec("1", "r", "r", ["ls"]) == 1
    assert "Failed to get credentials" in "".join(mock_rich_console.captured)


def test_cmd_exec_subprocess_fail(mock_rich_console, monkeypatch):
    """Test standard error trapping when os.execvpe fails to find the command."""
    monkeypatch.setattr(
        "awsctl.context_manager.load_context",
        lambda: {"current_org": "o", "account": "1", "role": "r", "region": "r"},
    )
    monkeypatch.setattr(
        "awsctl.config.get_org",
        lambda x: {"name": "o", "sso_start_url": "u", "sso_region": "r"},
    )
    token = sso_cache.SsoToken("t", "u", "r", datetime.now(timezone.utc), {})
    monkeypatch.setattr("awsctl.core.load_active_sso_token", lambda *a, **k: token)

    creds = {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "ST",
        }
    }
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda cmd: creds)

    # Fail execution with FileNotFoundError (Standard code 127)
    with patch("os.execvpe", side_effect=FileNotFoundError):
        # Pass explicit arguments as expected by cmd_exec signature
        assert core.cmd_exec("1", "r", "r", ["missing-cmd"]) == 127

    assert "Command not found" in "".join(mock_rich_console.captured)
