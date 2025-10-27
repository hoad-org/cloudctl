# file: tests/test_smoke.py
import pytest

from awsctl import cli


def test_help_command(capsys):
    cli.cmd_help(None)
    out = capsys.readouterr().out
    assert "awsctl — Navigate" in out or "awsctl — Navigate".split("—")[0] in out
    # Check for the new shell helper example
    assert "awsctl-use --account <id>" in out


@pytest.mark.parametrize("sub", ["setup", "init-config", "help", "doctor"])
def test_entrypoints_do_not_crash(sub, monkeypatch, tmp_path):
    # Mock dependencies for setup/doctor
    monkeypatch.setattr(cli.core, "get_orgs_path", lambda ensure=True: tmp_path / "orgs.yaml")
    monkeypatch.setattr(cli, "detect_shell_profile", lambda: tmp_path / ".zshrc")
    monkeypatch.setattr(cli, "inject_shell_function", lambda rc_file: None)
    monkeypatch.setattr(cli.core, "cmd_config_sync", lambda: 0)

    args = type("Args", (), {})()
    if sub == "setup":
        cli.cmd_setup(args)
    elif sub == "init-config":
        cli.cmd_init_config(args)
    elif sub == "doctor":
        cli.cmd_doctor(args)
    else:
        cli.cmd_help(args)
