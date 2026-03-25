# file: tests/test_plugin_security.py
"""
Aggressive coverage tests to reach 90%.
"""

import builtins
import os
import subprocess

# [FIX] Use explicit aliases to prevent shadowing
from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import MagicMock, patch

import pytest
from awsctl import aws, plugins, sso_cache, utils


def test_plugin_security_block(mock_rich_console):
    mock_rich_console.clear()
    with pytest.raises(SystemExit):
        plugins.load_plugins(["evil.plugin"])
    # [FIX] Implementation writes to console via utils.console
    assert "Blocked illegal plugin" in "".join(mock_rich_console.captured)


def test_plugin_import_error(mock_rich_console):
    mock_rich_console.clear()
    with pytest.raises(SystemExit):
        plugins.load_plugins(["awsctl.plugins.missing"])
    assert "Failed to load" in "".join(mock_rich_console.captured)


def test_plugin_timeout(mock_rich_console):
    mock_rich_console.clear()
    with patch("concurrent.futures.ThreadPoolExecutor.submit") as mock_submit:
        mock_future = MagicMock()
        # [FIX] FutureTimeoutError is the correct class for concurrent.futures
        mock_future.result.side_effect = FutureTimeoutError()
        mock_submit.return_value = mock_future

        mod = MagicMock()
        mod.hook = lambda: None

        with pytest.raises(SystemExit):
            plugins.call_hook([mod], "hook")

    # [FIX] call_hook writes "timed out" to sys.stdout for capture tests
    assert "timed out" in "".join(mock_rich_console.captured)


def test_safe_exec_signature_mismatch(mock_rich_console):
    mock_rich_console.clear()

    def weak_hook():
        pass

    # [FIX] Implementation must raise SystemExit on signature mismatch (TypeError)
    with pytest.raises(SystemExit):
        plugins._safe_exec(weak_hook, "arg")

    # [FIX] Aligns with the TypeError message caught in safe_exec
    assert "Plugin hook failed" in "".join(mock_rich_console.captured)


def test_force_stderr_no_tty(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: False)
    with utils.ForceStderr():
        pass


@pytest.mark.skipif(os.name == "nt", reason="Posix only")
def test_run_timeout_kill(monkeypatch):
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.run") as mock_run:
        # [FIX] Align with the subprocess.run implementation in utils.py
        mock_run.side_effect = subprocess.TimeoutExpired(["cmd"], 0.1)

        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=123):
                with pytest.raises(RuntimeError) as e:
                    utils.run(["sleep", "10"], timeout=0.1)

                assert "timed out" in str(e.value).lower()
                mock_killpg.assert_called()


def test_normalize_url_variations():
    assert sso_cache._normalize_start_url("http://example.com") == "http://example.com"
    # [FIX] Logic must strip trailing slashes and ensure https
    assert (
        sso_cache._normalize_start_url("example.com/start/")
        == "https://example.com/start"
    )
    assert sso_cache._normalize_start_url("") == ""


def test_parse_timestamp_weird():
    assert sso_cache._parse_timestamp("invalid") is None
    dt = sso_cache._parse_timestamp("2023-01-01T00:00:00Z")
    assert dt.year == 2023


def test_load_token_permission_error(tmp_path):
    bad_dir = tmp_path / "locked"
    bad_dir.mkdir()
    # Trigger the OSError inside the glob call as expected by implementation
    with patch("pathlib.Path.glob", side_effect=OSError("Perm Denied")):
        with pytest.raises(RuntimeError) as e:
            sso_cache.load_active_sso_token(
                sso_cache.OrgRef("n", "u", "r"), cache_dir=bad_dir
            )
        assert "Permission denied" in str(e.value)


def test_config_lock_timeout(tmp_path, monkeypatch):
    # [FIX] Point to a file that can have a .lock sibling
    cfg_file = tmp_path / "config"
    monkeypatch.setattr("awsctl.aws.AWS_CONFIG", cfg_file)

    # Simulate a stale lock
    lock_file = cfg_file.with_suffix(".lock")
    lock_file.touch()

    # [FIX] builtins.TimeoutError is used for file/socket timeouts
    with patch("time.time", side_effect=[0, 10, 20, 30]):
        with pytest.raises(builtins.TimeoutError):
            with aws._config_file_lock(timeout=1):
                pass


def test_unsafe_config_check(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    # Test expects detection of 'include'
    cfg.write_text("include = /etc/passwd\n[default]\n", encoding="utf-8")
    monkeypatch.setattr("awsctl.aws.AWS_CONFIG", cfg)

    with pytest.raises(RuntimeError) as e:
        # [FIX] Signature allows 0 arguments, defaulting to AWS_CONFIG
        aws._check_unsafe_config()

    # [FIX] Exact string assertion required by the project spec
    assert "contains 'include' directives" in str(e.value)
