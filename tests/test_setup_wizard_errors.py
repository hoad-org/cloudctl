# file: tests/test_setup_wizard_errors.py
import os
import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from cloudctl import shell, utils, wizard
from cloudctl.wizard import inquirer


def _seq_mock(values):
    """Return an inquirer factory whose .execute() yields *values* in order."""
    it = iter(values)

    def factory(**kw):
        m = MagicMock()
        m.execute.return_value = next(it)
        return m

    return factory


# ---------------------------------------------------------------------------
# Shell-function injection tests (unrelated to wizard flow)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Wizard write failure
# ---------------------------------------------------------------------------


def test_wizard_write_fail(monkeypatch, tmp_path, mock_rich_console):
    """Wizard returns False and reports error when mkstemp fails."""
    mock_org = {"name": "org", "provider": "aws"}
    monkeypatch.setattr(
        "cloudctl.wizard._load_registry_choices",
        lambda: [{"name": "Org", "value": mock_org}],
    )

    # checkbox: providers → ["aws"], registry → [mock_org]
    monkeypatch.setattr(inquirer, "checkbox", _seq_mock([["aws"], [mock_org]]))
    # confirm: no manual, yes save
    monkeypatch.setattr(inquirer, "confirm", _seq_mock([False, True]))

    from cloudctl import core
    monkeypatch.setattr(core, "get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml")

    with patch("tempfile.mkstemp", side_effect=OSError("Write Fail")):
        assert wizard.run_wizard() is False

    output = "".join(mock_rich_console.captured)
    assert "Failed to write config" in output
    assert "Write Fail" in output


# ---------------------------------------------------------------------------
# AWS profile sync failure — non-fatal warning
# ---------------------------------------------------------------------------


def test_wizard_cli_sync_fail(monkeypatch, tmp_path, mock_rich_console):
    """Sync failure is surfaced as a warning; wizard still returns True."""
    mock_org = {"name": "org", "provider": "aws"}
    monkeypatch.setattr(
        "cloudctl.wizard._load_registry_choices",
        lambda: [{"name": "Org", "value": mock_org}],
    )

    # checkbox: providers → ["aws"], registry → [mock_org]
    monkeypatch.setattr(inquirer, "checkbox", _seq_mock([["aws"], [mock_org]]))
    # confirm: no manual, yes save, yes shell
    monkeypatch.setattr(inquirer, "confirm", _seq_mock([False, True, True]))

    from cloudctl import core
    monkeypatch.setattr(core, "get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml")
    monkeypatch.setattr(core, "cmd_config_sync", MagicMock(return_value=1))
    monkeypatch.setattr(shell, "detect_shell_profile", lambda: tmp_path / "rc")
    monkeypatch.setattr(shell, "inject_shell_function", lambda x: True)

    # Sync failure is a warning — wizard succeeds overall
    assert wizard.run_wizard() is True

    output = "".join(mock_rich_console.captured)
    # Warning must be surfaced to the user
    assert "cloudctl doctor" in output


# ---------------------------------------------------------------------------
# Process-kill on timeout
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="os.killpg is Posix only")
def test_run_new_session_kill(monkeypatch):
    """killpg is called correctly on subprocess timeout."""
    monkeypatch.setattr("os.name", "posix")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["cmd"], 0.1)):
        with patch("os.killpg") as mock_killpg:
            with patch("os.getpgid", return_value=999):
                with pytest.raises(RuntimeError) as exc:
                    utils.run(["sleep"], timeout=0.1, capture=True)

                assert "timed out" in str(exc.value).lower()
                mock_killpg.assert_called_with(999, signal.SIGKILL)
