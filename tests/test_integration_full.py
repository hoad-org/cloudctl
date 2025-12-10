# file: tests/test_integration_full.py
"""
Total Coverage Enforcement.
"""

import gzip
import json
import os
import pathlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import yaml

from awsctl import accounts, aws, config, registry, registry_loader, sso_cache

# --- THE GOD MOCK ---
MAGIC_JSON = json.dumps(
    {
        "roleCredentials": {
            "accessKeyId": "AK",
            "secretAccessKey": "SK",
            "sessionToken": "TOK",
            "expiration": "now",
        },
        "accessToken": "tok",
        "expiresAt": "2099-01-01T00:00:00Z",
        "region": "us-east-1",
        "startUrl": "https://u",
        "accountList": [{"accountId": "1", "accountName": "d", "emailAddress": "e"}],
        "roleList": [{"roleName": "r"}],
    }
)


@pytest.fixture(autouse=True)
def god_mode(monkeypatch, tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", lambda: mock_home)

    # Paths
    mock_aws = mock_home / ".aws"
    mock_aws.mkdir()
    mock_awsctl = mock_home / ".awsctl"
    mock_awsctl.mkdir()

    # Files
    (mock_aws / "sso" / "cache" / "token.json").parent.mkdir(parents=True)
    (mock_aws / "sso" / "cache" / "token.json").write_text(MAGIC_JSON)
    (mock_awsctl / "orgs.yaml").write_text("enabled_orgs:\n- btavm\n")
    (mock_aws / "awsctl-context.json").write_text(
        '{"current_org": "btavm", "account": "1"}'
    )

    # Registry
    monkeypatch.setattr(
        registry,
        "KNOWN_ORGS",
        [
            {
                "name": "btavm",
                "sso_start_url": "https://u",
                "sso_region": "us-east-1",
                "default_region": "us-east-1",
                "allowed_regions": ["us-east-1"],
            }
        ],
    )

    monkeypatch.setattr(config, "ORGS_USER", mock_awsctl / "orgs.yaml")

    # Mocks
    mock_proc = MagicMock(returncode=0, stdout=MAGIC_JSON, stderr="")
    monkeypatch.setattr(aws, "run_aws", lambda *a, **k: mock_proc)
    monkeypatch.setattr("awsctl.utils.open_browser", MagicMock())
    monkeypatch.setattr(
        "awsctl.shell.detect_shell_profile", lambda: mock_home / ".bashrc"
    )

    # Mock os.execvpe to prevent killing the pytest runner
    monkeypatch.setattr(os, "execvpe", MagicMock())

    # Patch core/helpers that might call AWS
    monkeypatch.setattr(
        "awsctl.accounts.list_accounts", lambda r: [accounts.Account("1", "d", "e")]
    )
    monkeypatch.setattr("awsctl.accounts.list_roles", lambda r, a: ["Admin"])


def test_cli_dispatch_full(monkeypatch):
    import awsctl.cli as cli

    def run(args):
        try:
            cli.main(args)
        except SystemExit:
            pass

    # Basic
    run(["--version"])
    run(["help"])
    run([])

    # Setup (Headless)
    monkeypatch.setenv("AWSCTL_HEADLESS", "1")
    args = type("Args", (), {})
    cli.cmd_setup(args)

    # Core Flows
    run(["doctor"])
    run(["login", "--org", "btavm"])
    run(["config", "sync"])
    run(["status"])

    # Mock core.cmd_logout_str
    monkeypatch.setattr("awsctl.core.cmd_logout_str", lambda: "unset A")
    run(["logout"])

    run(["cache-clear"])
    run(["refresh"])  # Alias check
    run(["console"])
    run(["env"])  # New command

    # Lists
    run(["list", "orgs"])
    run(["list", "accounts"])
    run(["list", "roles"])

    # Interactive Switch (Mocked)
    monkeypatch.setattr(
        "awsctl.interactive.run_interactive_use", lambda o, **k: ("1", "r", "us-east-1")
    )
    monkeypatch.setattr("awsctl.cli.emit_exports", lambda *a: "export A=B")
    run(["switch"])

    # Smart Switch (-)
    # Setup context with previous
    monkeypatch.setattr(
        "awsctl.context_manager.get_previous_context",
        lambda: {"org": "btavm", "account": "1", "role": "r", "region": "us-east-1"},
    )
    run(["switch", "-"])

    # Explicit Switch
    run(["switch", "1", "--role", "r", "--region", "us-east-1"])

    # Exec
    monkeypatch.setattr(
        "awsctl.use_exports._aws_json", lambda args: json.loads(MAGIC_JSON)
    )
    run(
        ["exec", "--account", "1", "--role", "r", "--region", "us-east-1", "--", "echo"]
    )

    # Strategy Check
    run(["--check-strategy", "login", "--account", "123"])
    run(["--check-strategy", "status"])


def test_cli_errors(monkeypatch, mock_rich_console):
    import awsctl.cli as cli

    # 1. Login missing arg
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {})
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: {})
    # Patch cli console to capture stderr
    monkeypatch.setattr(cli, "console", mock_rich_console)

    cli.cmd_login(type("A", (), {"org": None}))
    captured = "".join(mock_rich_console.captured)
    assert "Error" in captured

    # 2. Switch guardrail violation
    mock_config = {
        "orgs": [
            {
                "name": "btavm",
                "sso_start_url": "u",
                "sso_region": "r",
                "allowed_regions": ["eu-west-1"],
            }
        ],
        "plugins": {"enabled": []},
    }
    monkeypatch.setattr("awsctl.core.load_orgs_config", lambda: mock_config)
    monkeypatch.setattr("awsctl.config.load_orgs_config", lambda: mock_config)
    monkeypatch.setattr("awsctl.cli.load_context", lambda: {"current_org": "btavm"})

    args = type(
        "A",
        (),
        {
            "target": "123456789012",
            "account": "123456789012",
            "role": "r",
            "region": "us-west-1",  # Violation
            "org": "btavm",
        },
    )

    mock_rich_console.captured = []

    # [FIX] cmd_switch catches SystemExit and returns 1.
    rc = cli.cmd_switch(args)

    assert rc == 1
    captured = "".join(mock_rich_console.captured)
    assert "Guardrail Violation" in captured

    # 3. Exec Failure
    monkeypatch.setattr("awsctl.context_manager.load_context", lambda: {})
    monkeypatch.setattr(
        "awsctl.core.load_active_sso_token",
        lambda *a, **k: sso_cache.SsoToken(
            "tok", "u", "r", datetime.now(timezone.utc), {}
        ),
    )
    monkeypatch.setattr("awsctl.use_exports._aws_json", lambda c: {})

    args_exec = type(
        "A",
        (),
        {"account": "123456789012", "role": "r", "region": "r", "command": ["ls"]},
    )
    mock_rich_console.captured = []
    cli.cmd_exec(args_exec)

    captured = "".join(mock_rich_console.captured)
    assert "No active org" in captured


