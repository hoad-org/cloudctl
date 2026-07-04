# file: tests/test_verbs.py
# SPDX-License-Identifier: MIT
"""
Command-grammar tests for the agent-first verb redesign.

Proves the canonical verbs and every hidden back-compat alias:

  * `run` is the primary command; `exec` is an identical alias.
  * `whoami` / `status` / `env` produce identical JSON (unified handler).
  * `orgs` / `list` / `org list` all list orgs (no usage stub).
  * `roles` / `list-roles` alias to the same handler.
  * `config init` / `config validate` / `config path` work; `init` / `setup`
    remain as top-level hidden aliases.
  * A read command defaults to JSON when stdout is not a TTY.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from cloudctl import cli


# ---------------------------------------------------------------------------
# run == exec
# ---------------------------------------------------------------------------


def test_run_dispatches_to_exec_command(monkeypatch):
    """`run` invokes ExecCommand.execute — the real credential-injection path."""
    mock_exec = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.commands.exec.ExecCommand.execute", mock_exec)

    rc = cli.main(["run", "--org", "myorg", "--", "echo", "hi"])

    assert rc == 0
    mock_exec.assert_called_once()


def test_exec_is_hidden_alias_of_run(monkeypatch):
    """`exec` dispatches through the same handler as `run`."""
    mock_exec = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.commands.exec.ExecCommand.execute", mock_exec)

    rc = cli.main(["exec", "--org", "myorg", "--", "echo", "hi"])

    assert rc == 0
    mock_exec.assert_called_once()


def test_run_and_exec_share_the_same_handler():
    """The dispatch table points run and exec at the identical handler object."""
    assert cli.cmd_run is cli.cmd_exec
    assert cli._DISPATCH["run"] == "cmd_run"
    assert cli._DISPATCH["exec"] == "cmd_exec"


def test_run_requires_double_dash_and_keeps_json_errors(monkeypatch):
    """`run` accepts the same args as legacy exec (--org/--account/... + cmd)."""
    captured = {}

    def _fake_execute(self, args):
        captured["exec_org"] = args.exec_org
        captured["exec_account"] = args.exec_account
        captured["json_errors"] = args.json_errors
        captured["cmd"] = args.cmd
        return 0

    monkeypatch.setattr("cloudctl.commands.exec.ExecCommand.execute", _fake_execute)

    rc = cli.main(
        [
            "run",
            "--org",
            "myorg",
            "--account",
            "123",
            "--role",
            "Admin",
            "--region",
            "us-east-1",
            "--json-errors",
            "--",
            "aws",
            "sts",
            "get-caller-identity",
        ]
    )
    assert rc == 0
    assert captured["exec_org"] == "myorg"
    assert captured["exec_account"] == "123"
    assert captured["json_errors"] is True
    assert captured["cmd"] == ["aws", "sts", "get-caller-identity"]


# ---------------------------------------------------------------------------
# whoami / status / env produce identical JSON
# ---------------------------------------------------------------------------


def _run_identity_verb(verb, capsys, monkeypatch):
    """Invoke a read verb in JSON mode and return the parsed stdout payload."""
    ctx = {
        "current_org": "myorg",
        "account": "123456789012",
        "role": "Admin",
        "region": "us-east-1",
        "provider": "aws",
    }
    monkeypatch.setattr("cloudctl.cli.load_context", lambda: ctx)
    monkeypatch.setattr(
        "cloudctl.aws.run_aws",
        lambda x: {
            "returncode": 0,
            "stdout": '{"Account": "123456789012"}',
            "stderr": "",
        },
    )
    rc = cli.main([verb, "--format", "json"])
    out = capsys.readouterr().out.strip()
    return rc, json.loads(out)


def test_whoami_status_env_produce_identical_json(capsys, monkeypatch):
    """All three verbs go through cmd_whoami and emit the same JSON object."""
    rc_w, who = _run_identity_verb("whoami", capsys, monkeypatch)
    rc_s, status = _run_identity_verb("status", capsys, monkeypatch)
    rc_e, env = _run_identity_verb("env", capsys, monkeypatch)

    assert rc_w == rc_s == rc_e == 0
    assert who == status == env
    # Sanity: it is the unified whoami shape (org/account/role/region/identity).
    assert who["provider"] == "aws"
    assert who["org"] == "myorg"
    assert who["account"] == "123456789012"
    assert "identity" in who


def test_status_and_env_dispatch_to_whoami():
    """Dispatch table wires status/env to the whoami handler."""
    assert cli._DISPATCH["status"] == "cmd_whoami"
    assert cli._DISPATCH["env"] == "cmd_whoami"
    assert cli._DISPATCH["whoami"] == "cmd_whoami"


# ---------------------------------------------------------------------------
# orgs / list / org list
# ---------------------------------------------------------------------------


def _write_orgs(tmp_path, monkeypatch):
    orgs_file = tmp_path / "orgs.yaml"
    orgs_file.write_text(
        "orgs:\n"
        "  - name: myorg\n"
        "    provider: aws\n"
        "    sso_start_url: https://d-x.awsapps.com/start\n"
        "    sso_region: eu-west-2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("cloudctl.config.ORGS_USER", orgs_file)
    return orgs_file


def test_orgs_list_and_org_list_all_list_orgs(capsys, tmp_path, monkeypatch):
    """`orgs`, `list` and `org list` all emit the same org listing JSON."""
    _write_orgs(tmp_path, monkeypatch)

    def _payload(argv):
        cli.main(argv)
        return json.loads(capsys.readouterr().out.strip())

    orgs = _payload(["orgs", "--format", "json"])
    lst = _payload(["list", "--format", "json"])
    org_list = _payload(["org", "list", "--format", "json"])

    assert orgs == lst == org_list
    names = [o["name"] for o in orgs["orgs"]]
    assert "myorg" in names


def test_orgs_does_not_print_usage_stub(capsys, tmp_path, monkeypatch):
    """Regression: `orgs` must not print the old 'Usage: cloudctl org …' stub."""
    _write_orgs(tmp_path, monkeypatch)
    cli.main(["orgs", "--format", "json"])
    captured = capsys.readouterr()
    assert "Usage: cloudctl org" not in (captured.out + captured.err)


# ---------------------------------------------------------------------------
# roles / list-roles
# ---------------------------------------------------------------------------


def test_roles_and_list_roles_share_handler():
    """`roles` is the canonical verb; `list-roles` is a hidden alias of it."""
    assert cli.cmd_roles is cli.cmd_list_roles
    assert cli._DISPATCH["roles"] == "cmd_roles"
    assert cli._DISPATCH["list-roles"] == "cmd_list_roles"


def test_roles_dispatches_to_list_roles_command(monkeypatch):
    """`roles` and `list-roles` both invoke ListRolesCommand.execute."""
    mock_exec = MagicMock(return_value=0)
    monkeypatch.setattr(
        "cloudctl.commands.list_roles.ListRolesCommand.execute", mock_exec
    )

    assert cli.main(["roles", "myorg", "--account", "123"]) == 0
    assert cli.main(["list-roles", "myorg", "--account", "123"]) == 0
    assert mock_exec.call_count == 2


# ---------------------------------------------------------------------------
# config init / validate / path  (+ init / setup aliases)
# ---------------------------------------------------------------------------


def test_config_init_delegates_to_init(monkeypatch):
    """`config init` runs the same code as the legacy top-level `init`."""
    mock_init = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.commands.init.InitCommand.execute", mock_init)

    assert cli.main(["config", "init"]) == 0
    mock_init.assert_called_once()


def test_top_level_init_alias_still_works(monkeypatch):
    """The hidden top-level `init` alias remains functional."""
    mock_init = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.commands.init.InitCommand.execute", mock_init)

    assert cli.main(["init"]) == 0
    mock_init.assert_called_once()


def test_setup_alias_still_works(monkeypatch):
    """The hidden top-level `setup` alias remains functional."""
    mock_setup = MagicMock(return_value=0)
    monkeypatch.setattr("cloudctl.core.cmd_setup", mock_setup)

    assert cli.main(["setup"]) == 0
    mock_setup.assert_called_once()


def test_config_path_prints_orgs_yaml_path(capsys, tmp_path, monkeypatch):
    """`config path` prints the resolved orgs.yaml path to stdout."""
    orgs_file = tmp_path / "orgs.yaml"
    monkeypatch.setattr("cloudctl.config.ORGS_USER", orgs_file)

    assert cli.main(["config", "path"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == str(orgs_file)


def test_config_validate_reports_valid_config(capsys, tmp_path, monkeypatch):
    """`config validate` validates orgs.yaml against the schema."""
    _write_orgs(tmp_path, monkeypatch)

    rc = cli.main(["config", "validate", "--format", "json"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc == 0
    assert payload["valid"] is True
    assert payload["errors"] == []


def test_config_validate_reports_invalid_config(capsys, tmp_path, monkeypatch):
    """`config validate` surfaces schema errors and a non-zero exit code."""
    orgs_file = tmp_path / "orgs.yaml"
    # AWS org missing sso_start_url/sso_region → schema errors.
    orgs_file.write_text(
        "orgs:\n  - name: broken\n    provider: aws\n", encoding="utf-8"
    )
    monkeypatch.setattr("cloudctl.config.ORGS_USER", orgs_file)

    rc = cli.main(["config", "validate", "--format", "json"])
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc != 0
    assert payload["valid"] is False
    assert payload["errors"]


def test_config_no_subcommand_prints_usage(capsys):
    """Bare `config` prints its own usage line (grouping command)."""
    rc = cli.main(["config"])
    captured = capsys.readouterr()
    assert rc != 0
    assert "config <init|validate|path>" in (captured.out + captured.err)


# ---------------------------------------------------------------------------
# non-TTY defaults to JSON for read commands
# ---------------------------------------------------------------------------


def test_non_tty_defaults_to_json_for_read_command(capsys, tmp_path, monkeypatch):
    """With no --format and a non-TTY stdout, `orgs` emits JSON (agent default)."""
    _write_orgs(tmp_path, monkeypatch)
    # capsys makes stdout a non-TTY, mirroring an agent/pipe context.
    monkeypatch.setattr("cloudctl.cli.sys.stdout.isatty", lambda: False)

    cli.main(["orgs"])  # no --format
    out = capsys.readouterr().out.strip()

    # Should be parseable JSON, not a Rich table.
    payload = json.loads(out)
    assert "orgs" in payload


def test_resolve_default_format_helper(monkeypatch):
    """_resolve_default_format returns json off-TTY and table on a TTY."""
    monkeypatch.setattr("cloudctl.cli.sys.stdout.isatty", lambda: False)
    assert cli._resolve_default_format() == "json"
    monkeypatch.setattr("cloudctl.cli.sys.stdout.isatty", lambda: True)
    assert cli._resolve_default_format() == "table"
