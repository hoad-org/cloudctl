# file: tests/test_setup.py
from unittest.mock import MagicMock

from awsctl import cli


def test_cmd_setup_runs(monkeypatch, tmp_path):
    orgs = tmp_path / "orgs.yaml"
    orgs.write_text("orgs: []")
    monkeypatch.setattr("awsctl.core.get_orgs_path", lambda ensure=True: orgs)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")

    # Mock preflights
    monkeypatch.setattr(
        cli,
        "preflight_checks",
        lambda: [
            {"tool": "aws", "cmd": "aws", "ok": True},
            {"tool": "jq", "cmd": "jq", "ok": True},
            {"tool": "python3", "cmd": "python3", "ok": True},
        ],
    )

    # Mock shell setup functions
    mock_detect = MagicMock(return_value=tmp_path / ".zshrc")
    mock_inject = MagicMock()
    monkeypatch.setattr(cli, "detect_shell_profile", mock_detect)
    monkeypatch.setattr(cli, "inject_shell_function", mock_inject)
    monkeypatch.setattr(cli.core, "cmd_config_sync", MagicMock())

    cli.cmd_setup(None)

    # Verify setup installed the shell function
    mock_inject.assert_called_once_with(tmp_path / ".zshrc")