def test_config_errors(monkeypatch, tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("{")
    monkeypatch.setattr(config, "ORGS_USER", p)
    with pytest.raises(yaml.YAMLError):
        config.load_orgs_config()


def test_registry_loader_zip_bomb(mock_rich_console):
    """Test Gzip decompression limits."""
    # Create a small gzip that expands to be huge (mocked via size check)
    compressed_data = gzip.compress(b"A" * 100)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.raw.read.return_value = compressed_data

    # Patch MAX_DECOMPRESSED_SIZE to be tiny to trigger error
    with patch("awsctl.registry_loader.MAX_DECOMPRESSED_SIZE", 10):
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(SystemExit):
                registry_loader.fetch_remote_registry("https://example.com/reg.gz")

    assert "Decompressed size exceeds limit" in "".join(mock_rich_console.captured)


def test_registry_loader_bad_json(mock_rich_console):
    """Test invalid JSON response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    mock_resp.raw.read.return_value = b"{ invalid json }"

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            registry_loader.fetch_remote_registry("https://example.com/reg.json")

    assert "Failed to load" in "".join(mock_rich_console.captured)


def test_config_hydrate_missing_org(monkeypatch, mock_rich_console):
    """Ensure we warn on missing orgs."""
    monkeypatch.setattr("awsctl.registry.KNOWN_ORGS", [])

    # [FIX] Pass set, not dict, to match current config.py signature
    enabled_names = {"missing"}

    config._hydrate_orgs(enabled_names)

    # Check the CAPTURED output of the mock console
    assert "Warning: Org 'missing' not found" in "".join(mock_rich_console.captured)


def test_load_raw_config_missing_file(monkeypatch):
    monkeypatch.setattr(
        "awsctl.config.get_orgs_path",
        lambda ensure=False: MagicMock(exists=lambda: False),
    )
    assert config.load_raw_config() == {}


def test_load_raw_config_bad_yaml(monkeypatch, tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("{")
    monkeypatch.setattr("awsctl.config.get_orgs_path", lambda ensure=False: f)

    with pytest.raises(yaml.YAMLError):
        config.load_raw_config()
