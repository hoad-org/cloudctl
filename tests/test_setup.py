# file: tests/test_setup.py
from unittest.mock import MagicMock

from cloudctl import cli


def test_cmd_setup_runs(monkeypatch, tmp_path, mock_rich_console):
    """
    Verify that the setup command orchestrates the configuration path,
    shell detection, and core setup logic correctly.
    """
    # 1. Setup Mock Filesystem
    orgs = tmp_path / "orgs.yaml"
    orgs.write_text("orgs: []", encoding="utf-8")

    # Patch the config path to use our temporary file
    monkeypatch.setattr("cloudctl.core.get_orgs_path", lambda ensure=True: orgs)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    # 2. Environment Controls
    # Ensure headless mode to prevent browser popups during setup tests
    monkeypatch.setenv("AWSCTL_HEADLESS", "1")

    # 3. Mock Subsystems
    # Mock shell integration to prevent actual disk writes to real shell profiles
    mock_detect = MagicMock(return_value=tmp_path / ".zshrc")
    mock_inject = MagicMock(return_value=True)

    monkeypatch.setattr("cloudctl.shell.detect_shell_profile", mock_detect)
    monkeypatch.setattr("cloudctl.shell.inject_shell_function", mock_inject)

    # 4. Mock Core Actions
    # We patch cli.core specifically to ensure the dispatcher uses our mock
    mock_core_setup = MagicMock(return_value=0)
    monkeypatch.setattr(cli.core, "cmd_setup", mock_core_setup)
    monkeypatch.setattr(cli.core, "cmd_config_sync", MagicMock(return_value=0))

    # 5. Execute Command
    # [FIX] Use a SimpleNamespace or a Mock to simulate the argparse Namespace
    from argparse import Namespace

    args = Namespace()

    # Entry point call
    exit_code = cli.cmd_setup(args)

    # 6. Verifications
    # Ensure the command returned a success code (0)
    assert exit_code == 0
    # Verify that the core setup logic was actually triggered
    mock_core_setup.assert_called_once()


def test_cmd_setup_failure_handling(monkeypatch, tmp_path, mock_rich_console):
    """
    Verify that if the setup wizard fails, the CLI exit code reflects it.
    """
    # Mock core.cmd_setup to return failure (1)
    monkeypatch.setattr(cli.core, "cmd_setup", MagicMock(return_value=1))

    from argparse import Namespace

    args = Namespace()

    exit_code = cli.cmd_setup(args)

    assert exit_code == 1
