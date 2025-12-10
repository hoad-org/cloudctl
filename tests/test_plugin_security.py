# file: tests/test_plugin_security.py
"""
Aggressive coverage tests to reach 90%.
"""

import builtins
import os
import subprocess

# [FIX] Alias concurrent TimeoutError so it doesn't shadow builtin
from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import MagicMock, patch

import pytest

from awsctl import aws, plugins, sso_cache, utils


def test_plugin_security_block(mock_rich_console):
    with pytest.raises(SystemExit):
        plugins.load_plugins(["evil.plugin"])
    assert "Blocked illegal plugin" in "".join(mock_rich_console.captured)


def test_plugin_import_error(mock_rich_console):
    with pytest.raises(SystemExit):
        plugins.load_plugins(["awsctl.plugins.missing"])
    assert "Failed to load" in "".join(mock_rich_console.captured)


def test_plugin_timeout(mock_rich_console):
    with patch("concurrent.futures.ThreadPoolExecutor.submit") as mock_submit:
        mock_future = MagicMock()
        # [FIX] Use the exact exception class
        mock_future.result.side_effect = FutureTimeoutError()
        mock_submit.return_value = mock_future
        mod = MagicMock()
        mod.hook = lambda: None

        with pytest.raises(SystemExit):
            plugins.call_hook([mod], "hook")

    assert "timed out" in "".join(mock_rich_console.captured)


def test_safe_exec_signature_mismatch(mock_rich_console):
    def weak_hook():
        pass

    plugins._safe_exec(weak_hook, "arg")
    assert "signature mismatch" in "".join(mock_rich_console.captured)


def test_force_stderr_no_tty(monkeypatch):
    monkeypatch.setattr("os.isatty", lambda fd: False)
    with utils.ForceStderr():
        pass


# [FIX] Skip on Windows to avoid crashing Pytest internals with os.name patching
@pytest.mark.skipif(os.name == "nt", reason="Posix only")
def test_run_timeout_kill(monkeypatch):
    # [FIX] Mock os.name safely
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(["cmd"], 1)
        proc.pid = 123
        mock_popen.return_value.__enter__.return_value = proc

        # [FIX] Mock killpg to avoid PermissionError on Mac/Linux CI runners
        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=123):
                with pytest.raises(RuntimeError):
                    utils.run(["sleep", "10"], timeout=0.1)

                mock_killpg.assert_called()


def test_normalize_url_variations():
    assert sso_cache._normalize_start_url("http://example.com") == "http://example.com"
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
    with patch("pathlib.Path.glob", side_effect=OSError("Perm Denied")):
        with pytest.raises(RuntimeError) as e:
            sso_cache.load_active_sso_token(
                sso_cache.OrgRef("n", "u", "r"), cache_dir=bad_dir
            )
        assert "Permission denied" in str(e.value)


def test_config_lock_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("awsctl.aws.AWS_CONFIG", tmp_path / "config")
    (tmp_path / "config.lock").touch()

    # [FIX] Use builtins.TimeoutError (not concurrent.futures.TimeoutError)
    # [FIX] Ensure time side effects are sufficient for loop
    with patch("time.time", side_effect=[0, 10, 20, 30]):
        with pytest.raises(builtins.TimeoutError):
            with aws._config_file_lock(timeout=1):
                pass


def test_unsafe_config_check(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.write_text("include = /etc/passwd\n[default]\n")
    monkeypatch.setattr("awsctl.aws.AWS_CONFIG", cfg)
    with pytest.raises(RuntimeError) as e:
        aws._check_unsafe_config()
    assert "contains 'include' directives" in str(e.value)
