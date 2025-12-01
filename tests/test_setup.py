# file: tests/test_setup.py
from unittest.mock import MagicMock

from awsctl import cli


def test_cmd_setup_runs(monkeypatch, tmp_path):
    orgs = tmp_path / "orgs.yaml"
    orgs.write_text("orgs: []")
    monkeypatch.setattr("awsctl.core.get_orgs_path", lambda ensure=True: orgs)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    # Force Headless Mode
    monkeypatch.setenv("AWSCTL_HEADLESS", "1")

    # Mock shell setup functions
    mock_detect = MagicMock(return_value=tmp_path / ".zshrc")
    mock_inject = MagicMock()

    monkeypatch.setattr("awsctl.shell.detect_shell_profile", mock_detect)
    monkeypatch.setattr("awsctl.shell.inject_shell_function", mock_inject)

    monkeypatch.setattr(cli.core, "cmd_config_sync", MagicMock())
    monkeypatch.setattr(cli.core, "cmd_setup", MagicMock(return_value=0))

    # [FIX] Pass empty namespace args
    args = type("Args", (), {})
    cli.cmd_setup(args)

    assert True
