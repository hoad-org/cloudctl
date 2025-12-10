# file: tests/test_setup_wizard_errors.py
import os
import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from awsctl import registry, shell, utils, wizard


# [FIX] Skip on Windows
@pytest.mark.skipif(os.name == "nt", reason="Sudo/chown logic is Posix only")
# [FIX] Skip on Windows
@pytest.mark.skipif(os.name == "nt", reason="Sudo/chown logic is Posix only")
def test_inject_shell_no_sudo_uid(monkeypatch, tmp_path):
    rc = tmp_path / ".bashrc"
    rc.touch()
    if hasattr(os, "geteuid"):
        monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_UID", raising=False)
    with patch("os.chown") as mock_chown:
        shell.inject_shell_function(rc)
        mock_chown.assert_not_called()


def test_wizard_write_fail(monkeypatch, tmp_path, mock_rich_console):
    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(registry, "get_choices", lambda: [])
    monkeypatch.setattr("awsctl.wizard.inquirer.checkbox", lambda **k: mock_cb)

    conf = tmp_path / "orgs.yaml"
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=True: conf)

    with patch("tempfile.mkstemp", side_effect=OSError("Write Fail")):
        assert wizard.run_wizard() is False

    assert "Failed to write config" in "".join(mock_rich_console.captured)


def test_wizard_cli_sync_fail(monkeypatch, tmp_path, mock_rich_console):
    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(registry, "get_choices", lambda: [])
    monkeypatch.setattr("awsctl.wizard.inquirer.checkbox", lambda **k: mock_cb)

    monkeypatch.setattr(
        "awsctl.config.get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml"
    )
    monkeypatch.setattr(
        "awsctl.core.cmd_config_sync", MagicMock(side_effect=Exception("Sync Fail"))
    )
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr("awsctl.shell.inject_shell_function", lambda x: True)

    assert wizard.run_wizard() is True
    assert "Failed to sync profiles" in "".join(mock_rich_console.captured)


# [FIX] Skip on Windows to avoid crashing Pytest internals with os.name patching
@pytest.mark.skipif(os.name == "nt", reason="os.killpg is Posix only")
def test_run_new_session_kill(monkeypatch):
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.side_effect = subprocess.TimeoutExpired(["cmd"], 1)
        proc.pid = 999
        mock_popen.return_value.__enter__.return_value = proc

        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=999):
                with pytest.raises(RuntimeError):
                    utils.run(["sleep"], timeout=0.1, capture=True)

                mock_killpg.assert_called_with(999, signal.SIGKILL)
