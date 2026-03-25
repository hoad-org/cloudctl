# file: tests/test_setup_wizard_errors.py
import os
import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from awsctl import registry, shell, utils, wizard
from awsctl.wizard import inquirer


# [FIX] Skip on Windows
@pytest.mark.skipif(os.name == "nt", reason="Sudo/chown logic is Posix only")
def test_inject_shell_no_sudo_uid(monkeypatch, tmp_path):
    """Ensure chown is skipped if SUDO_UID is not present."""
    rc = tmp_path / ".bashrc"
    rc.touch()
    if hasattr(os, "geteuid"):
        monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.delenv("SUDO_UID", raising=False)
    with patch("os.chown") as mock_chown:
        shell.inject_shell_function(rc)
        mock_chown.assert_not_called()


def test_wizard_write_fail(monkeypatch, tmp_path, mock_rich_console):
    """Test that the wizard returns False and prints an error when disk write fails."""
    # 1. Setup mocks to bypass prompts
    monkeypatch.setattr("awsctl.registry.get_registry", lambda: [{"name": "org"}])
    monkeypatch.setattr(
        registry, "get_choices", lambda: [{"name": "Org", "value": {"name": "org"}}]
    )

    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_cb)

    # 2. Mock path and force write failure via mkstemp (used for atomic writes)
    conf = tmp_path / "orgs.yaml"
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=True: conf)

    with patch("tempfile.mkstemp", side_effect=OSError("Write Fail")):
        assert wizard.run_wizard() is False

    # 3. Verify capture
    output = "".join(mock_rich_console.captured)
    assert "Failed to update config" in output
    assert "Write Fail" in output


def test_wizard_cli_sync_fail(monkeypatch, tmp_path, mock_rich_console):
    """Test that the wizard continues but reports failure if profile sync fails."""
    monkeypatch.setattr("awsctl.registry.get_registry", lambda: [{"name": "org"}])
    monkeypatch.setattr(
        registry, "get_choices", lambda: [{"name": "Org", "value": {"name": "org"}}]
    )

    mock_cb = MagicMock()
    mock_cb.execute.return_value = [{"name": "org"}]
    monkeypatch.setattr(inquirer, "checkbox", lambda **k: mock_cb)

    # Mock the config path to a real temp location
    monkeypatch.setattr(
        "awsctl.config.get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml"
    )

    # Force the sync command to return non-zero/fail
    monkeypatch.setattr("awsctl.core.cmd_config_sync", MagicMock(return_value=1))
    monkeypatch.setattr("awsctl.shell.detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr("awsctl.shell.inject_shell_function", lambda x: True)

    # If sync fails, the wizard should return False (non-zero exit)
    assert wizard.run_wizard() is False
    assert "Failed to sync profiles" in "".join(mock_rich_console.captured)


@pytest.mark.skipif(os.name == "nt", reason="os.killpg is Posix only")
def test_run_new_session_kill(monkeypatch):
    """Test killpg is called correctly for timeouts."""
    monkeypatch.setattr("os.name", "posix")

    # Implementation uses subprocess.run, so we mock that directly
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 0.1)):
        with patch("os.killpg") as mock_killpg:
            # Implementation uses os.getpgid(0) for session groups
            with patch("os.getpgid", return_value=999):
                with pytest.raises(RuntimeError) as e:
                    utils.run(["sleep"], timeout=0.1, capture=True)

                assert "timed out" in str(e.value).lower()
                mock_killpg.assert_called_with(0, signal.SIGKILL)
